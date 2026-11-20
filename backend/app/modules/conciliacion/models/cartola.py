"""Cartola bancaria procesada."""
from app.core.database import db
from .base import BaseModel


class Cartola(BaseModel):
    __tablename__ = "cartolas"

    cuenta_id = db.Column(
        db.String(36),
        db.ForeignKey("cuentas_bancarias.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    centro_costo_id = db.Column(
        db.String(36),
        db.ForeignKey("centros_costo.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    numero_cartola = db.Column(db.String(64), nullable=True, index=True)
    periodo_desde = db.Column(db.Date, nullable=True)
    periodo_hasta = db.Column(db.Date, nullable=True)
    fecha_emision = db.Column(db.Date, nullable=True)

    archivo_nombre = db.Column(db.String(255), nullable=False)
    archivo_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)

    total_abonos_informado = db.Column(db.BigInteger, nullable=True)
    total_cargos_informado = db.Column(db.BigInteger, nullable=True)
    saldo_inicial_informado = db.Column(db.BigInteger, nullable=True)
    saldo_final_informado = db.Column(db.BigInteger, nullable=True)

    total_abonos_extraido = db.Column(db.BigInteger, nullable=True)
    cantidad_movimientos = db.Column(db.Integer, nullable=False, default=0)
    validacion_ok = db.Column(db.Boolean, nullable=False, default=False)
    validacion_mensaje = db.Column(db.Text, nullable=True)

    cuenta = db.relationship("CuentaBancaria", back_populates="cartolas")
    centro_costo = db.relationship("CentroCosto", lazy="selectin")
    movimientos = db.relationship(
        "MovimientoBancario", back_populates="cartola",
        cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self, include_movimientos: bool = False) -> dict:
        data = {
            "id": self.id,
            "numero_cartola": self.numero_cartola,
            "periodo_desde": self.periodo_desde.isoformat() if self.periodo_desde else None,
            "periodo_hasta": self.periodo_hasta.isoformat() if self.periodo_hasta else None,
            "archivo_nombre": self.archivo_nombre,
            "total_abonos_informado": self.total_abonos_informado,
            "total_abonos_extraido": self.total_abonos_extraido,
            "cantidad_movimientos": self.cantidad_movimientos,
            "validacion_ok": self.validacion_ok,
            "validacion_mensaje": self.validacion_mensaje,
            "cuenta": self.cuenta.to_dict() if self.cuenta else None,
            "centro_costo": (
                {"id": self.centro_costo.id, "codigo": self.centro_costo.codigo}
                if self.centro_costo else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_movimientos:
            data["movimientos"] = [m.to_dict() for m in self.movimientos]
        return data