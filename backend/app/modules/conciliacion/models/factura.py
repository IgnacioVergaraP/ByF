"""Factura electrónica chilena."""
from app.core.database import db
from .base import BaseModel


class Factura(BaseModel):
    __tablename__ = "facturas"

    importacion_id = db.Column(
        db.String(36),
        db.ForeignKey("importaciones_facturas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    tipo_documento = db.Column(db.String(32), nullable=False, default="FACTURA_ELECTRONICA")
    folio = db.Column(db.String(32), nullable=False, index=True)
    rut_emisor = db.Column(db.String(16), nullable=True, index=True)
    rut_emisor_normalizado = db.Column(db.String(16), nullable=True, index=True)
    razon_social_emisor = db.Column(db.String(255), nullable=True)
    rut_receptor = db.Column(db.String(16), nullable=True)
    rut_receptor_normalizado = db.Column(db.String(16), nullable=True, index=True)
    razon_social_receptor = db.Column(db.String(255), nullable=True)

    fecha_emision = db.Column(db.Date, nullable=True)
    fecha_vencimiento = db.Column(db.Date, nullable=True)

    neto = db.Column(db.BigInteger, nullable=True)
    exento = db.Column(db.BigInteger, nullable=True)
    iva = db.Column(db.BigInteger, nullable=True)
    total = db.Column(db.BigInteger, nullable=True)

    archivo_nombre = db.Column(db.String(255), nullable=False)
    archivo_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    estado = db.Column(db.String(32), nullable=False, default="procesada")
    estado_asociacion = db.Column(
        db.String(32), nullable=False, default="pendiente", index=True
    )

    validacion_ok = db.Column(db.Boolean, nullable=False, default=False)
    validacion_mensaje = db.Column(db.Text, nullable=True)
    errores_json = db.Column(db.Text, nullable=True)

    importacion = db.relationship("ImportacionFactura", back_populates="facturas")
    detalles = db.relationship(
        "DetalleFactura", back_populates="factura",
        cascade="all, delete-orphan", lazy="selectin"
    )
    asociaciones = db.relationship(
        "AsociacionFacturaPropiedad", back_populates="factura",
        cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "rut_emisor_normalizado", "tipo_documento", "folio",
            name="uq_factura_identidad_tributaria",
        ),
    )

    def _totales_pago(self) -> tuple[int, int, str]:
        from app.modules.conciliacion.models import AplicacionPago
        from sqlalchemy import func

        result = (
            db.session.query(func.coalesce(func.sum(AplicacionPago.monto_aplicado), 0))
            .filter(
                AplicacionPago.factura_id == self.id,
                AplicacionPago.activa.is_(True),
            )
            .scalar()
        )
        total_pagado = int(result or 0)
        total = int(self.total or 0)
        saldo = max(0, total - total_pagado)

        if self.estado != "procesada":
            return total_pagado, saldo, "requiere_revision"
        if total_pagado == 0:
            return total_pagado, saldo, "pendiente"
        if saldo == 0:
            return total_pagado, saldo, "pagada"
        return total_pagado, saldo, "parcial"

    def to_dict(self, include_detalles: bool = False, include_asociaciones: bool = False) -> dict:
        total_pagado, saldo, estado_pago = self._totales_pago()
        data = {
            "id": self.id,
            "tipo_documento": self.tipo_documento,
            "folio": self.folio,
            "rut_emisor": self.rut_emisor,
            "razon_social_emisor": self.razon_social_emisor,
            "rut_receptor": self.rut_receptor,
            "razon_social_receptor": self.razon_social_receptor,
            "fecha_emision": self.fecha_emision.isoformat() if self.fecha_emision else None,
            "fecha_vencimiento": self.fecha_vencimiento.isoformat() if self.fecha_vencimiento else None,
            "neto": self.neto,
            "exento": self.exento,
            "iva": self.iva,
            "total": self.total,
            "total_pagado": total_pagado,
            "saldo_pendiente": saldo,
            "estado_pago": estado_pago,
            "archivo_nombre": self.archivo_nombre,
            "estado": self.estado,
            "estado_asociacion": self.estado_asociacion,
            "validacion_ok": self.validacion_ok,
            "validacion_mensaje": self.validacion_mensaje,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_detalles:
            data["detalles"] = [d.to_dict() for d in self.detalles]
        if include_asociaciones:
            data["asociaciones"] = [a.to_dict() for a in self.asociaciones]
        return data