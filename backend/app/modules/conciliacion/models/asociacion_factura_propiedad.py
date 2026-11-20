"""Asociación factura → propiedad, con conceptos y método."""
import json

from app.core.database import db
from .base import BaseModel


class AsociacionFacturaPropiedad(BaseModel):
    __tablename__ = "asociaciones_factura_propiedad"

    factura_id = db.Column(
        db.String(36),
        db.ForeignKey("facturas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    propiedad_id = db.Column(
        db.String(36),
        db.ForeignKey("propiedades.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    centro_costo_id = db.Column(
        db.String(36),
        db.ForeignKey("centros_costo.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    conceptos_json = db.Column(db.Text, nullable=False, default="[]")
    estado = db.Column(db.String(32), nullable=False, default="asociada_manual")
    # asociada_manual | asociada_automatica | sugerida | pendiente
    metodo = db.Column(db.String(32), nullable=False, default="manual")
    # manual | por_rut_aprendido | por_codigo_linea | por_razon_social

    factura = db.relationship("Factura", back_populates="asociaciones")
    propiedad = db.relationship("Propiedad", lazy="selectin")
    centro_costo = db.relationship("CentroCosto", lazy="selectin")

    __table_args__ = (
        db.UniqueConstraint(
            "factura_id", "propiedad_id",
            name="uq_asociacion_factura_propiedad",
        ),
    )

    @property
    def conceptos(self) -> list[str]:
        try:
            return json.loads(self.conceptos_json or "[]")
        except (ValueError, TypeError):
            return []

    def set_conceptos(self, conceptos: list[str]) -> None:
        self.conceptos_json = json.dumps(conceptos or [], ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "factura_id": self.factura_id,
            "propiedad": {
                "id": self.propiedad.id,
                "nombre_original": self.propiedad.nombre_original,
            } if self.propiedad else None,
            "centro_costo": {
                "id": self.centro_costo.id,
                "codigo": self.centro_costo.codigo,
            } if self.centro_costo else None,
            "conceptos": self.conceptos,
            "estado": self.estado,
            "metodo": self.metodo,
        }