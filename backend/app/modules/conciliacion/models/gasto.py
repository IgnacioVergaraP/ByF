"""Movimientos de egreso, documentos y reglas de clasificación de gastos."""
from app.core.database import db
from .base import BaseModel


class GastoEgreso(BaseModel):
    __tablename__ = "gastos_egresos"

    cartola_id = db.Column(
        db.String(36), db.ForeignKey("cartolas.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    centro_costo_id = db.Column(
        db.String(36), db.ForeignKey("centros_costo.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    fecha = db.Column(db.Date, nullable=False, index=True)
    descripcion_original = db.Column(db.Text, nullable=False)
    descripcion_normalizada = db.Column(db.String(512), nullable=False, index=True)
    beneficiario = db.Column(db.String(255), nullable=True)
    monto = db.Column(db.BigInteger, nullable=False)
    pagina_origen = db.Column(db.Integer, nullable=False)
    orden_en_pagina = db.Column(db.Integer, nullable=False)
    huella_movimiento = db.Column(db.String(64), nullable=False)
    tipo_gasto = db.Column(db.String(16), nullable=True)
    categoria = db.Column(db.String(100), nullable=True)
    subcategoria = db.Column(db.String(255), nullable=True)
    clasificacion_origen = db.Column(db.String(16), nullable=False, default="manual")
    regla_id = db.Column(
        db.String(36), db.ForeignKey("gasto_reglas.id", ondelete="SET NULL"),
        nullable=True,
    )
    sugerencia_tipo = db.Column(db.String(16), nullable=True)
    sugerencia_categoria = db.Column(db.String(100), nullable=True)
    sugerencia_subcategoria = db.Column(db.String(255), nullable=True)
    sugerencia_regla_id = db.Column(
        db.String(36), db.ForeignKey("gasto_reglas.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        db.UniqueConstraint("cartola_id", "huella_movimiento", name="uq_gasto_cartola_huella"),
    )


class GastoDocumento(BaseModel):
    __tablename__ = "gastos_documentos"

    centro_costo_id = db.Column(
        db.String(36), db.ForeignKey("centros_costo.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    archivo_nombre = db.Column(db.String(255), nullable=False)
    archivo_hash = db.Column(db.String(64), nullable=False, index=True)
    content_type = db.Column(db.String(120), nullable=False)
    contenido = db.Column(db.LargeBinary, nullable=False)
    fecha_documento = db.Column(db.Date, nullable=True, index=True)
    monto = db.Column(db.BigInteger, nullable=True, index=True)
    __table_args__ = (
        db.UniqueConstraint(
            "centro_costo_id", "archivo_hash",
            name="uq_gasto_documento_entidad_hash",
        ),
    )


class GastoAsociacion(BaseModel):
    __tablename__ = "gastos_asociaciones"

    egreso_id = db.Column(
        db.String(36), db.ForeignKey("gastos_egresos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    documento_id = db.Column(
        db.String(36), db.ForeignKey("gastos_documentos.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    estado = db.Column(db.String(16), nullable=False, default="sugerida")
    __table_args__ = (
        db.UniqueConstraint("egreso_id", "documento_id", name="uq_gasto_asociacion"),
    )


class GastoRegla(BaseModel):
    __tablename__ = "gasto_reglas"

    centro_costo_id = db.Column(
        db.String(36), db.ForeignKey("centros_costo.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    campo = db.Column(db.String(32), nullable=False, default="descripcion")
    valor_normalizado = db.Column(db.String(512), nullable=False)
    tipo_gasto = db.Column(db.String(16), nullable=False)
    categoria = db.Column(db.String(100), nullable=True)
    subcategoria = db.Column(db.String(255), nullable=True)
    __table_args__ = (
        db.UniqueConstraint(
            "centro_costo_id", "campo", "valor_normalizado",
            name="uq_gasto_regla_entidad_valor",
        ),
    )


class GastoExcel(BaseModel):
    __tablename__ = "gastos_excels"

    centro_costo_id = db.Column(db.String(36), db.ForeignKey("centros_costo.id"), nullable=False)
    archivo_nombre = db.Column(db.String(255), nullable=False)
    archivo_hash = db.Column(db.String(64), nullable=False)
    contenido = db.Column(db.LargeBinary, nullable=False)
    __table_args__ = (db.UniqueConstraint("centro_costo_id", "archivo_hash"),)


class GastoExcelFila(BaseModel):
    __tablename__ = "gastos_excel_filas"

    documento_id = db.Column(db.String(36), db.ForeignKey("gastos_documentos.id", ondelete="CASCADE"), nullable=False, unique=True)
    excel_id = db.Column(db.String(36), db.ForeignKey("gastos_excels.id"), nullable=False, index=True)
    hoja = db.Column(db.String(255), nullable=False)
    fila = db.Column(db.Integer, nullable=False)
    destinatario = db.Column(db.Text, nullable=False)
    observacion = db.Column(db.Text, nullable=False)
    rut = db.Column(db.String(32), nullable=False)
