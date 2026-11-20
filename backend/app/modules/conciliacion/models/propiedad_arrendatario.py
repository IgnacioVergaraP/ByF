"""Relación muchos-a-muchos entre propiedades y arrendatarios."""
from app.core.database import db
from .base import BaseModel


class PropiedadArrendatario(BaseModel):
    __tablename__ = "propiedades_arrendatarios"

    propiedad_id = db.Column(
        db.String(36),
        db.ForeignKey("propiedades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    arrendatario_id = db.Column(
        db.String(36),
        db.ForeignKey("arrendatarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    propiedad = db.relationship("Propiedad", back_populates="arrendatarios")
    arrendatario = db.relationship("Arrendatario", back_populates="propiedades")

    __table_args__ = (
        db.UniqueConstraint(
            "propiedad_id", "arrendatario_id",
            name="uq_propiedad_arrendatario",
        ),
    )