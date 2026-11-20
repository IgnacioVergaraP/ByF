"""Aplicación de un movimiento bancario a una factura."""
from app.core.database import db
from .base import BaseModel


class AplicacionPago(BaseModel):
    __tablename__ = "aplicaciones_pago"

    movimiento_id = db.Column(
        db.String(36),
        db.ForeignKey("movimientos_bancarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    factura_id = db.Column(
        db.String(36),
        db.ForeignKey("facturas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monto_aplicado = db.Column(db.BigInteger, nullable=False)

    metodo = db.Column(db.String(16), nullable=False, default="manual")
    # manual | automatico

    activa = db.Column(db.Boolean, nullable=False, default=True, index=True)
    fecha_aplicacion = db.Column(db.Date, nullable=False)
    responsable = db.Column(db.String(128), nullable=True)

    llave_idempotencia = db.Column(
        db.String(128), nullable=False, unique=True, index=True
    )

    movimiento = db.relationship("MovimientoBancario", lazy="selectin")
    factura = db.relationship("Factura", lazy="selectin")

    __table_args__ = (
        # Un movimiento no puede tener dos aplicaciones activas a la misma factura
        db.Index(
            "uq_aplicacion_activa_mov_fact",
            "movimiento_id", "factura_id",
            unique=True,
            sqlite_where=db.text("activa = 1"),
            postgresql_where=db.text("activa IS TRUE"),
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "movimiento_id": self.movimiento_id,
            "factura_id": self.factura_id,
            "monto_aplicado": self.monto_aplicado,
            "metodo": self.metodo,
            "activa": self.activa,
            "fecha_aplicacion": self.fecha_aplicacion.isoformat() if self.fecha_aplicacion else None,
            "responsable": self.responsable,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
