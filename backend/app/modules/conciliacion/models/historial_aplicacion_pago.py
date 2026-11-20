"""Auditoría de aplicaciones de pago."""
from app.core.database import db
from .base import BaseModel


class HistorialAplicacionPago(BaseModel):
    __tablename__ = "historial_aplicaciones_pago"

    aplicacion_id = db.Column(
        db.String(36),
        db.ForeignKey("aplicaciones_pago.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    accion = db.Column(db.String(32), nullable=False)
    # crear | revertir | corregir
    detalle_json = db.Column(db.Text, nullable=True)
    responsable = db.Column(db.String(128), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "aplicacion_id": self.aplicacion_id,
            "accion": self.accion,
            "detalle_json": self.detalle_json,
            "responsable": self.responsable,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }