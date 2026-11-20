"""Blueprint del módulo Conciliación."""
from flask import Blueprint, jsonify, request

from app.core.database import db
from app.modules.conciliacion.repositories.asociacion_repository import (
    AsociacionRepository,
)
from app.modules.conciliacion.repositories.cartola_repository import CartolaRepository
from app.modules.conciliacion.repositories.maestro_repository import MaestroRepository
from app.modules.conciliacion.repositories.movimiento_repository import MovimientoRepository
from app.modules.conciliacion.services.asociacion_service import AsociacionService
from app.modules.conciliacion.services.cartola_service import CartolaService
from app.modules.conciliacion.services.grafo_service import GrafoService
from app.modules.conciliacion.services.import_service import ImportService
from app.modules.conciliacion.services.reconocimiento_service import ReconocimientoService

bp = Blueprint("conciliacion", __name__)

MAX_PDF_SIZE = 20 * 1024 * 1024


@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "module": "conciliacion", "version": "0.6.0"}), 200


# ---------- Maestro ----------
@bp.route("/maestro/import", methods=["POST"])
def import_maestro():
    if "file" not in request.files:
        return jsonify({"error": "Archivo no enviado"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Nombre de archivo vacío"}), 400
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        return jsonify({"error": "Formato no soportado. Usa .xlsx"}), 400
    service = ImportService()
    try:
        result = service.import_excel(file.stream)
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Error inesperado: {exc}"}), 500
    return jsonify({
        "total_rows": result.total_rows,
        "imported_rows": result.imported_rows,
        "skipped_rows": result.skipped_rows,
        "errors": result.errors,
    }), 200


@bp.route("/propiedades", methods=["GET"])
def list_propiedades():
    repo = MaestroRepository()
    props = repo.list_propiedades()
    return jsonify({"total": len(props), "items": [p.to_dict() for p in props]}), 200


@bp.route("/arrendatarios", methods=["GET"])
def list_arrendatarios():
    repo = MaestroRepository()
    arrs = repo.list_arrendatarios()
    return jsonify({"total": len(arrs), "items": [a.to_dict() for a in arrs]}), 200


@bp.route("/centros-costo", methods=["GET"])
def list_centros():
    repo = MaestroRepository()
    centros = repo.list_centros()
    return jsonify({"total": len(centros), "items": [c.to_dict() for c in centros]}), 200


# ---------- Cartolas ----------
@bp.route("/cartolas/import", methods=["POST"])
def import_cartola():
    if "file" not in request.files:
        return jsonify({"error": "Archivo no enviado"}), 400
    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Se requiere un archivo PDF"}), 400

    centro_costo_id = (request.form.get("centro_costo_id") or "").strip()
    if not centro_costo_id:
        return jsonify({"error": "Debes seleccionar un centro de costo"}), 400

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_PDF_SIZE:
        return jsonify({"error": "El archivo excede 20 MB"}), 400

    service = CartolaService()
    try:
        result = service.import_pdf(file.stream, file.filename, centro_costo_id)
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Error procesando la cartola: {exc}"}), 500

    if result.errores:
        return jsonify({
            "error": "No se pudo procesar la cartola",
            "detalles": result.errores,
        }), 400

    return jsonify({
        "cartola_id": result.cartola_id,
        "duplicada": result.duplicada,
        "cantidad_movimientos": result.cantidad_movimientos,
        "cantidad_cargos": result.cantidad_cargos,
        "total_abonos_extraido": result.total_abonos_extraido,
        "total_abonos_informado": result.total_abonos_informado,
        "validacion_ok": result.validacion_ok,
        "validacion_mensaje": result.validacion_mensaje,
    }), 200


@bp.route("/cartolas", methods=["GET"])
def list_cartolas():
    repo = CartolaRepository()
    cartolas = repo.list_cartolas()
    return jsonify({
        "total": len(cartolas),
        "items": [c.to_dict() for c in cartolas],
    }), 200


@bp.route("/cartolas/<cartola_id>", methods=["GET"])
def get_cartola(cartola_id: str):
    repo = CartolaRepository()
    cartola = repo.get_cartola(cartola_id)
    if cartola is None:
        return jsonify({"error": "Cartola no encontrada"}), 404
    return jsonify(cartola.to_dict(include_movimientos=True)), 200


# ---------- Movimientos ----------
@bp.route("/movimientos", methods=["GET"])
def list_movimientos():
    estado = request.args.get("estado")
    repo = MovimientoRepository()
    movs = repo.list_movimientos(estado=estado)
    total_abonos = sum(m.monto for m in movs)
    pendientes = sum(1 for m in movs if m.estado == "pendiente")
    asociados = sum(
        1 for m in movs if m.estado in ("asociado_manual", "asociado_automatico")
    )
    return jsonify({
        "total": len(movs),
        "total_abonos": total_abonos,
        "pendientes": pendientes,
        "asociados": asociados,
        "items": [m.to_dict() for m in movs],
    }), 200


@bp.route("/centros-costo-en-movimientos", methods=["GET"])
def centros_costo_en_movimientos():
    """Devuelve los CC que aparecen efectivamente en los movimientos."""
    from app.modules.conciliacion.models import CentroCosto, MovimientoBancario

    rows = (
        db.session.query(CentroCosto)
        .join(MovimientoBancario, MovimientoBancario.centro_costo_id == CentroCosto.id)
        .distinct()
        .order_by(CentroCosto.codigo)
        .all()
    )
    return jsonify({
        "total": len(rows),
        "items": [
            {"id": c.id, "codigo": c.codigo, "nombre_normalizado": c.nombre_normalizado}
            for c in rows
        ],
    }), 200


# ---------- Asociaciones ----------
@bp.route("/movimientos/<movimiento_id>/sugerencias", methods=["GET"])
def sugerencias(movimiento_id: str):
    repo = AsociacionRepository()
    mov = repo.get_movimiento(movimiento_id)
    if mov is None:
        return jsonify({"error": "Movimiento no encontrado"}), 404

    depositante_norm = mov.depositante_normalizado or ""
    asociaciones = repo.list_asociaciones_por_depositante(depositante_norm, solo_vigentes=True)

    coincidencia_exacta = None
    sugerencias_list = []
    if len(asociaciones) == 1:
        asoc = asociaciones[0]
        props = repo.propiedades_de_arrendatario(asoc.arrendatario_id)
        coincidencia_exacta = {
            "arrendatario": asoc.arrendatario.to_dict() if asoc.arrendatario else None,
            "propiedades": [
                {"id": p.id, "nombre_original": p.nombre_original} for p in props
            ],
        }
    elif len(asociaciones) > 1:
        for asoc in asociaciones:
            props = repo.propiedades_de_arrendatario(asoc.arrendatario_id)
            sugerencias_list.append({
                "arrendatario": asoc.arrendatario.to_dict() if asoc.arrendatario else None,
                "propiedades": [
                    {"id": p.id, "nombre_original": p.nombre_original} for p in props
                ],
            })

    return jsonify({
        "movimiento_id": mov.id,
        "depositante_original": mov.depositante_original,
        "depositante_normalizado": depositante_norm,
        "monto": mov.monto,
        "fecha": mov.fecha.isoformat() if mov.fecha else None,
        "coincidencia_exacta": coincidencia_exacta,
        "sugerencias": sugerencias_list,
    }), 200


@bp.route("/movimientos/<movimiento_id>/asociaciones", methods=["GET"])
def get_asociaciones_movimiento(movimiento_id: str):
    repo = AsociacionRepository()
    mov = repo.get_movimiento(movimiento_id)
    if mov is None:
        return jsonify({"error": "Movimiento no encontrado"}), 404
    asociaciones = repo.asociaciones_de_movimiento(movimiento_id)
    return jsonify({
        "movimiento_id": mov.id,
        "estado": mov.estado,
        "items": [a.to_dict() for a in asociaciones],
    }), 200


@bp.route("/movimientos/<movimiento_id>/asociar", methods=["POST"])
def asociar_movimiento(movimiento_id: str):
    data = request.get_json(silent=True) or {}
    arrendatario_id = data.get("arrendatario_id")
    propiedades = data.get("propiedades") or []
    if not arrendatario_id or not propiedades:
        return jsonify({"error": "Faltan arrendatario_id o propiedades"}), 400

    service = AsociacionService()
    result = service.asociar(
        movimiento_id=movimiento_id,
        arrendatario_id=arrendatario_id,
        propiedades=propiedades,
        accion="crear",
    )
    if not result.ok:
        return jsonify({"error": "; ".join(result.errores)}), 400
    return jsonify({
        "ok": True,
        "estado": result.estado,
        "asociacion_id": result.asociacion_id,
    }), 200


@bp.route("/movimientos/<movimiento_id>/corregir", methods=["POST"])
def corregir_movimiento(movimiento_id: str):
    data = request.get_json(silent=True) or {}
    arrendatario_id = data.get("arrendatario_id")
    propiedades = data.get("propiedades") or []
    if not arrendatario_id or not propiedades:
        return jsonify({"error": "Faltan arrendatario_id o propiedades"}), 400

    service = AsociacionService()
    result = service.asociar(
        movimiento_id=movimiento_id,
        arrendatario_id=arrendatario_id,
        propiedades=propiedades,
        accion="corregir",
    )
    if not result.ok:
        return jsonify({"error": "; ".join(result.errores)}), 400
    return jsonify({
        "ok": True,
        "estado": result.estado,
        "asociacion_id": result.asociacion_id,
    }), 200


@bp.route("/movimientos/<movimiento_id>/asociar", methods=["DELETE"])
def desasociar_movimiento(movimiento_id: str):
    service = AsociacionService()
    result = service.desasociar(movimiento_id=movimiento_id)
    if not result.ok:
        return jsonify({"error": "; ".join(result.errores)}), 400
    return jsonify({"ok": True, "estado": result.estado}), 200


@bp.route("/asociaciones", methods=["GET"])
def list_asociaciones():
    from app.modules.conciliacion.models import AsociacionDepositante
    items = AsociacionDepositante.query.order_by(
        AsociacionDepositante.depositante_normalizado
    ).all()
    return jsonify({
        "total": len(items),
        "items": [a.to_dict() for a in items],
    }), 200


@bp.route("/reconocimiento/run", methods=["POST"])
def run_reconocimiento():
    service = ReconocimientoService()
    result = service.reconocer_pendientes()
    return jsonify({
        "procesados": result.procesados,
        "automaticos": result.automaticos,
        "pendientes": result.pendientes,
        "errores": result.errores,
    }), 200


# ---------- Grafo ----------
@bp.route("/grafo", methods=["GET"])
def get_grafo():
    service = GrafoService()
    return jsonify(service.build()), 200


# ---------- Mapa ----------
@bp.route("/mapa/asociar", methods=["POST"])
def mapa_asociar():
    data = request.get_json(silent=True) or {}
    arrendatario_id = data.get("arrendatario_id")
    depositante_norm = data.get("depositante_normalizado")
    depositante_orig = data.get("depositante_original") or depositante_norm
    if not arrendatario_id or not depositante_norm:
        return jsonify({"error": "Faltan arrendatario_id o depositante_normalizado"}), 400

    from app.modules.conciliacion.models import AsociacionDepositante

    existente = AsociacionDepositante.query.filter_by(
        depositante_normalizado=depositante_norm,
        arrendatario_id=arrendatario_id,
    ).first()
    if existente is not None:
        existente.vigente = True
        existente.depositante_original = depositante_orig
        db.session.commit()
        return jsonify({"ok": True, "id": existente.id}), 200

    nueva = AsociacionDepositante(
        depositante_original=depositante_orig,
        depositante_normalizado=depositante_norm,
        arrendatario_id=arrendatario_id,
        vigente=True,
    )
    db.session.add(nueva)
    db.session.commit()
    return jsonify({"ok": True, "id": nueva.id}), 200


@bp.route("/mapa/asociar/<asociacion_id>", methods=["DELETE"])
def mapa_eliminar(asociacion_id: str):
    from app.modules.conciliacion.models import AsociacionDepositante

    asoc = AsociacionDepositante.query.filter_by(id=asociacion_id).first()
    if asoc is None:
        return jsonify({"error": "Asociación no encontrada"}), 404
    asoc.vigente = False
    db.session.commit()
    return jsonify({"ok": True}), 200


# ---------- Limpieza ----------
@bp.route("/limpiar", methods=["POST"])
def limpiar():
    from app.modules.conciliacion.services.limpieza_service import LimpiezaService

    data = request.get_json(silent=True) or {}
    service = LimpiezaService()
    result = service.limpiar(
        movimientos=bool(data.get("movimientos")),
        cartolas=bool(data.get("cartolas")),
        cuentas=bool(data.get("cuentas")),
        asociaciones=bool(data.get("asociaciones")),
        facturas=bool(data.get("facturas")),
    )
    if not result.ok:
        return jsonify({"error": "; ".join(result.errores)}), 400
    return jsonify({
        "ok": True,
        "eliminados": result.eliminados,
    }), 200
    

# ---------- Facturas ----------
@bp.route("/facturas/import", methods=["POST"])
def importar_facturas():
    from app.modules.conciliacion.services.factura_service import FacturaService

    if "files[]" not in request.files and "files" not in request.files:
        return jsonify({"error": "No se enviaron archivos"}), 400

    archivos = request.files.getlist("files[]") or request.files.getlist("files")
    if not archivos:
        return jsonify({"error": "Lista de archivos vacía"}), 400

    MAX_FACTURAS = 50
    MAX_SIZE = 15 * 1024 * 1024
    if len(archivos) > MAX_FACTURAS:
        return jsonify({"error": f"Máximo {MAX_FACTURAS} archivos por lote"}), 400

    pares = []
    for f in archivos:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            continue
        data = f.read()
        if len(data) > MAX_SIZE:
            continue
        pares.append((f.filename, data))

    if not pares:
        return jsonify({"error": "Ningún archivo PDF válido"}), 400

    service = FacturaService()
    try:
        result = service.importar_lote(pares)
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Error procesando lote: {exc}"}), 500

    return jsonify({
        "importacion_id": result.importacion_id,
        "archivos_recibidos": result.archivos_recibidos,
        "facturas_validas": result.facturas_validas,
        "facturas_duplicadas": result.facturas_duplicadas,
        "facturas_con_error": result.facturas_con_error,
        "detalles": [
            {"archivo": d.archivo, "ok": d.ok, "duplicada": d.duplicada,
             "folio": d.folio, "errores": d.errores}
            for d in result.detalles
        ],
    }), 200


@bp.route("/facturas", methods=["GET"])
def list_facturas():
    from app.modules.conciliacion.repositories.factura_repository import FacturaRepository
    repo = FacturaRepository()
    facturas = repo.list_facturas()
    return jsonify({
        "total": len(facturas),
        "items": [f.to_dict() for f in facturas],
    }), 200


# ---------- Gastos ----------
@bp.route("/gastos/archivos", methods=["GET"])
def listar_gastos_archivos():
    from app.modules.conciliacion.services.gastos_service import GastosService
    return jsonify(GastosService.listar_archivos(request.args.get("centro_costo_id"))), 200


@bp.route("/gastos/cartolas/<cartola_id>", methods=["DELETE"])
def eliminar_gastos_cartola(cartola_id):
    from app.modules.conciliacion.services.gastos_service import GastosService
    try:
        return jsonify(GastosService.eliminar_cartola_gastos(cartola_id)), 200
    except LookupError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 404


@bp.route("/gastos/excels/<excel_id>", methods=["DELETE"])
def eliminar_gastos_excel(excel_id):
    from app.modules.conciliacion.services.gastos_service import GastosService
    try:
        return jsonify(GastosService.eliminar_excel(excel_id)), 200
    except LookupError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 404


@bp.route("/gastos/catalogo", methods=["GET"])
def gastos_catalogo():
    from app.modules.conciliacion.services.gastos_service import GastosService
    return jsonify({"categorias": GastosService.catalogo()}), 200


@bp.route("/gastos", methods=["GET"])
def list_gastos():
    from app.modules.conciliacion.models import GastoEgreso
    from app.modules.conciliacion.services.gastos_service import GastosService

    gastos = GastoEgreso.query.order_by(
        GastoEgreso.fecha.desc(), GastoEgreso.pagina_origen,
        GastoEgreso.orden_en_pagina,
    ).all()
    items = [GastosService.egreso_dict(gasto) for gasto in gastos]
    centro_costo_id = request.args.get("centro_costo_id")
    tipo_gasto = request.args.get("tipo_gasto")
    estado = request.args.get("estado")
    categoria = request.args.get("categoria")
    subcategoria = request.args.get("subcategoria")
    if centro_costo_id:
        items = [item for item in items if item["centro_costo_id"] == centro_costo_id]
    if tipo_gasto:
        items = [item for item in items if item["tipo_gasto"] == tipo_gasto]
    if estado:
        items = [item for item in items if item["estado_conciliacion"] == estado]
    if categoria:
        items = [item for item in items if item["categoria"] == categoria]
    if subcategoria:
        items = [item for item in items if item["subcategoria"] == subcategoria]
    return jsonify({"total": len(items), "items": items}), 200


@bp.route("/gastos/<egreso_id>/clasificacion", methods=["PUT"])
def clasificar_gasto(egreso_id: str):
    from app.modules.conciliacion.models import GastoEgreso
    from app.modules.conciliacion.services.gastos_service import GastosService

    egreso = db.session.get(GastoEgreso, egreso_id)
    if egreso is None:
        return jsonify({"error": "Egreso no encontrado."}), 404
    data = request.get_json(silent=True) or {}
    try:
        GastosService().clasificar(
            egreso,
            str(data.get("tipo_gasto", "")),
            data.get("categoria"),
            data.get("subcategoria"),
            bool(data.get("recordar_regla", False)),
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify(GastosService.egreso_dict(egreso)), 200


@bp.route("/gastos/<egreso_id>/clasificacion", methods=["DELETE"])
def desclasificar_gasto(egreso_id: str):
    from app.modules.conciliacion.models import GastoEgreso
    from app.modules.conciliacion.services.gastos_service import GastosService

    egreso = db.session.get(GastoEgreso, egreso_id)
    if egreso is None:
        return jsonify({"error": "Egreso no encontrado."}), 404
    GastosService.desclasificar(egreso)
    db.session.commit()
    return jsonify(GastosService.egreso_dict(egreso)), 200


@bp.route("/gastos/documentos", methods=["GET"])
def list_gastos_documentos():
    from app.modules.conciliacion.services.gastos_service import GastosService
    documentos = GastosService.listar_documentos()
    centro_costo_id = request.args.get("centro_costo_id")
    if centro_costo_id:
        documentos = [
            documento for documento in documentos
            if documento["centro_costo_id"] == centro_costo_id
        ]
    return jsonify({"total": len(documentos), "items": documentos}), 200


@bp.route("/gastos/documentos", methods=["POST"])
def subir_gastos_documento():
    from werkzeug.utils import secure_filename
    from app.modules.conciliacion.services.gastos_service import GastosService

    archivo = request.files.get("file")
    centro_costo_id = (request.form.get("centro_costo_id") or "").strip()
    if archivo is None or not archivo.filename:
        return jsonify({"error": "Debes seleccionar un Excel de gastos."}), 400
    if not centro_costo_id:
        return jsonify({"error": "Debes seleccionar un centro de costo."}), 400
    if not archivo.filename.lower().endswith(".xlsx"):
        return jsonify({"error": "Los gastos deben cargarse en formato Excel (.xlsx)."}), 400
    contenido = archivo.read(MAX_PDF_SIZE + 1)
    if not contenido:
        return jsonify({"error": "El documento está vacío."}), 400
    if len(contenido) > MAX_PDF_SIZE:
        return jsonify({"error": "El documento excede 20 MB."}), 400
    try:
        resultado = GastosService().importar_excel(
            centro_costo_id,
            secure_filename(archivo.filename),
            contenido,
        )
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify(resultado), 200


@bp.route("/gastos/documentos/<documento_id>/descargar", methods=["GET"])
def descargar_gastos_documento(documento_id: str):
    from io import BytesIO
    from flask import send_file
    from app.core.supabase_persistencia import contenido_gasto
    from app.modules.conciliacion.models import GastoDocumento, GastoExcelFila, GastoExcel

    documento = db.session.get(GastoDocumento, documento_id)
    if documento is None:
        return jsonify({"error": "Documento no encontrado."}), 404
    fila = GastoExcelFila.query.filter_by(documento_id=documento_id).first()
    excel = db.session.get(GastoExcel, fila.excel_id) if fila else None
    return send_file(
        BytesIO(contenido_gasto(excel or documento)),
        mimetype=documento.content_type,
        as_attachment=True,
        download_name=documento.archivo_nombre,
    )


@bp.route("/gastos/<egreso_id>/asociaciones", methods=["POST"])
def asociar_gasto_documento(egreso_id: str):
    from app.modules.conciliacion.services.gastos_service import GastosService
    data = request.get_json(silent=True) or {}
    documento_id = str(data.get("documento_id", ""))
    try:
        asociacion = GastosService.asociar(
            egreso_id, documento_id, bool(data.get("confirmar", False))
        )
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "id": asociacion.id,
        "estado": asociacion.estado,
    }), 200


@bp.route("/gastos/asociaciones/<asociacion_id>/confirmar", methods=["POST"])
def confirmar_gasto_asociacion(asociacion_id: str):
    from app.modules.conciliacion.models import GastoAsociacion
    asociacion = db.session.get(GastoAsociacion, asociacion_id)
    if asociacion is None:
        return jsonify({"error": "Sugerencia de asociación no encontrada."}), 404
    from app.modules.conciliacion.services.gastos_service import GastosService
    try:
        asociacion = GastosService.asociar(asociacion.egreso_id, asociacion.documento_id, True)
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"id": asociacion.id, "estado": asociacion.estado}), 200


@bp.route("/gastos/asociaciones/<asociacion_id>", methods=["DELETE"])
def desasociar_gasto_documento(asociacion_id: str):
    from app.modules.conciliacion.models import GastoAsociacion
    asociacion = db.session.get(GastoAsociacion, asociacion_id)
    if asociacion is None:
        return jsonify({"error": "Asociación no encontrada."}), 404
    db.session.delete(asociacion)
    db.session.commit()
    return jsonify({"ok": True}), 200


@bp.route("/facturas/<factura_id>", methods=["GET"])
def get_factura(factura_id: str):
    from app.modules.conciliacion.repositories.factura_repository import FacturaRepository
    repo = FacturaRepository()
    factura = repo.get_factura(factura_id)
    if factura is None:
        return jsonify({"error": "Factura no encontrada"}), 404
    return jsonify(factura.to_dict(include_detalles=True)), 200


@bp.route("/facturas/importaciones", methods=["GET"])
def list_importaciones_facturas():
    from app.modules.conciliacion.repositories.factura_repository import FacturaRepository
    repo = FacturaRepository()
    importaciones = repo.list_importaciones()
    return jsonify({
        "total": len(importaciones),
        "items": [i.to_dict() for i in importaciones],
    }), 200
    
# ---------- Asociación de facturas ----------
@bp.route("/facturas/<factura_id>/sugerencias", methods=["GET"])
def facturas_sugerencias(factura_id: str):
    from app.modules.conciliacion.services.factura_asociacion_service import (
        FacturaAsociacionService,
    )
    service = FacturaAsociacionService()
    r = service.sugerir(factura_id)
    if r.errores:
        return jsonify({"error": "; ".join(r.errores)}), 400
    return jsonify({
        "factura_id": r.factura_id,
        "rut_receptor": r.rut_receptor,
        "razon_social_receptor": r.razon_social_receptor,
        "codigos_detectados": r.codigos_detectados,
        "identidad_aprendida": r.identidad_aprendida,
        "sugerencias": [
            {
                "arrendatario_id": s.arrendatario_id,
                "nombre": s.nombre,
                "score": s.score,
                "propiedades": s.propiedades,
            }
            for s in r.sugerencias
        ],
    }), 200


@bp.route("/facturas/<factura_id>/asociar", methods=["POST"])
def facturas_asociar(factura_id: str):
    from app.modules.conciliacion.services.factura_asociacion_service import (
        FacturaAsociacionService,
    )
    data = request.get_json(silent=True) or {}
    arr_id = data.get("arrendatario_id")
    propiedades = data.get("propiedades") or []
    confirmar = bool(data.get("confirmar_identidad", True))
    if not arr_id or not propiedades:
        return jsonify({"error": "Faltan arrendatario_id o propiedades"}), 400

    service = FacturaAsociacionService()
    r = service.asociar(factura_id, arr_id, propiedades, confirmar_identidad=confirmar)
    if not r.ok:
        return jsonify({"error": "; ".join(r.errores)}), 400
    return jsonify({"ok": True, "estado_asociacion": r.estado_asociacion}), 200


@bp.route("/facturas/<factura_id>/asociar", methods=["DELETE"])
def facturas_desasociar(factura_id: str):
    from app.modules.conciliacion.services.factura_asociacion_service import (
        FacturaAsociacionService,
    )
    service = FacturaAsociacionService()
    r = service.desasociar(factura_id)
    if not r.ok:
        return jsonify({"error": "; ".join(r.errores)}), 400
    return jsonify({"ok": True, "estado_asociacion": r.estado_asociacion}), 200


@bp.route("/facturas/<factura_id>/asociaciones", methods=["GET"])
def facturas_asociaciones(factura_id: str):
    from app.modules.conciliacion.repositories.factura_asociacion_repository import (
        FacturaAsociacionRepository,
    )
    repo = FacturaAsociacionRepository()
    factura = repo.get_factura(factura_id)
    if factura is None:
        return jsonify({"error": "Factura no encontrada"}), 404
    return jsonify({
        "factura_id": factura.id,
        "estado_asociacion": factura.estado_asociacion,
        "items": [a.to_dict() for a in repo.asociaciones_de_factura(factura_id)],
    }), 200


@bp.route("/facturas/<factura_id>/historial", methods=["GET"])
def facturas_historial(factura_id: str):
    from app.modules.conciliacion.repositories.factura_asociacion_repository import (
        FacturaAsociacionRepository,
    )
    repo = FacturaAsociacionRepository()
    return jsonify({
        "factura_id": factura_id,
        "items": [h.to_dict() for h in repo.list_historial(factura_id)],
    }), 200


@bp.route("/facturas/reconocimiento/run", methods=["POST"])
def facturas_reconocimiento_run():
    from app.modules.conciliacion.services.factura_asociacion_service import (
        FacturaAsociacionService,
    )
    service = FacturaAsociacionService()
    r = service.reconocer_todas()
    return jsonify(r), 200


# ---------- Identidades tributarias ----------
@bp.route("/identidades-tributarias", methods=["GET"])
def identidades_list():
    from app.modules.conciliacion.repositories.factura_asociacion_repository import (
        FacturaAsociacionRepository,
    )
    repo = FacturaAsociacionRepository()
    items = repo.list_identidades()
    return jsonify({
        "total": len(items),
        "items": [i.to_dict() for i in items],
    }), 200


@bp.route("/identidades-tributarias", methods=["POST"])
def identidades_upsert():
    from app.modules.conciliacion.repositories.factura_asociacion_repository import (
        FacturaAsociacionRepository,
    )
    from app.modules.conciliacion.utils.rut import normalizar_rut

    data = request.get_json(silent=True) or {}
    rut = normalizar_rut(data.get("rut_receptor") or "")
    arr_id = data.get("arrendatario_id")
    razon = data.get("razon_social")
    if not rut or not arr_id:
        return jsonify({"error": "Faltan rut_receptor válido o arrendatario_id"}), 400

    repo = FacturaAsociacionRepository()
    ident = repo.upsert_identidad(rut, razon, arr_id, origen="manual")
    repo.commit()
    return jsonify({"ok": True, "id": ident.id}), 200

# ---------- Conciliación / Aplicaciones de pago ----------
@bp.route("/movimientos/<movimiento_id>/sugerencias-facturas", methods=["GET"])
def movimiento_sugerencias_facturas(movimiento_id: str):
    from app.modules.conciliacion.services.conciliacion_service import (
        ConciliacionService,
    )
    service = ConciliacionService()
    return jsonify({"items": service.sugerencias_para_movimiento(movimiento_id)}), 200


@bp.route("/facturas/<factura_id>/sugerencias-movimientos", methods=["GET"])
def factura_sugerencias_movimientos(factura_id: str):
    from app.modules.conciliacion.services.conciliacion_service import (
        ConciliacionService,
    )
    service = ConciliacionService()
    return jsonify({"items": service.sugerencias_para_factura(factura_id)}), 200


@bp.route("/aplicaciones-pago", methods=["POST"])
def crear_aplicacion_pago():
    from app.modules.conciliacion.services.conciliacion_service import (
        ConciliacionService,
    )
    data = request.get_json(silent=True) or {}
    movimiento_id = data.get("movimiento_id")
    factura_id = data.get("factura_id")
    monto = data.get("monto_aplicado")
    if not movimiento_id or not factura_id or monto is None:
        return jsonify({"error": "Faltan movimiento_id, factura_id o monto_aplicado"}), 400

    try:
        monto_int = int(monto)
    except (TypeError, ValueError):
        return jsonify({"error": "monto_aplicado debe ser un entero"}), 400

    service = ConciliacionService()
    r = service.aplicar_pago(
        movimiento_id=movimiento_id,
        factura_id=factura_id,
        monto_aplicado=monto_int,
        metodo=data.get("metodo", "manual"),
        responsable=data.get("responsable"),
        llave_idempotencia=data.get("llave_idempotencia"),
    )
    if not r.ok:
        return jsonify({"error": "; ".join(r.errores)}), 400
    return jsonify({
        "ok": True,
        "aplicacion_id": r.aplicacion_id,
        "idempotente": r.idempotente,
        "excedente": r.excedente,
    }), 200


@bp.route("/aplicaciones-pago/<aplicacion_id>/revertir", methods=["POST"])
def revertir_aplicacion_pago(aplicacion_id: str):
    from app.modules.conciliacion.services.conciliacion_service import (
        ConciliacionService,
    )
    data = request.get_json(silent=True) or {}
    service = ConciliacionService()
    r = service.revertir(aplicacion_id, responsable=data.get("responsable"))
    if not r.ok:
        return jsonify({"error": "; ".join(r.errores)}), 400
    return jsonify({"ok": True, "aplicacion_id": r.aplicacion_id}), 200


@bp.route("/aplicaciones-pago", methods=["GET"])
def listar_aplicaciones_pago():
    from app.modules.conciliacion.models import AplicacionPago
    factura_id = request.args.get("factura_id")
    movimiento_id = request.args.get("movimiento_id")
    q = AplicacionPago.query
    if factura_id:
        q = q.filter_by(factura_id=factura_id)
    if movimiento_id:
        q = q.filter_by(movimiento_id=movimiento_id)
    items = q.order_by(AplicacionPago.created_at.desc()).all()
    return jsonify({
        "total": len(items),
        "items": [a.to_dict() for a in items],
    }), 200


@bp.route("/facturas/<factura_id>/excedentes", methods=["GET"])
def factura_excedentes(factura_id: str):
    from app.modules.conciliacion.models import AplicacionPago, Factura
    from app.modules.conciliacion.services.conciliacion_service import ConciliacionService

    if db.session.get(Factura, factura_id) is None:
        return jsonify({"error": "Factura no encontrada"}), 404
    aplicaciones = AplicacionPago.query.filter_by(
        factura_id=factura_id, activa=True,
    ).order_by(AplicacionPago.created_at.desc()).all()
    service = ConciliacionService()
    items = []
    vistos = set()
    for aplicacion in aplicaciones:
        if aplicacion.movimiento_id in vistos:
            continue
        vistos.add(aplicacion.movimiento_id)
        excedente = service._calcular_excedente(aplicacion.movimiento_id, factura_id)
        if excedente is not None:
            items.append(excedente)
    return jsonify({"items": items}), 200


@bp.route("/facturas/<factura_id>/saldos", methods=["GET"])
def factura_saldos(factura_id: str):
    from app.modules.conciliacion.repositories.aplicacion_pago_repository import (
        AplicacionPagoRepository,
    )
    repo = AplicacionPagoRepository()
    f = repo.get_factura(factura_id)
    if f is None:
        return jsonify({"error": "Factura no encontrada"}), 404
    total = int(f.total or 0)
    pagado = repo.total_pagado_factura(factura_id)
    saldo = max(0, total - pagado)
    if f.estado != "procesada":
        estado_pago = "requiere_revision"
    elif pagado == 0:
        estado_pago = "pendiente"
    elif saldo == 0:
        estado_pago = "pagada"
    else:
        estado_pago = "parcial"
    return jsonify({
        "factura_id": factura_id,
        "total": total,
        "total_pagado": pagado,
        "saldo_pendiente": saldo,
        "estado_pago": estado_pago,
    }), 200


@bp.route("/movimientos/<movimiento_id>/saldos", methods=["GET"])
def movimiento_saldos(movimiento_id: str):
    from app.modules.conciliacion.repositories.aplicacion_pago_repository import (
        AplicacionPagoRepository,
    )
    repo = AplicacionPagoRepository()
    m = repo.get_movimiento(movimiento_id)
    if m is None:
        return jsonify({"error": "Movimiento no encontrado"}), 404
    monto = int(m.monto)
    aplicado = repo.total_aplicado_movimiento(movimiento_id)
    disponible = max(0, monto - aplicado)
    if aplicado == 0:
        totalidad = "sin_aplicar"
    elif disponible == 0:
        totalidad = "aplicado_total"
    else:
        totalidad = "aplicado_parcial"
    return jsonify({
        "movimiento_id": movimiento_id,
        "monto": monto,
        "total_aplicado": aplicado,
        "disponible": disponible,
        "totalidad": totalidad,
    }), 200


@bp.route("/conciliacion/reconocer", methods=["POST"])
def conciliacion_reconocer():
    from app.modules.conciliacion.services.conciliacion_service import (
        ConciliacionService,
    )
    service = ConciliacionService()
    r = service.reconocer_todos()
    return jsonify({
        "grupos_procesados": r.grupos_procesados,
        "aplicaciones_creadas": r.aplicaciones_creadas,
        "errores": r.errores,
        "detalle": r.detalle,
    }), 200
    
# ---------- Aplicar cadena descubierta ----------
@bp.route("/conciliacion/aplicar-cadena", methods=["POST"])
def conciliacion_aplicar_cadena():
    """Aplica una cadena descubierta: aprende las capas y crea la aplicación."""
    from app.modules.conciliacion.services.aprendizaje_service import (
        AprendizajeService, CadenaDescubierta,
    )
    from app.modules.conciliacion.models import AplicacionPago
    from app.modules.conciliacion.utils.idempotencia import generar_llave
    from datetime import date

    data = request.get_json(silent=True) or {}
    mov_id = data.get("movimiento_id")
    arr_id = data.get("arrendatario_id")
    prop_id = data.get("propiedad_id")
    fact_id = data.get("factura_id")
    monto = data.get("monto_aplicado")

    if not all([mov_id, arr_id, prop_id, fact_id, monto]):
        return jsonify({"error": "Faltan datos de la cadena"}), 400

    try:
        monto_int = int(monto)
    except (TypeError, ValueError):
        return jsonify({"error": "monto_aplicado debe ser un entero"}), 400

    cadena = CadenaDescubierta(
        movimiento_id=mov_id,
        arrendatario_id=arr_id,
        propiedad_id=prop_id,
        factura_id=fact_id,
        score_total=100,
    )

    try:
        service = AprendizajeService()
        service.aprender_cadena(cadena, origen="manual")
        llave = generar_llave()
        db.session.add(AplicacionPago(
            movimiento_id=mov_id,
            factura_id=fact_id,
            monto_aplicado=monto_int,
            metodo="manual",
            activa=True,
            fecha_aplicacion=date.today(),
            llave_idempotencia=llave,
        ))
        db.session.commit()
        return jsonify({"ok": True}), 200
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 500
    
@bp.route("/facturas/<factura_id>/reprocesar", methods=["POST"])
def factura_reprocesar(factura_id: str):
    from app.modules.conciliacion.services.factura_service import FacturaService
    service = FacturaService()
    r = service.reprocesar(factura_id)
    if not r.get("ok"):
        return jsonify({"error": r.get("error", "Error desconocido")}), 400
    return jsonify(r), 200

@bp.route("/movimientos-disponibles", methods=["GET"])
def movimientos_disponibles():
    """Lista movimientos con disponible > 0 para aplicar pagos."""
    from app.modules.conciliacion.repositories.aplicacion_pago_repository import (
        AplicacionPagoRepository,
    )
    repo = AplicacionPagoRepository()
    from app.modules.conciliacion.models import MovimientoBancario
    movs = MovimientoBancario.query.order_by(
        MovimientoBancario.fecha.desc()
    ).all()
    items = []
    for m in movs:
        disponible = int(m.monto) - repo.total_aplicado_movimiento(m.id)
        if disponible <= 0:
            continue
        items.append({
            "id": m.id,
            "fecha": m.fecha.isoformat() if m.fecha else None,
            "depositante_original": m.depositante_original,
            "depositante_normalizado": m.depositante_normalizado,
            "monto": int(m.monto),
            "disponible": disponible,
        })
    return jsonify({"total": len(items), "items": items}), 200
