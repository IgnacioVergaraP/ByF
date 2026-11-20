"""Consolida centros de costo que solo difieren en mayúsculas y minúsculas.

Uso:
    cd backend
    python -m app.modules.conciliacion.utils.migration_cc

Requiere que la base esté respaldada antes de ejecutarse.
"""
from sqlalchemy import select

from app import create_app
from app.core.database import db
from app.modules.conciliacion.models import CentroCosto


def migrar() -> None:
    app = create_app()
    centros = CentroCosto.__table__
    referencias = [
        fk.parent
        for tabla in db.metadata.tables.values()
        for fk in tabla.foreign_keys
        if fk.column is centros.c.id
    ]
    cambios = []
    with app.app_context(), db.engine.begin() as conexion:
        grupos = {}
        filas = conexion.execute(select(centros.c.id, centros.c.codigo, centros.c.created_at))
        for centro in filas:
            grupos.setdefault(centro.codigo.casefold(), []).append(centro)

        for grupo in grupos.values():
            if len(grupo) < 2:
                continue
            canonico, *duplicados = sorted(
                grupo, key=lambda c: (not c.codigo.isupper(), c.created_at, c.id)
            )
            ids_duplicados = [c.id for c in duplicados]
            # Si hay una colisión de unicidad, se revierte la migración completa.
            for columna in referencias:
                conexion.execute(
                    columna.table.update()
                    .where(columna.in_(ids_duplicados))
                    .values({columna: canonico.id})
                )
            conexion.execute(centros.delete().where(centros.c.id.in_(ids_duplicados)))
            cambios.extend((c.codigo, canonico.codigo) for c in duplicados)

    for anterior, actual in cambios:
        print(f"Centro consolidado: {anterior} → {actual}")
    print(f"Centros consolidados: {len(cambios)}")


if __name__ == "__main__":
    migrar()
