"""Servicio de asociaciones manuales y correcciones."""
import json
from dataclasses import dataclass, field

from app.modules.conciliacion.repositories.asociacion_repository import (
    AsociacionRepository,
)
from app.modules.conciliacion.utils.normalization import normalize_text


@dataclass
class AsociacionResult:
    ok: bool = False
    movimiento_id: str | None = None
    estado: str | None = None
    asociacion_id: str | None = None
    errores: list[str] = field(default_factory=list)


class AsociacionService:
    def __init__(self, repo: AsociacionRepository | None = None) -> None:
        self.repo = repo or AsociacionRepository()

    def asociar(
        self,
        movimiento_id: str,
        arrendatario_id: str,
        propiedades: list[dict],
        accion: str = "crear",
    ) -> AsociacionResult:
        """
        propiedades: [{ "propiedad_id": "...", "conceptos": ["Arriendo", "GGCC"] }]
        accion: "crear" (default) o "corregir"
        """
        result = AsociacionResult(movimiento_id=movimiento_id)
        mov = self.repo.get_movimiento(movimiento_id)
        if mov is None:
            result.errores.append("Movimiento no encontrado.")
            return result
        if not propiedades:
            result.errores.append("Debe seleccionar al menos una propiedad.")
            return result

        arr = self.repo.get_arrendatario(arrendatario_id)
        if arr is None:
            result.errores.append("Arrendatario no encontrado.")
            return result

        estado_previo = mov.estado
        snapshot_previo = [
            a.to_dict() for a in self.repo.asociaciones_de_movimiento(movimiento_id)
        ]

        depositante_norm = normalize_text(mov.depositante_original or "")
        if not depositante_norm:
            result.errores.append("El movimiento no tiene depositante identificable.")
            return result

        try:
            # Limpiar asociaciones previas de este movimiento
            self.repo.delete_asociaciones_de_movimiento(movimiento_id)

            # Asegurar asociación maestra (depositante ↔ arrendatario)
            asoc_master = self.repo.get_or_create_asociacion(
                depositante_original=mov.depositante_original or "",
                depositante_norm=depositante_norm,
                arrendatario_id=arrendatario_id,
            )

            for item in propiedades:
                prop_id = item.get("propiedad_id")
                conceptos = item.get("conceptos", []) or []
                prop = self.repo.get_propiedad(prop_id)
                if prop is None:
                    result.errores.append(f"Propiedad {prop_id} no encontrada.")
                    continue
                self.repo.create_asociacion_movimiento(
                    movimiento_id=movimiento_id,
                    asociacion_id=asoc_master.id,
                    propiedad_id=prop_id,
                    conceptos=conceptos,
                    estado="manual",
                )

            if result.errores:
                self.repo.rollback()
                return result

            self.repo.set_estado_movimiento(mov, "asociado_manual")

            detalle = {
                "estado_previo": estado_previo,
                "arrendatario_id": arrendatario_id,
                "propiedades": propiedades,
                "asociaciones_previas": snapshot_previo,
            }
            self.repo.add_historial(
                movimiento_id=movimiento_id,
                accion=accion,
                detalle_json=json.dumps(detalle, ensure_ascii=False),
            )

            self.repo.commit()
            result.ok = True
            result.estado = "asociado_manual"
            result.asociacion_id = asoc_master.id
            return result
        except Exception as exc:
            self.repo.rollback()
            result.errores.append(f"Error inesperado: {exc}")
            return result

    def desasociar(self, movimiento_id: str) -> AsociacionResult:
        result = AsociacionResult(movimiento_id=movimiento_id)
        mov = self.repo.get_movimiento(movimiento_id)
        if mov is None:
            result.errores.append("Movimiento no encontrado.")
            return result

        try:
            snapshot = [
                a.to_dict() for a in self.repo.asociaciones_de_movimiento(movimiento_id)
            ]
            self.repo.delete_asociaciones_de_movimiento(movimiento_id)
            self.repo.set_estado_movimiento(mov, "pendiente")
            self.repo.add_historial(
                movimiento_id=movimiento_id,
                accion="desasociar",
                detalle_json=json.dumps(
                    {"asociaciones_eliminadas": snapshot}, ensure_ascii=False
                ),
            )
            self.repo.commit()
            result.ok = True
            result.estado = "pendiente"
            return result
        except Exception as exc:
            self.repo.rollback()
            result.errores.append(f"Error inesperado: {exc}")
            return result