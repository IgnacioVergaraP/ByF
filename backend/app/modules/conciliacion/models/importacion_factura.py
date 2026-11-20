"""Lote de carga masiva de facturas."""
from app.core.database import db
from .base import BaseModel


class ImportacionFactura(BaseModel):
    __tablename__ = "importaciones_facturas"

    archivos_recibidos = db.Column(db.Integer, nullable=False, default=0)
    facturas_procesadas = db.Column(db.Integer, nullable=False, default=0)
    facturas_validas = db.Column(db.Integer, nullable=False, default=0)
    facturas_duplicadas = db.Column(db.Integer, nullable=False, default=0)
    facturas_con_error = db.Column(db.Integer, nullable=False, default=0)
    detalle_json = db.Column(db.Text, nullable=True)

    facturas = db.relationship(
        "Factura", back_populates="importacion",
        cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "archivos_recibidos": self.archivos_recibidos,
            "facturas_procesadas": self.facturas_procesadas,
            "facturas_validas": self.facturas_validas,
            "facturas_duplicadas": self.facturas_duplicadas,
            "facturas_con_error": self.facturas_con_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }