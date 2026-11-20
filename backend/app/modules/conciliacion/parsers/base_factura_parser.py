"""Estructuras comunes para parsers de facturas."""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class ParsedDetalle:
    codigo: Optional[str] = None
    descripcion: Optional[str] = None
    cantidad: Optional[float] = None
    unidad: Optional[str] = None
    precio_unitario: Optional[float] = None
    descuento: Optional[int] = None
    total_linea: Optional[int] = None


@dataclass
class ParsedFactura:
    tipo_documento: str = "FACTURA_ELECTRONICA"
    folio: Optional[str] = None
    rut_emisor: Optional[str] = None
    razon_social_emisor: Optional[str] = None
    rut_receptor: Optional[str] = None
    razon_social_receptor: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    neto: Optional[int] = None
    exento: Optional[int] = None
    iva: Optional[int] = None
    total: Optional[int] = None
    detalles: list[ParsedDetalle] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    metodo_extraccion: str = "texto"  # texto | ocr | mixto


class BaseFacturaParser:
    def parse(self, data: bytes, archivo_nombre: str) -> ParsedFactura:
        raise NotImplementedError