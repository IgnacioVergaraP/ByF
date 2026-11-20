"""Historial de auditoría de asociaciones."""
from app.core.database import db
from .base import BaseModel


class HistorialAsociacion(BaseModel):
    __tablename__ = "historial_asociaciones"

    movimiento_id = db.Column(
        db.String(36),
        db.ForeignKey("movimientos_bancarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    accion = db.Column(db.String(32), nullable=False)  # crear | corregir | desasociar
    detalle_json = db.Column(db.Text, nullable=True)
    usuario = db.Column(db.String(128), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "movimiento_id": self.movimiento_id,
            "accion": self.accion,
            "detalle_json": self.detalle_json,
            "usuario": self.usuario,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }