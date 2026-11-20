"""Interfaz y estructuras comunes para parsers de cartolas."""
from dataclasses import dataclass, field
from datetime import date
from typing import BinaryIO, Optional


@dataclass
class ParsedMovimiento:
    fecha: date
    descripcion_original: str
    depositante_original: Optional[str]
    monto: int
    pagina_origen: int
    orden_en_pagina: int


@dataclass
class ParsedCartola:
    banco: str
    numero_cuenta: str
    numero_cartola: Optional[str]
    periodo_desde: Optional[date]
    periodo_hasta: Optional[date]
    total_abonos_informado: Optional[int]
    total_cargos_informado: Optional[int]
    saldo_inicial_informado: Optional[int]
    saldo_final_informado: Optional[int]
    movimientos: list[ParsedMovimiento] = field(default_factory=list)
    cargos: list[ParsedMovimiento] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class BaseCartolaParser:
    """Interfaz base para parsers de cartolas bancarias."""

    def parse(self, file_stream: BinaryIO) -> ParsedCartola:
        raise NotImplementedError