"""Cuenta bancaria receptora de cartolas."""
from app.core.database import db
from .base import BaseModel


class CuentaBancaria(BaseModel):
    __tablename__ = "cuentas_bancarias"

    banco = db.Column(db.String(128), nullable=False)
    numero_cuenta = db.Column(db.String(64), nullable=False, unique=True, index=True)
    moneda = db.Column(db.String(16), nullable=False, default="CLP")

    cartolas = db.relationship("Cartola", back_populates="cuenta", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "banco": self.banco,
            "numero_cuenta": self.numero_cuenta,
            "moneda": self.moneda,
        }