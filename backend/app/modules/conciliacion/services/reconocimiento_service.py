"""Servicio de reconocimiento automático de depositantes."""
import json
from dataclasses import dataclass, field

from app.modules.conciliacion.models import (
    AsociacionMovimiento,
    MovimientoBancario,
    PropiedadArrendatario,
)
from app.modules.conciliacion.repositories.asociacion_repository import (
    AsociacionRepository,
)
from app.modules.conciliacion.utils.normalization import normalize_text


@dataclass
class ReconocimientoResult:
    procesados: int = 0
    automaticos: int = 0
    pendientes: int = 0
    errores: list[str] = field(default_factory=list)


class ReconocimientoService:
    def __init__(self, repo: AsociacionRepository | None = None) -> None:
        self.repo = repo or AsociacionRepository()

    def reconocer_pendientes(self) -> ReconocimientoResult:
        """Recorre todos los movimientos pendientes y aplica reconocimiento."""
        result = ReconocimientoResult()
        pendientes = MovimientoBancario.query.filter_by(estado="pendiente").all()

        try:
            for mov in pendientes:
                result.procesados += 1
                if self._reconocer_movimiento(mov):
                    result.automaticos += 1
                else:
                    result.pendientes += 1
            self.repo.commit()
        except Exception as exc:
            self.repo.rollback()
            result.errores.append(f"Error en reconocimiento: {exc}")
        return result

    def _reconocer_movimiento(self, mov: MovimientoBancario) -> bool:
        depositante_norm = (mov.depositante_normalizado or "").strip()
        if not depositante_norm:
            return False

        asociaciones = self.repo.list_asociaciones_por_depositante(
            depositante_norm, solo_vigentes=True
        )
        if len(asociaciones) != 1:
            # 0: desconocido. >1: ambiguo.
            return False

        asoc = asociaciones[0]
        # Propiedades que el maestro le asigna al arrendatario
        propiedades = self.repo.propiedades_de_arrendatario(asoc.arrendatario_id)
        if len(propiedades) != 1:
            # 0: no podemos determinar dónde va. >1: ambiguo.
            return False

        prop = propiedades[0]

        # Crear vínculo
        self.repo.create_asociacion_movimiento(
            movimiento_id=mov.id,
            asociacion_id=asoc.id,
            propiedad_id=prop.id,
            conceptos=[],
            estado="automatico",
        )
        self.repo.set_estado_movimiento(mov, "asociado_automatico")
        self.repo.add_historial(
            movimiento_id=mov.id,
            accion="crear",
            detalle_json=json.dumps({
                "automatico": True,
                "arrendatario_id": asoc.arrendatario_id,
                "propiedad_id": prop.id,
            }, ensure_ascii=False),
        )
        return True