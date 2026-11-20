"""Servicio de asociación de facturas con arrendatarios y propiedades."""
import json
from dataclasses import dataclass, field

from app.modules.conciliacion.repositories.factura_asociacion_repository import (
    FacturaAsociacionRepository,
)
from app.modules.conciliacion.utils.similitud import (
    similitud_codigo_propiedad, similitud_razon_social,
)


@dataclass
class SugerenciaArrendatario:
    arrendatario_id: str
    nombre: str
    score: float
    propiedades: list[dict] = field(default_factory=list)


@dataclass
class SugerenciasResult:
    factura_id: str
    rut_receptor: str | None
    razon_social_receptor: str | None
    identidad_aprendida: dict | None = None
    sugerencias: list[SugerenciaArrendatario] = field(default_factory=list)
    codigos_detectados: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


@dataclass
class AsociarResult:
    ok: bool = False
    factura_id: str | None = None
    estado_asociacion: str | None = None
    errores: list[str] = field(default_factory=list)


class FacturaAsociacionService:
    def __init__(self, repo: FacturaAsociacionRepository | None = None) -> None:
        self.repo = repo or FacturaAsociacionRepository()

    # ---------- Códigos de línea ----------
    @staticmethod
    def _codigos_de_factura(factura) -> list[str]:
        codigos = []
        for det in factura.detalles:
            if det.codigo:
                codigos.append(det.codigo)
        return codigos

    # ---------- Sugerencias ----------
    def sugerir(self, factura_id: str) -> SugerenciasResult:
        res = SugerenciasResult(factura_id=factura_id, rut_receptor=None, razon_social_receptor=None)
        factura = self.repo.get_factura(factura_id)
        if factura is None:
            res.errores.append("Factura no encontrada.")
            return res

        res.rut_receptor = factura.rut_receptor_normalizado
        res.razon_social_receptor = factura.razon_social_receptor
        res.codigos_detectados = self._codigos_de_factura(factura)

        # 1. Identidad aprendida
        if factura.rut_receptor_normalizado:
            ident = self.repo.get_identidad(factura.rut_receptor_normalizado)
            if ident:
                arr = self.repo.get_arrendatario(ident.arrendatario_id)
                if arr:
                    props = self.repo.propiedades_de_arrendatario(arr.id)
                    res.identidad_aprendida = {
                        "arrendatario": arr.to_dict(),
                        "propiedades": [
                            {"id": p.id, "nombre_original": p.nombre_original}
                            for p in props
                        ],
                    }

        # 2. Sugerencias por razón social
        if factura.razon_social_receptor:
            candidatos = self.repo.buscar_arrendatarios_por_nombre(
                factura.razon_social_receptor
            )
            for arr in candidatos:
                score = similitud_razon_social(
                    factura.razon_social_receptor, arr.nombre_original
                )
                if score < 0.4:
                    continue
                props = self.repo.propiedades_de_arrendatario(arr.id)
                # Refinar con códigos de línea
                if res.codigos_detectados:
                    for p in props:
                        if any(
                            similitud_codigo_propiedad(c, p.nombre_original) >= 0.7
                            for c in res.codigos_detectados
                        ):
                            score = min(1.0, score + 0.15)
                res.sugerencias.append(SugerenciaArrendatario(
                    arrendatario_id=arr.id,
                    nombre=arr.nombre_original,
                    score=score,
                    propiedades=[
                        {"id": p.id, "nombre_original": p.nombre_original}
                        for p in props
                    ],
                ))

        res.sugerencias.sort(key=lambda x: x.score, reverse=True)
        return res

    # ---------- Asociación manual ----------
    def asociar(
        self,
        factura_id: str,
        arrendatario_id: str,
        propiedades: list[dict],
        confirmar_identidad: bool = True,
        accion: str = "crear",
    ) -> AsociarResult:
        res = AsociarResult(factura_id=factura_id)
        factura = self.repo.get_factura(factura_id)
        if factura is None:
            res.errores.append("Factura no encontrada.")
            return res
        arr = self.repo.get_arrendatario(arrendatario_id)
        if arr is None:
            res.errores.append("Arrendatario no encontrado.")
            return res
        if not propiedades:
            res.errores.append("Debe seleccionar al menos una propiedad.")
            return res

        snapshot_previo = [a.to_dict() for a in self.repo.asociaciones_de_factura(factura_id)]

        try:
            # Limpiar asociaciones previas
            self.repo.limpiar_asociaciones_factura(factura_id)

            for item in propiedades:
                prop_id = item.get("propiedad_id")
                conceptos = item.get("conceptos", []) or []
                prop = self.repo.get_propiedad(prop_id)
                if prop is None:
                    res.errores.append(f"Propiedad {prop_id} no encontrada.")
                    continue
                cc_id = prop.centro_costo_id
                self.repo.create_asociacion(
                    factura_id=factura_id,
                    propiedad_id=prop_id,
                    centro_costo_id=cc_id,
                    conceptos=conceptos,
                    estado="asociada_manual",
                    metodo="manual",
                )

            if res.errores:
                self.repo.rollback()
                return res

            # Confirmar identidad tributaria (RUT → arrendatario)
            if confirmar_identidad and factura.rut_receptor_normalizado:
                self.repo.upsert_identidad(
                    rut_norm=factura.rut_receptor_normalizado,
                    razon_social=factura.razon_social_receptor,
                    arrendatario_id=arrendatario_id,
                    origen="manual",
                )

            self.repo.set_estado_factura(factura, "asociada_manual")
            detalle = {
                "arrendatario_id": arrendatario_id,
                "propiedades": propiedades,
                "asociaciones_previas": snapshot_previo,
            }
            self.repo.add_historial(
                factura_id=factura_id,
                accion=accion,
                detalle_json=json.dumps(detalle, ensure_ascii=False),
            )
            self.repo.commit()

            res.ok = True
            res.estado_asociacion = "asociada_manual"
            return res
        except Exception as exc:
            self.repo.rollback()
            res.errores.append(f"Error inesperado: {exc}")
            return res

    def desasociar(self, factura_id: str) -> AsociarResult:
        res = AsociarResult(factura_id=factura_id)
        factura = self.repo.get_factura(factura_id)
        if factura is None:
            res.errores.append("Factura no encontrada.")
            return res
        try:
            snapshot = [a.to_dict() for a in self.repo.asociaciones_de_factura(factura_id)]
            self.repo.limpiar_asociaciones_factura(factura_id)
            self.repo.set_estado_factura(factura, "pendiente")
            self.repo.add_historial(
                factura_id=factura_id, accion="quitar",
                detalle_json=json.dumps({"eliminadas": snapshot}, ensure_ascii=False),
            )
            self.repo.commit()
            res.ok = True
            res.estado_asociacion = "pendiente"
            return res
        except Exception as exc:
            self.repo.rollback()
            res.errores.append(f"Error inesperado: {exc}")
            return res

    # ---------- Reconocimiento automático ----------
    def reconocer_factura(self, factura_id: str) -> AsociarResult:
        """Intenta autoasociar solo si es inequívoco y previamente aprendido."""
        res = AsociarResult(factura_id=factura_id)
        factura = self.repo.get_factura(factura_id)
        if factura is None:
            res.errores.append("Factura no encontrada.")
            return res

        # No autoasociar si la factura no está validada documentalmente
        if factura.estado != "procesada":
            return res

        # Requiere RUT aprendido
        if not factura.rut_receptor_normalizado:
            return res
        ident = self.repo.get_identidad(factura.rut_receptor_normalizado)
        if ident is None:
            return res

        # Debe tener una única propiedad asociada al arrendatario
        props = self.repo.propiedades_de_arrendatario(ident.arrendatario_id)
        if len(props) != 1:
            return res

        try:
            self.repo.limpiar_asociaciones_factura(factura_id)
            prop = props[0]
            self.repo.create_asociacion(
                factura_id=factura_id,
                propiedad_id=prop.id,
                centro_costo_id=prop.centro_costo_id,
                conceptos=[],
                estado="asociada_automatica",
                metodo="por_rut_aprendido",
            )
            self.repo.set_estado_factura(factura, "asociada_automatica")
            self.repo.add_historial(
                factura_id=factura_id, accion="reconocer",
                detalle_json=json.dumps({
                    "arrendatario_id": ident.arrendatario_id,
                    "propiedad_id": prop.id,
                    "metodo": "por_rut_aprendido",
                }, ensure_ascii=False),
            )
            self.repo.commit()
            res.ok = True
            res.estado_asociacion = "asociada_automatica"
            return res
        except Exception as exc:
            self.repo.rollback()
            res.errores.append(f"Error inesperado: {exc}")
            return res

    def reconocer_todas(self) -> dict:
        from app.modules.conciliacion.models import Factura
        pendientes = Factura.query.filter_by(estado_asociacion="pendiente").all()
        procesadas = 0
        auto = 0
        for f in pendientes:
            procesadas += 1
            r = self.reconocer_factura(f.id)
            if r.ok:
                auto += 1
        return {"procesadas": procesadas, "asociadas_auto": auto}