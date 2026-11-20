"""Repositorio de aplicaciones de pago."""
from typing import Optional

from sqlalchemy import func

from app.core.database import db
from app.modules.conciliacion.models import (
    AplicacionPago,
    Factura,
    HistorialAplicacionPago,
    MovimientoBancario,
)


class AplicacionPagoRepository:
    # ---------- Consultas ----------
    def get_movimiento(self, movimiento_id: str) -> Optional[MovimientoBancario]:
        return MovimientoBancario.query.filter_by(id=movimiento_id).first()

    def get_factura(self, factura_id: str) -> Optional[Factura]:
        return Factura.query.filter_by(id=factura_id).first()

    def get_aplicacion(self, aplicacion_id: str) -> Optional[AplicacionPago]:
        return AplicacionPago.query.filter_by(id=aplicacion_id).first()

    def get_por_llave(self, llave: str) -> Optional[AplicacionPago]:
        return AplicacionPago.query.filter_by(llave_idempotencia=llave).first()

    def total_aplicado_movimiento(self, movimiento_id: str) -> int:
        result = (
            db.session.query(func.coalesce(func.sum(AplicacionPago.monto_aplicado), 0))
            .filter(
                AplicacionPago.movimiento_id == movimiento_id,
                AplicacionPago.activa.is_(True),
            )
            .scalar()
        )
        return int(result or 0)

    def total_pagado_factura(self, factura_id: str) -> int:
        result = (
            db.session.query(func.coalesce(func.sum(AplicacionPago.monto_aplicado), 0))
            .filter(
                AplicacionPago.factura_id == factura_id,
                AplicacionPago.activa.is_(True),
            )
            .scalar()
        )
        return int(result or 0)

    def aplicaciones_de_movimiento(
        self, movimiento_id: str, solo_activas: bool = True
    ) -> list[AplicacionPago]:
        q = AplicacionPago.query.filter_by(movimiento_id=movimiento_id)
        if solo_activas:
            q = q.filter(AplicacionPago.activa.is_(True))
        return q.all()

    def aplicaciones_de_factura(
        self, factura_id: str, solo_activas: bool = True
    ) -> list[AplicacionPago]:
        q = AplicacionPago.query.filter_by(factura_id=factura_id)
        if solo_activas:
            q = q.filter(AplicacionPago.activa.is_(True))
        return q.all()

    def facturas_de_movimiento(self, movimiento_id: str) -> list[Factura]:
        """Facturas vinculadas a un movimiento."""
        return (
            db.session.query(Factura)
            .join(AplicacionPago, AplicacionPago.factura_id == Factura.id)
            .filter(
                AplicacionPago.movimiento_id == movimiento_id,
                AplicacionPago.activa.is_(True),
            )
            .distinct()
            .all()
        )

    def movimientos_de_factura(self, factura_id: str) -> list[MovimientoBancario]:
        """Movimientos vinculados a una factura."""
        return (
            db.session.query(MovimientoBancario)
            .join(AplicacionPago, AplicacionPago.movimiento_id == MovimientoBancario.id)
            .filter(
                AplicacionPago.factura_id == factura_id,
                AplicacionPago.activa.is_(True),
            )
            .distinct()
            .all()
        )

    # ---------- Creaciones ----------
    def create_aplicacion(self, **kwargs) -> AplicacionPago:
        obj = AplicacionPago(**kwargs)
        db.session.add(obj)
        db.session.flush()
        return obj

    def add_historial(
        self, aplicacion_id: str, accion: str,
        detalle_json: str | None = None, responsable: str | None = None,
    ) -> HistorialAplicacionPago:
        obj = HistorialAplicacionPago(
            aplicacion_id=aplicacion_id,
            accion=accion,
            detalle_json=detalle_json,
            responsable=responsable,
        )
        db.session.add(obj)
        db.session.flush()
        return obj

    # ---------- Transacciones ----------
    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()