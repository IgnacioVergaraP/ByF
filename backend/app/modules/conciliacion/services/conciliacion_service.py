"""Servicio de conciliación: aplicación manual y sugerencias."""
import json
from dataclasses import dataclass, field
from datetime import date

from app.core.database import db
from app.modules.conciliacion.models import Factura
from app.modules.conciliacion.repositories.aplicacion_pago_repository import (
    AplicacionPagoRepository,
)
from app.modules.conciliacion.services.aprendizaje_service import (
    AprendizajeService, CadenaDescubierta,
)
from app.modules.conciliacion.services.motor_combinaciones import (
    MotorCombinaciones, MotorResult,
)
from app.modules.conciliacion.utils.idempotencia import generar_llave


@dataclass
class AplicarResult:
    ok: bool = False
    aplicacion_id: str | None = None
    idempotente: bool = False
    errores: list[str] = field(default_factory=list)
    excedente: dict | None = None


@dataclass
class RevertirResult:
    ok: bool = False
    aplicacion_id: str | None = None
    errores: list[str] = field(default_factory=list)


class ConciliacionService:
    def __init__(self, repo: AplicacionPagoRepository | None = None) -> None:
        self.repo = repo or AplicacionPagoRepository()
        self.aprendizaje = AprendizajeService()

    # ---------- Aplicar ----------
    def aplicar_pago(
        self, movimiento_id: str, factura_id: str, monto_aplicado: int,
        metodo: str = "manual", responsable: str | None = None,
        llave_idempotencia: str | None = None,
    ) -> AplicarResult:
        res = AplicarResult()
        if monto_aplicado is None or monto_aplicado <= 0:
            res.errores.append("El monto debe ser un entero positivo.")
            return res

        llave = (llave_idempotencia or "").strip() or generar_llave()
        existente = self.repo.get_por_llave(llave)
        if existente is not None:
            res.ok = True
            res.aplicacion_id = existente.id
            res.idempotente = True
            res.excedente = self._calcular_excedente(
                movimiento_id, factura_actual_id=factura_id
            )
            return res

        try:
            mov = self.repo.get_movimiento(movimiento_id)
            factura = self.repo.get_factura(factura_id)
            if mov is None:
                res.errores.append("Movimiento no encontrado.")
                return res
            if factura is None:
                res.errores.append("Factura no encontrada.")
                return res
            if factura.estado != "procesada":
                res.errores.append(f"Factura en estado '{factura.estado}', no admite pagos.")
                return res

            disponible = int(mov.monto) - self.repo.total_aplicado_movimiento(movimiento_id)
            if monto_aplicado > disponible:
                res.errores.append(f"El monto excede el disponible del movimiento (${disponible:,}).")
                return res

            saldo = int(factura.total or 0) - self.repo.total_pagado_factura(factura_id)
            if monto_aplicado > saldo:
                res.errores.append(f"El monto excede el saldo pendiente de la factura (${saldo:,}).")
                return res

            ap = self.repo.create_aplicacion(
                movimiento_id=movimiento_id, factura_id=factura_id,
                monto_aplicado=int(monto_aplicado), metodo=metodo, activa=True,
                fecha_aplicacion=date.today(), responsable=responsable,
                llave_idempotencia=llave,
            )
            self.repo.add_historial(
                aplicacion_id=ap.id, accion="crear",
                detalle_json=json.dumps({
                    "movimiento_id": movimiento_id, "factura_id": factura_id,
                    "monto": int(monto_aplicado), "metodo": metodo,
                }, ensure_ascii=False),
                responsable=responsable,
            )
            # Calcular antes del commit: si falla, el pago también se revierte.
            excedente = self._calcular_excedente(
                movimiento_id, factura_actual_id=factura_id
            )
            self.repo.commit()
            res.ok = True
            res.aplicacion_id = ap.id
            res.excedente = excedente
            return res
        except Exception as exc:
            self.repo.rollback()
            res.errores.append(f"Error inesperado: {exc}")
            return res

    # ---------- Revertir ----------
    def revertir(self, aplicacion_id: str, responsable: str | None = None) -> RevertirResult:
        res = RevertirResult(aplicacion_id=aplicacion_id)
        try:
            ap = self.repo.get_aplicacion(aplicacion_id)
            if ap is None:
                res.errores.append("Aplicación no encontrada.")
                return res
            if not ap.activa:
                res.errores.append("La aplicación ya está revertida.")
                return res
            snapshot = ap.to_dict()
            ap.activa = False
            db.session.flush()
            self.repo.add_historial(
                aplicacion_id=ap.id, accion="revertir",
                detalle_json=json.dumps(snapshot, ensure_ascii=False),
                responsable=responsable,
            )
            self.repo.commit()
            res.ok = True
            return res
        except Exception as exc:
            self.repo.rollback()
            res.errores.append(f"Error inesperado: {exc}")
            return res

    # ---------- Sugerencias ----------
    def sugerencias_para_movimiento(self, movimiento_id: str) -> list[dict]:
        cadenas = self.aprendizaje.descubrir_cadenas_para_movimiento(movimiento_id)
        return [self._cadena_a_dict(c) for c in cadenas]

    def sugerencias_para_factura(self, factura_id: str) -> list[dict]:
        cadenas = self.aprendizaje.descubrir_cadenas_para_factura(factura_id)
        return [self._cadena_a_dict(c) for c in cadenas]

    @staticmethod
    def _cadena_a_dict(c: CadenaDescubierta) -> dict:
        return {
            "movimiento_id": c.movimiento_id,
            "arrendatario_id": c.arrendatario_id,
            "arrendatario_nombre": c.arrendatario_nombre,
            "propiedad_id": c.propiedad_id,
            "propiedad_nombre": c.propiedad_nombre,
            "factura_id": c.factura_id,
            "factura_folio": c.factura_folio,
            "factura_saldo": c.factura_saldo,
            "monto_disponible": c.monto_disponible,
            "score": c.score_total,
            "motivo": c.motivo,
        }

    # ---------- Reconocimiento ----------
    def reconocer_todos(self) -> MotorResult:
        return MotorCombinaciones().reconocer_todos()

    # ---------- Excedente ----------
    def _calcular_excedente(
        self, movimiento_id: str, factura_actual_id: str,
    ) -> dict | None:
        mov = self.repo.get_movimiento(movimiento_id)
        if mov is None:
            return None
        disponible = int(mov.monto) - self.repo.total_aplicado_movimiento(movimiento_id)
        if disponible <= 0:
            return None

        factura_actual = self.repo.get_factura(factura_actual_id)
        if factura_actual is None:
            return None

        # El RUT de la factura identifica al receptor incluso cuando el depósito
        # se eligió manualmente y aún no existe una asociación aprendida.
        facturas_candidatas = []
        rut = factura_actual.rut_receptor_normalizado
        if rut:
            candidatas = Factura.query.filter(
                Factura.estado == "procesada",
                Factura.rut_receptor_normalizado == rut,
                Factura.id != factura_actual_id,
            ).order_by(Factura.fecha_emision, Factura.id).all()
            for factura in candidatas:
                saldo = int(factura.total or 0) - self.repo.total_pagado_factura(factura.id)
                if saldo <= 0:
                    continue
                facturas_candidatas.append({
                    "factura_id": factura.id,
                    "folio": factura.folio,
                    "saldo_pendiente": saldo,
                    "razon_social_receptor": factura.razon_social_receptor,
                })

        return {
            "movimiento_id": movimiento_id,
            "monto_disponible": disponible,
            "facturas_candidatas": facturas_candidatas,
        }
