"""Arrendatario (campo ARRENDATARIO del Excel maestro)."""
from app.core.database import db
from .base import BaseModel


class Arrendatario(BaseModel):
    __tablename__ = "arrendatarios"

    nombre_original = db.Column(db.String(255), nullable=False)
    nombre_normalizado = db.Column(db.String(255), nullable=False, unique=True, index=True)

    propiedades = db.relationship(
        "PropiedadArrendatario",
        back_populates="arrendatario",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre_original": self.nombre_original,
            "nombre_normalizado": self.nombre_normalizado,
        }