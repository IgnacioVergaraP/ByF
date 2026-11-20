"""Vínculo entre un movimiento bancario y las propiedades asociadas."""
import json

from app.core.database import db
from .base import BaseModel


class AsociacionMovimiento(BaseModel):
    __tablename__ = "asociaciones_movimientos"

    movimiento_id = db.Column(
        db.String(36),
        db.ForeignKey("movimientos_bancarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asociacion_id = db.Column(
        db.String(36),
        db.ForeignKey("asociaciones_depositantes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    propiedad_id = db.Column(
        db.String(36),
        db.ForeignKey("propiedades.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    conceptos_json = db.Column(db.Text, nullable=False, default="[]")
    estado = db.Column(db.String(32), nullable=False, default="manual")

    movimiento = db.relationship("MovimientoBancario", lazy="selectin")
    asociacion = db.relationship("AsociacionDepositante", back_populates="movimientos")
    propiedad = db.relationship("Propiedad", lazy="selectin")

    __table_args__ = (
        db.UniqueConstraint(
            "movimiento_id", "propiedad_id",
            name="uq_asociacion_movimiento_propiedad",
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
            "movimiento_id": self.movimiento_id,
            "asociacion_id": self.asociacion_id,
            "propiedad": {
                "id": self.propiedad.id,
                "nombre_original": self.propiedad.nombre_original,
            } if self.propiedad else None,
            "conceptos": self.conceptos,
            "estado": self.estado,
        }