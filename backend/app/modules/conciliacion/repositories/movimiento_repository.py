"""Repositorio de movimientos bancarios."""
from app.core.database import db
from app.modules.conciliacion.models import MovimientoBancario


class MovimientoRepository:
    def create_movimiento(self, **kwargs) -> MovimientoBancario:
        obj = MovimientoBancario(**kwargs)
        db.session.add(obj)
        db.session.flush()
        return obj

    def list_movimientos(self, estado: str | None = None) -> list[MovimientoBancario]:
        q = MovimientoBancario.query
        if estado:
            q = q.filter_by(estado=estado)
        return q.order_by(
            MovimientoBancario.fecha.desc(),
            MovimientoBancario.pagina_origen,
            MovimientoBancario.orden_en_pagina,
        ).all()

    def count_by_estado(self, estado: str) -> int:
        return MovimientoBancario.query.filter_by(estado=estado).count()

    def sum_abonos(self) -> int:
        from sqlalchemy import func
        result = db.session.query(
            func.coalesce(func.sum(MovimientoBancario.monto), 0)
        ).scalar()
        return int(result or 0)