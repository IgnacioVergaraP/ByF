"""Línea de detalle de una factura."""
from app.core.database import db
from .base import BaseModel


class DetalleFactura(BaseModel):
    __tablename__ = "detalles_factura"

    factura_id = db.Column(
        db.String(36),
        db.ForeignKey("facturas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo = db.Column(db.String(64), nullable=True)
    descripcion = db.Column(db.String(255), nullable=True)
    cantidad = db.Column(db.Numeric(12, 3), nullable=True)
    unidad = db.Column(db.String(16), nullable=True)
    precio_unitario = db.Column(db.Numeric(18, 2), nullable=True)
    descuento = db.Column(db.BigInteger, nullable=True)
    total_linea = db.Column(db.BigInteger, nullable=True)

    factura = db.relationship("Factura", back_populates="detalles")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "codigo": self.codigo,
            "descripcion": self.descripcion,
            "cantidad": float(self.cantidad) if self.cantidad is not None else None,
            "unidad": self.unidad,
            "precio_unitario": float(self.precio_unitario) if self.precio_unitario is not None else None,
            "descuento": self.descuento,
            "total_linea": self.total_linea,
        }