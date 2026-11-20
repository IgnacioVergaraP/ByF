"""Asociación aprendida RUT receptor → arrendatario."""
from app.core.database import db
from .base import BaseModel


class IdentidadTributaria(BaseModel):
    __tablename__ = "identidades_tributarias"

    rut_receptor_normalizado = db.Column(
        db.String(16), nullable=False, unique=True, index=True
    )
    razon_social_original = db.Column(db.String(255), nullable=True)
    arrendatario_id = db.Column(
        db.String(36),
        db.ForeignKey("arrendatarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    arrendatario = db.relationship("Arrendatario", lazy="selectin")

    vigente = db.Column(db.Boolean, nullable=False, default=True, index=True)
    origen = db.Column(db.String(16), nullable=False, default="manual")
    # manual | auto

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rut_receptor_normalizado": self.rut_receptor_normalizado,
            "razon_social_original": self.razon_social_original,
            "arrendatario": self.arrendatario.to_dict() if self.arrendatario else None,
            "vigente": self.vigente,
            "origen": self.origen,
        }