"""Asociación aprendida entre un depositante bancario y un arrendatario."""
from app.core.database import db
from .base import BaseModel


class AsociacionDepositante(BaseModel):
    __tablename__ = "asociaciones_depositantes"

    depositante_original = db.Column(db.String(255), nullable=False)
    depositante_normalizado = db.Column(db.String(255), nullable=False, index=True)

    arrendatario_id = db.Column(
        db.String(36),
        db.ForeignKey("arrendatarios.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    arrendatario = db.relationship("Arrendatario", lazy="selectin")

    vigente = db.Column(db.Boolean, nullable=False, default=True, index=True)

    movimientos = db.relationship(
        "AsociacionMovimiento",
        back_populates="asociacion",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "depositante_normalizado", "arrendatario_id",
            name="uq_asociacion_depositante_arrendatario",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "depositante_original": self.depositante_original,
            "depositante_normalizado": self.depositante_normalizado,
            "arrendatario": self.arrendatario.to_dict() if self.arrendatario else None,
            "vigente": self.vigente,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }