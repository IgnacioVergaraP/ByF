"""Inicializa el esquema privado y copia opcionalmente la base SQLite."""
from argparse import ArgumentParser
from contextlib import nullcontext
import os
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.schema import CreateSchema

from app.config import POSTGRES_SCHEMA, POSTGRES_SCHEMA_MAP, postgres_url
from app.core.database import db
from app.modules.conciliacion import models  # noqa: F401


def verificar_origen(origen, tablas):
    inspector = inspect(origen)
    nombres = {tabla.name for tabla in tablas}
    if set(inspector.get_table_names()) != nombres:
        raise ValueError("Las tablas de SQLite no coinciden con los modelos de la aplicación.")
    if origen.exec_driver_sql("PRAGMA foreign_key_check").first():
        raise ValueError("SQLite tiene referencias inválidas. Corrige el origen antes de migrar.")

    for tabla in tablas:
        columnas = {columna["name"] for columna in inspector.get_columns(tabla.name)}
        if columnas != set(tabla.columns.keys()):
            raise ValueError(f"Las columnas de {tabla.name} no coinciden con el modelo.")


def importar(origen, destino):
    tablas = db.metadata.sorted_tables
    verificar_origen(origen, tablas)
    for tabla in tablas:
        if destino.execute(select(tabla.c.id).limit(1)).first():
            raise ValueError(f"{tabla.name} ya contiene datos en PostgreSQL.")

    cantidades = {}
    for tabla in tablas:
        filas = origen.execute(select(tabla)).mappings()
        for lote in filas.partitions(100):
            destino.execute(tabla.insert(), [dict(fila) for fila in lote])
        total = origen.scalar(select(func.count()).select_from(tabla))
        if destino.scalar(select(func.count()).select_from(tabla)) != total:
            raise ValueError(f"La verificación de filas falló en {tabla.name}.")
        cantidades[tabla.name] = total
    return cantidades


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, help="Ruta a la base SQLite que se copiará")
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("Configura DATABASE_URL con la conexión de PostgreSQL.")

    sqlite = None
    if args.sqlite is not None:
        ruta = args.sqlite.resolve()
        if not ruta.is_file():
            parser.error("No existe el archivo SQLite indicado.")
        sqlite = create_engine(f"sqlite:///{ruta.as_uri()}?mode=ro&uri=true")

    postgres = create_engine(
        postgres_url(database_url),
        execution_options={"schema_translate_map": POSTGRES_SCHEMA_MAP},
        hide_parameters=True,
    )
    with sqlite.connect() if sqlite is not None else nullcontext() as origen:
        if origen is not None:
            origen.exec_driver_sql("BEGIN")
        with postgres.begin() as destino:
            # Serializa inicializaciones e importaciones de esta aplicación.
            destino.execute(text("SELECT pg_advisory_xact_lock(643490220)"))
            destino.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            destino.execute(CreateSchema(POSTGRES_SCHEMA, if_not_exists=True))
            db.metadata.create_all(destino)
            cantidades = importar(origen, destino) if origen is not None else {}

    print(f"Esquema listo: {POSTGRES_SCHEMA}")
    for tabla, total in cantidades.items():
        print(f"{tabla}: {total} filas")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error)) from None
