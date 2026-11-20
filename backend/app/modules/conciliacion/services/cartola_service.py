"""Servicio de procesamiento de cartolas PDF."""
import hashlib
import io
from dataclasses import dataclass, field
from typing import BinaryIO

from app.modules.conciliacion.parsers import BancoChileParser, ParsedCartola
from app.modules.conciliacion.repositories.cartola_repository import CartolaRepository
from app.modules.conciliacion.repositories.movimiento_repository import MovimientoRepository
from app.modules.conciliacion.services.reconocimiento_service import ReconocimientoService
from app.modules.conciliacion.utils.normalization import normalize_text


@dataclass
class CartolaImportResult:
    cartola_id: str | None = None
    duplicada: bool = False
    cantidad_movimientos: int = 0
    cantidad_cargos: int = 0
    total_abonos_extraido: int = 0
    total_abonos_informado: int | None = None
    validacion_ok: bool = False
    validacion_mensaje: str | None = None
    errores: list[str] = field(default_factory=list)


class CartolaService:
    def __init__(
        self,
        cartola_repo: CartolaRepository | None = None,
        mov_repo: MovimientoRepository | None = None,
    ) -> None:
        self.cartola_repo = cartola_repo or CartolaRepository()
        self.mov_repo = mov_repo or MovimientoRepository()

    def _hash(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _huella(self, fecha, pagina: int, orden: int, descripcion: str, monto: int) -> str:
        raw = f"{fecha}|{pagina}|{orden}|{descripcion}|{monto}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _resolver_numero_cuenta(self, parsed: ParsedCartola) -> str:
        numero = (parsed.numero_cuenta or "").strip()
        if numero:
            return numero
        return f"{parsed.banco}-SIN-NUMERO"

    def import_pdf(
        self,
        file_stream: BinaryIO,
        archivo_nombre: str,
        centro_costo_id: str,
    ) -> CartolaImportResult:
        result = CartolaImportResult()

        if not centro_costo_id:
            result.errores.append("Falta seleccionar un centro de costo.")
            return result

        from app.modules.conciliacion.models import CentroCosto
        cc = CentroCosto.query.filter_by(id=centro_costo_id).first()
        if cc is None:
            result.errores.append(f"Centro de costo '{centro_costo_id}' no encontrado.")
            return result

        data = file_stream.read()
        archivo_hash = self._hash(data)

        existente = self.cartola_repo.get_cartola_por_hash(archivo_hash)
        if existente is not None:
            result.cartola_id = existente.id
            result.duplicada = True
            result.cantidad_movimientos = existente.cantidad_movimientos
            result.total_abonos_extraido = existente.total_abonos_extraido or 0
            result.total_abonos_informado = existente.total_abonos_informado
            result.validacion_ok = existente.validacion_ok
            result.validacion_mensaje = existente.validacion_mensaje
            from app.modules.conciliacion.models import GastoEgreso
            result.cantidad_cargos = GastoEgreso.query.filter_by(
                cartola_id=existente.id
            ).count()
            if result.cantidad_cargos == 0:
                parsed_existente = BancoChileParser().parse(io.BytesIO(data))
                if parsed_existente.errores:
                    result.errores.extend(parsed_existente.errores)
                    return result
                from app.modules.conciliacion.services.gastos_service import GastosService
                result.cantidad_cargos = GastosService().crear_cargos(
                    existente.id, existente.centro_costo_id, parsed_existente.cargos
                )
                self.cartola_repo.commit()
            return result

        parser = BancoChileParser()
        parsed: ParsedCartola = parser.parse(io.BytesIO(data))

        if parsed.errores:
            result.errores.extend(parsed.errores)
            return result

        if not parsed.movimientos and not parsed.cargos:
            result.errores.append("La cartola no contiene abonos ni cargos.")
            return result

        numero_cuenta = self._resolver_numero_cuenta(parsed)
        cuenta = self.cartola_repo.get_cuenta_por_numero(numero_cuenta)
        if cuenta is None:
            cuenta = self.cartola_repo.create_cuenta(
                banco=parsed.banco, numero=numero_cuenta
            )

        total_extraido = sum(m.monto for m in parsed.movimientos)
        result.total_abonos_extraido = total_extraido
        result.total_abonos_informado = parsed.total_abonos_informado

        if parsed.total_abonos_informado is not None:
            if total_extraido == parsed.total_abonos_informado:
                result.validacion_ok = True
                result.validacion_mensaje = "Suma de abonos coincide con el total informado."
            else:
                result.validacion_ok = False
                result.validacion_mensaje = (
                    f"Diferencia: extraído ${total_extraido:,} vs "
                    f"informado ${parsed.total_abonos_informado:,}"
                )
        else:
            result.validacion_ok = False
            result.validacion_mensaje = "No se encontró total de abonos informado en el PDF."

        cartola = self.cartola_repo.create_cartola(
            cuenta_id=cuenta.id,
            centro_costo_id=cc.id,
            numero_cartola=parsed.numero_cartola,
            periodo_desde=parsed.periodo_desde,
            periodo_hasta=parsed.periodo_hasta,
            archivo_nombre=archivo_nombre,
            archivo_hash=archivo_hash,
            total_abonos_informado=parsed.total_abonos_informado,
            total_cargos_informado=parsed.total_cargos_informado,
            saldo_inicial_informado=parsed.saldo_inicial_informado,
            saldo_final_informado=parsed.saldo_final_informado,
            total_abonos_extraido=total_extraido,
            cantidad_movimientos=len(parsed.movimientos),
            validacion_ok=result.validacion_ok,
            validacion_mensaje=result.validacion_mensaje,
        )

        for mov in parsed.movimientos:
            huella = self._huella(
                mov.fecha, mov.pagina_origen, mov.orden_en_pagina,
                mov.descripcion_original, mov.monto,
            )
            depositante_norm = (
                normalize_text(mov.depositante_original)
                if mov.depositante_original else None
            )
            self.mov_repo.create_movimiento(
                cartola_id=cartola.id,
                centro_costo_id=cc.id,
                fecha=mov.fecha,
                descripcion_original=mov.descripcion_original,
                depositante_original=mov.depositante_original,
                depositante_normalizado=depositante_norm,
                monto=mov.monto,
                pagina_origen=mov.pagina_origen,
                orden_en_pagina=mov.orden_en_pagina,
                huella_movimiento=huella,
                estado="pendiente",
            )

        from app.modules.conciliacion.services.gastos_service import GastosService
        result.cantidad_cargos = GastosService().crear_cargos(
            cartola.id, cc.id, parsed.cargos
        )

        self.cartola_repo.commit()
        result.cartola_id = cartola.id
        result.cantidad_movimientos = len(parsed.movimientos)

        try:
            ReconocimientoService().reconocer_pendientes()
        except Exception:
            pass
        try:
            from app.modules.conciliacion.services.conciliacion_service import (
                ConciliacionService,
            )
            ConciliacionService().reconocer_todos()
        except Exception:
            pass

        return result