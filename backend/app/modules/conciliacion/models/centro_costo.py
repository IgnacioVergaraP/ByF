"""Centro de costo (campo CC del Excel maestro)."""
from app.core.database import db
from .base import BaseModel


class CentroCosto(BaseModel):
    __tablename__ = "centros_costo"

    codigo = db.Column(db.String(64), nullable=False, unique=True, index=True)
    nombre_original = db.Column(db.String(255), nullable=False)
    nombre_normalizado = db.Column(db.String(255), nullable=False, index=True)

    propiedades = db.relationship(
        "Propiedad", back_populates="centro_costo", lazy="selectin"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "codigo": self.codigo,
            "nombre_original": self.nombre_original,
            "nombre_normalizado": self.nombre_normalizado,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }