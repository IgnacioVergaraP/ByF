"""Propiedad (campo PROPIEDAD del Excel maestro)."""
from app.core.database import db
from .base import BaseModel


class Propiedad(BaseModel):
    __tablename__ = "propiedades"

    nombre_original = db.Column(db.String(255), nullable=False)
    nombre_normalizado = db.Column(db.String(255), nullable=False, index=True)

    centro_costo_id = db.Column(
        db.String(36),
        db.ForeignKey("centros_costo.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    centro_costo = db.relationship("CentroCosto", back_populates="propiedades")

    arrendatarios = db.relationship(
        "PropiedadArrendatario",
        back_populates="propiedad",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    conceptos = db.relationship(
        "PropiedadConcepto",
        back_populates="propiedad",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "centro_costo_id", "nombre_normalizado",
            name="uq_propiedad_cc_nombre_norm",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre_original": self.nombre_original,
            "nombre_normalizado": self.nombre_normalizado,
            "centro_costo": self.centro_costo.to_dict() if self.centro_costo else None,
            "arrendatarios": [
                pa.arrendatario.to_dict() for pa in self.arrendatarios
                if pa.arrendatario is not None
            ],
            "conceptos": [pc.concepto.nombre for pc in self.conceptos
                          if pc.concepto is not None],
        }