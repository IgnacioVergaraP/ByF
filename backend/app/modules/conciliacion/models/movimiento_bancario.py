"""Movimiento bancario (abono) extraído de una cartola."""
from app.core.database import db
from .base import BaseModel


class MovimientoBancario(BaseModel):
    __tablename__ = "movimientos_bancarios"

    cartola_id = db.Column(
        db.String(36),
        db.ForeignKey("cartolas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    centro_costo_id = db.Column(
        db.String(36),
        db.ForeignKey("centros_costo.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    fecha = db.Column(db.Date, nullable=False, index=True)
    descripcion_original = db.Column(db.Text, nullable=False)
    depositante_original = db.Column(db.String(255), nullable=True)
    depositante_normalizado = db.Column(db.String(255), nullable=True, index=True)
    monto = db.Column(db.BigInteger, nullable=False)

    pagina_origen = db.Column(db.Integer, nullable=False)
    orden_en_pagina = db.Column(db.Integer, nullable=False)
    huella_movimiento = db.Column(db.String(64), nullable=False, index=True)

    estado = db.Column(db.String(32), nullable=False, default="pendiente")

    cartola = db.relationship("Cartola", back_populates="movimientos")
    centro_costo = db.relationship("CentroCosto", lazy="selectin")

    __table_args__ = (
        db.UniqueConstraint(
            "cartola_id", "huella_movimiento",
            name="uq_movimiento_cartola_huella",
        ),
    )

    def _arrendatarios_asociados(self) -> list[dict]:
        from app.modules.conciliacion.models import AsociacionMovimiento
        asocs = AsociacionMovimiento.query.filter_by(movimiento_id=self.id).all()
        vistos: dict[str, dict] = {}
        for a in asocs:
            prop = a.propiedad
            if prop is None:
                continue
            for pa in prop.arrendatarios:
                arr = pa.arrendatario
                if arr is None:
                    continue
                if arr.id not in vistos:
                    vistos[arr.id] = {
                        "id": arr.id,
                        "nombre_original": arr.nombre_original,
                        "nombre_normalizado": arr.nombre_normalizado,
                    }
        return list(vistos.values())

    def _centros_costo_asociados(self) -> list[dict]:
        if self.centro_costo is not None:
            return [{
                "id": self.centro_costo.id,
                "codigo": self.centro_costo.codigo,
                "nombre_normalizado": self.centro_costo.nombre_normalizado,
            }]
        return []

    def _totales_aplicados(self) -> tuple[int, int, str]:
        """Devuelve (total_aplicado, disponible, totalidad)."""
        from app.modules.conciliacion.models import AplicacionPago
        from sqlalchemy import func

        result = (
            db.session.query(func.coalesce(func.sum(AplicacionPago.monto_aplicado), 0))
            .filter(
                AplicacionPago.movimiento_id == self.id,
                AplicacionPago.activa.is_(True),
            )
            .scalar()
        )
        total_aplicado = int(result or 0)
        disponible = max(0, int(self.monto) - total_aplicado)

        if total_aplicado == 0:
            totalidad = "sin_aplicar"
        elif disponible == 0:
            totalidad = "aplicado_total"
        else:
            totalidad = "aplicado_parcial"

        return total_aplicado, disponible, totalidad

    def _facturas_relacionadas(self) -> list[dict]:
        from app.modules.conciliacion.models import AplicacionPago, Factura
        asocs = (
            db.session.query(AplicacionPago, Factura)
            .join(Factura, Factura.id == AplicacionPago.factura_id)
            .filter(
                AplicacionPago.movimiento_id == self.id,
                AplicacionPago.activa.is_(True),
            )
            .all()
        )
        return [
            {"folio": f.folio, "factura_id": f.id, "monto_aplicado": ap.monto_aplicado}
            for ap, f in asocs
        ]

    def to_dict(self) -> dict:
        total_aplicado, disponible, totalidad = self._totales_aplicados()
        facturas = self._facturas_relacionadas()
        return {
            "id": self.id,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "descripcion_original": self.descripcion_original,
            "depositante_original": self.depositante_original,
            "depositante_normalizado": self.depositante_normalizado,
            "monto": self.monto,
            "pagina_origen": self.pagina_origen,
            "orden_en_pagina": self.orden_en_pagina,
            "estado": self.estado,
            "cartola_id": self.cartola_id,
            "centro_costo": (
                {"id": self.centro_costo.id, "codigo": self.centro_costo.codigo}
                if self.centro_costo else None
            ),
            "centros_costo": self._centros_costo_asociados(),
            "arrendatarios": self._arrendatarios_asociados(),
            "total_aplicado": total_aplicado,
            "disponible": disponible,
            "totalidad": totalidad,
            "facturas_relacionadas": facturas,
            "factura_folio": facturas[0]["folio"] if len(facturas) == 1 else (
                f"{facturas[0]['folio']} +{len(facturas)-1}" if len(facturas) > 1 else None
            ),
            "factura_totalidad": totalidad,
        }