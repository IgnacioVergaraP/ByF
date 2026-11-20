"""Concepto (campo CONCEPTO del Excel maestro)."""
from app.core.database import db
from .base import BaseModel


class Concepto(BaseModel):
    __tablename__ = "conceptos"

    nombre = db.Column(db.String(128), nullable=False, unique=True, index=True)
    nombre_normalizado = db.Column(db.String(128), nullable=False, index=True)

    propiedades = db.relationship(
        "PropiedadConcepto",
        back_populates="concepto",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "nombre_normalizado": self.nombre_normalizado,
        }