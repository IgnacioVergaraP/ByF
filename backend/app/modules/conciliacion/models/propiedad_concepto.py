"""Relación muchos-a-muchos entre propiedades y conceptos."""
from app.core.database import db
from .base import BaseModel


class PropiedadConcepto(BaseModel):
    __tablename__ = "propiedades_conceptos"

    propiedad_id = db.Column(
        db.String(36),
        db.ForeignKey("propiedades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concepto_id = db.Column(
        db.String(36),
        db.ForeignKey("conceptos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    propiedad = db.relationship("Propiedad", back_populates="conceptos")
    concepto = db.relationship("Concepto", back_populates="propiedades")

    __table_args__ = (
        db.UniqueConstraint(
            "propiedad_id", "concepto_id",
            name="uq_propiedad_concepto",
        ),
    )