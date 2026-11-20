"""Copia SQLite a Supabase mediante la Data API y verifica el total por tabla."""
from argparse import ArgumentParser
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select

from app.config import BASE_DIR
from app.core.database import db
from app.core.supabase_data_api import SupabaseDataAPI
from app.modules.conciliacion import models  # noqa: F401
from migrations.importar_postgres import verificar_origen


def _valor_json(valor):
    if isinstance(valor, (bytes, memoryview)):
        return "\\x" + bytes(valor).hex()
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=BASE_DIR / "instance" / "conciliacion.db")
    args = parser.parse_args()
    ruta = args.sqlite.resolve()
    if not ruta.is_file():
        parser.error("No existe el archivo SQLite indicado.")

    load_dotenv(BASE_DIR / ".env")
    api = SupabaseDataAPI()
    motor = create_engine(f"sqlite:///{ruta.as_uri()}?mode=ro&uri=true")
    tablas = db.metadata.sorted_tables
    with motor.connect() as origen:
        origen.exec_driver_sql("BEGIN")
        verificar_origen(origen, tablas)
        filas = {
            tabla.name: [
                {columna: _valor_json(valor) for columna, valor in fila.items()}
                for fila in origen.execute(select(tabla)).mappings()
            ]
            for tabla in tablas
        }
    cantidades = api.importar_sqlite(filas)
    if cantidades != {nombre: len(datos) for nombre, datos in filas.items()}:
        raise ValueError("Los totales que devolvió Supabase difieren de los datos de origen.")
    for nombre, cantidad in cantidades.items():
        print(f"{nombre}: {cantidad} filas")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error)) from None
