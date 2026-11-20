"""Adapta las transacciones de conciliación a las llamadas RPC de Supabase."""
from datetime import datetime, timezone
import json

from flask import g, jsonify, request
from sqlalchemy import DateTime, LargeBinary, create_engine, event
from sqlalchemy.pool import StaticPool

from app.core.database import db, motor_solicitud
from app.core.supabase_data_api import ErrorDataAPI, SupabaseDataAPI


def _json_fila(columnas, valores):
    return json.dumps({
        columna: "\\x" + valor.hex() if isinstance(valor, bytes) else valor
        for columna, valor in zip(columnas, valores)
    }, ensure_ascii=False, allow_nan=False)


def _instalar_registro(conexion, tabla):
    columnas = [c.name for c in tabla.columns if c.name != "id"]
    nombre = tabla.name
    viejos = ", ".join(f'OLD."{c}"' for c in columnas)
    nuevos = ", ".join(f'NEW."{c}"' for c in columnas)
    conexion.create_function(f"fila_{nombre}", len(columnas),
                             lambda *valores: _json_fila(columnas, valores))

    def campos_cambiados(*valores):
        anteriores, actuales = valores[:len(columnas)], valores[len(columnas):]
        cambiadas = {c: nuevo for c, viejo, nuevo in zip(columnas, anteriores, actuales)
                    if viejo != nuevo}
        return _json_fila(cambiadas.keys(), cambiadas.values())

    conexion.create_function(f"cambios_{nombre}", 2 * len(columnas), campos_cambiados)
    # BEFORE DELETE conserva el orden entre el padre y los efectos en cascada.
    for operacion, momento, id_fila, datos in (
        ("INSERT", "AFTER", "NEW.id", f"fila_{nombre}({nuevos})"),
        ("UPDATE", "AFTER", "NEW.id", f"cambios_{nombre}({viejos}, {nuevos})"),
        ("DELETE", "BEFORE", "OLD.id", "NULL"),
    ):
        conexion.execute(f'''
            CREATE TEMP TRIGGER "{nombre}_{operacion}" {momento} {operacion} ON "{nombre}"
            BEGIN
                INSERT INTO cambios_app (tabla, operacion, id_fila, datos)
                VALUES ('{nombre}', '{operacion}', {id_fila}, {datos});
            END
        ''')


def _fila_sqlite(tabla, fila):
    for columna in tabla.columns:
        if isinstance(columna.type, LargeBinary):
            yield b""
        elif isinstance(columna.type, DateTime) and fila[columna.name] is not None:
            fecha = datetime.fromisoformat(fila[columna.name])
            if fecha.tzinfo is not None:
                fecha = fecha.astimezone(timezone.utc).replace(tzinfo=None)
            yield fecha.isoformat(sep=" ", timespec="microseconds")
        else:
            yield fila[columna.name]


def _cargar_motor(filas):
    tablas = db.metadata.sorted_tables
    if set(filas) != {tabla.name for tabla in tablas}:
        raise RuntimeError("El esquema remoto no coincide con los modelos de conciliación.")
    motor = create_engine("sqlite://", poolclass=StaticPool)

    @event.listens_for(motor, "connect")
    def configurar(conexion, _registro):
        conexion.isolation_level = None

    @event.listens_for(motor, "begin")
    def iniciar(conexion):
        conexion.exec_driver_sql("BEGIN")

    try:
        with motor.begin() as conexion:
            db.metadata.create_all(conexion)
            for tabla in tablas:
                datos = [tuple(_fila_sqlite(tabla, fila)) for fila in filas[tabla.name]]
                if datos:
                    marcadores = ", ".join("?" for _ in tabla.columns)
                    conexion.exec_driver_sql(f'INSERT INTO "{tabla.name}" VALUES ({marcadores})', datos)

        with motor.begin() as conexion:
            conexion.exec_driver_sql("""
                CREATE TEMP TABLE cambios_app (
                    orden INTEGER PRIMARY KEY,
                    tabla TEXT NOT NULL,
                    operacion TEXT NOT NULL,
                    id_fila TEXT NOT NULL,
                    datos TEXT
                )
            """)
            for tabla in tablas:
                _instalar_registro(conexion.connection.driver_connection, tabla)
    except BaseException:
        motor.dispose()
        raise
    return motor


def _respuesta_error(error):
    if error.codigo == "40001":
        return jsonify(error="Los datos cambiaron durante la operación. Actualiza e inténtalo nuevamente."), 409
    return jsonify(error="No se pudo completar la operación con Supabase."), 503


def habilitar_supabase(app, blueprint):
    api = SupabaseDataAPI()

    @app.errorhandler(ErrorDataAPI)
    def error_data_api(error):
        app.logger.warning("%s", error)
        return _respuesta_error(error)

    @app.before_request
    def cargar_datos():
        if request.blueprint != blueprint or request.endpoint == f"{blueprint}.health" or request.method == "OPTIONS":
            return
        datos = api.rpc("datos_conciliacion", {})
        motor = _cargar_motor(datos["filas"])
        g.conciliacion_remota = (api, datos["revision"], motor, motor_solicitud.set(motor))

    @app.after_request
    def guardar_datos(respuesta):
        estado = g.get("conciliacion_remota")
        if estado is None or respuesta.status_code >= 400:
            return respuesta
        _, revision, motor, _ = estado
        # Descarta las escrituras que el servicio no llegó a confirmar.
        db.session.remove()
        with motor.connect() as conexion:
            filas = conexion.exec_driver_sql("""
                SELECT tabla, operacion, id_fila, datos FROM cambios_app ORDER BY orden
            """)
            cambios = [
                {"tabla": tabla, "operacion": operacion, "id": id_fila,
                 "datos": json.loads(datos) if datos is not None else None}
                for tabla, operacion, id_fila, datos in filas
                if datos != "{}"
            ]
        if cambios:
            try:
                api.rpc("guardar_conciliacion", {"p_revision": revision, "p_cambios": cambios})
            except ErrorDataAPI as error:
                app.logger.warning("%s", error)
                cuerpo, codigo = _respuesta_error(error)
                cuerpo.status_code = codigo
                return cuerpo
        return respuesta

    @app.teardown_request
    def cerrar_datos(_error):
        estado = g.pop("conciliacion_remota", None)
        if estado is not None:
            _, _, motor, token = estado
            try:
                db.session.remove()
            finally:
                motor_solicitud.reset(token)
                motor.dispose()


def contenido_gasto(documento):
    estado = g.get("conciliacion_remota")
    if estado is None:
        return documento.contenido
    api, revision, _, _ = estado
    contenido = api.rpc("archivo_conciliacion", {
        "p_revision": revision, "p_tabla": documento.__tablename__, "p_id": documento.id,
    })
    return bytes.fromhex(contenido)
