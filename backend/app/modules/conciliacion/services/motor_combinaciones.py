"""Motor de combinaciones para conciliación automática.

Estrategia:
  Fase 1: match exacto 1 depósito → 1 factura.
  Fase 2: combinaciones (2×1, 1×2, 3×1, 1×3, 4×1, 1×4, 2×2).
  Solo aplica combinaciones únicas.
  Desempate por fecha: prioriza el depósito más reciente.
  Idempotente: no crea aplicaciones duplicadas.
"""
import hashlib
import itertools
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy import func

from app.core.database import db
from app.modules.conciliacion.models import (
    AplicacionPago,
    Arrendatario,
    AsociacionDepositante,
    AsociacionFacturaPropiedad,
    Factura,
    IdentidadTributaria,
    MovimientoBancario,
    Propiedad,
    PropiedadArrendatario,
)


MAX_PIEZAS = 4


@dataclass
class AplicacionCreada:
    movimiento_ids: list[str]
    factura_ids: list[str]
    monto: int
    motivo: str


@dataclass
class MotorResult:
    grupos_procesados: int = 0
    aplicaciones_creadas: int = 0
    errores: list[str] = field(default_factory=list)
    detalle: list[dict] = field(default_factory=list)


class MotorCombinaciones:
    def reconocer_todos(self) -> MotorResult:
        res = MotorResult()

        # 0. Inferir propiedades para facturas que tengan identidad
        #    tributaria pero no AsociacionFacturaPropiedad.
        try:
            from app.modules.conciliacion.services.aprendizaje_service import (
                AprendizajeService,
            )
            svc = AprendizajeService()
            for f in Factura.query.filter(Factura.estado == "procesada").all():
                try:
                    svc.inferir_propiedad_para_factura(f.id)
                except Exception:
                    pass
            db.session.commit()
        except Exception:
            db.session.rollback()

        # 1. Agrupar por arrendatario
        try:
            grupos = self._agrupar_por_arrendatario()
        except Exception as exc:
            res.errores.append(f"Error agrupando: {exc}")
            return res

        res.grupos_procesados = len(grupos)

        for arr_id, data in grupos.items():
            try:
                creadas = self._procesar_grupo(arr_id, data)
                res.aplicaciones_creadas += len(creadas)
                for c in creadas:
                    res.detalle.append({
                        "arrendatario_id": arr_id,
                        "movimientos": c.movimiento_ids,
                        "facturas": c.factura_ids,
                        "monto": c.monto,
                        "motivo": c.motivo,
                    })
            except Exception as exc:
                db.session.rollback()
                res.errores.append(f"Grupo {arr_id}: {exc}")

        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            res.errores.append(f"Error al commit: {exc}")
        return res

    # ---------- Agrupación ----------
    def _agrupar_por_arrendatario(self) -> dict[str, dict]:
        grupos: dict[str, dict] = {}

        # Depósitos con disponible, por arrendatario aprendido
        movs = MovimientoBancario.query.all()
        for m in movs:
            disponible = int(m.monto) - self._total_aplicado_mov(m.id)
            if disponible <= 0 or not m.depositante_normalizado:
                continue
            arrs = AsociacionDepositante.query.filter_by(
                depositante_normalizado=m.depositante_normalizado, vigente=True
            ).all()
            for a in arrs:
                grupos.setdefault(a.arrendatario_id, {"movs": [], "facturas": []})
                if m not in grupos[a.arrendatario_id]["movs"]:
                    grupos[a.arrendatario_id]["movs"].append(m)

        # Facturas con saldo, por arrendatario de la identidad o de la propiedad
        facturas = Factura.query.filter_by(estado="procesada").all()
        for f in facturas:
            saldo = int(f.total or 0) - self._total_pagado_factura(f.id)
            if saldo <= 0:
                continue
            arrs = set()
            if f.rut_receptor_normalizado:
                ident = IdentidadTributaria.query.filter_by(
                    rut_receptor_normalizado=f.rut_receptor_normalizado, vigente=True
                ).first()
                if ident:
                    arrs.add(ident.arrendatario_id)
            for asoc in AsociacionFacturaPropiedad.query.filter_by(factura_id=f.id).all():
                prop = asoc.propiedad
                if prop:
                    for pa in prop.arrendatarios:
                        arrs.add(pa.arrendatario_id)
            for arr_id in arrs:
                grupos.setdefault(arr_id, {"movs": [], "facturas": []})
                if f not in grupos[arr_id]["facturas"]:
                    grupos[arr_id]["facturas"].append(f)

        return grupos

    # ---------- Procesamiento por grupo ----------
    def _procesar_grupo(self, arr_id: str, data: dict) -> list[AplicacionCreada]:
        movs = data["movs"]
        facturas = data["facturas"]
        if not movs or not facturas:
            return []

        mov_disponibles = [
            (m.id, int(m.monto) - self._total_aplicado_mov(m.id), m.fecha)
            for m in movs
        ]
        fac_saldos = [
            (f.id, int(f.total or 0) - self._total_pagado_factura(f.id), f.fecha_emision)
            for f in facturas
        ]

        aplicadas: list[AplicacionCreada] = []
        aplicadas += self._fase_exacta(mov_disponibles, fac_saldos)
        aplicadas += self._fase_combinaciones(mov_disponibles, fac_saldos, aplicadas)
        return aplicadas

    # ---------- Fase 1: match exacto ----------
    def _fase_exacta(
        self,
        movs: list[tuple[str, int, date | None]],
        facturas: list[tuple[str, int, date | None]],
    ) -> list[AplicacionCreada]:
        aplicadas: list[AplicacionCreada] = []
        usados_mov: set[str] = set()
        usadas_fac: set[str] = set()

        for f_id, f_saldo, f_fecha in facturas:
            if f_id in usadas_fac:
                continue
            matches = [
                (m_id, m_disponible, m_fecha)
                for m_id, m_disponible, m_fecha in movs
                if m_id not in usados_mov and m_disponible == f_saldo
            ]
            if not matches:
                continue
            matches.sort(key=lambda x: x[2] or date.min, reverse=True)
            m_id, m_disponible, _ = matches[0]

            # Skip si ya existe una aplicación activa para (mov, factura)
            ya = AplicacionPago.query.filter_by(
                movimiento_id=m_id, factura_id=f_id, activa=True
            ).first()
            if ya is not None:
                usados_mov.add(m_id)
                usadas_fac.add(f_id)
                continue

            try:
                self._aplicar(m_id, f_id, f_saldo, "exacto")
                usados_mov.add(m_id)
                usadas_fac.add(f_id)
                aplicadas.append(AplicacionCreada(
                    movimiento_ids=[m_id],
                    factura_ids=[f_id],
                    monto=f_saldo,
                    motivo="match exacto",
                ))
            except Exception:
                db.session.rollback()
                continue
        return aplicadas

    # ---------- Fase 2: combinaciones ----------
    def _fase_combinaciones(
        self,
        movs: list[tuple[str, int, date | None]],
        facturas: list[tuple[str, int, date | None]],
        aplicadas: list[AplicacionCreada],
    ) -> list[AplicacionCreada]:
        usados_mov = {mid for a in aplicadas for mid in a.movimiento_ids}
        usadas_fac = {fid for a in aplicadas for fid in a.factura_ids}
        movs_disp = [(m, d, f) for m, d, f in movs if m not in usados_mov and d > 0]
        fac_saldos = [(f, s, fe) for f, s, fe in facturas if f not in usadas_fac and s > 0]

        nuevas: list[AplicacionCreada] = []
        patrones = [
            (2, 1), (1, 2),
            (3, 1), (1, 3),
            (4, 1), (1, 4),
            (2, 2),
        ]
        for n_movs, n_facts in patrones:
            nuevas += self._probar_patron(movs_disp, fac_saldos, nuevas, n_movs, n_facts)

        return nuevas

    def _probar_patron(
        self,
        movs: list[tuple[str, int, date | None]],
        facturas: list[tuple[str, int, date | None]],
        ya_aplicadas: list[AplicacionCreada],
        n_movs: int,
        n_facts: int,
    ) -> list[AplicacionCreada]:
        if len(movs) < n_movs or len(facturas) < n_facts:
            return []

        usados_mov: set[str] = {mid for a in ya_aplicadas for mid in a.movimiento_ids}
        usadas_fac: set[str] = {fid for a in ya_aplicadas for fid in a.factura_ids}
        resultado: list[AplicacionCreada] = []

        for mov_combo in itertools.combinations(movs, n_movs):
            if any(m[0] in usados_mov for m in mov_combo):
                continue
            total_mov = sum(m[1] for m in mov_combo)

            for fac_combo in itertools.combinations(facturas, n_facts):
                if any(f[0] in usadas_fac for f in fac_combo):
                    continue
                total_fac = sum(f[1] for f in fac_combo)

                if total_mov != total_fac:
                    continue

                # Verificar unicidad: si hay otra combinación de facturas que
                # sume lo mismo, es ambiguo.
                otros_fac = [
                    fc for fc in itertools.combinations(facturas, n_facts)
                    if fc != fac_combo
                    and not any(f[0] in usadas_fac for f in fc)
                    and sum(f[1] for f in fc) == total_mov
                ]
                if otros_fac:
                    continue

                mov_ids = [m[0] for m in mov_combo]
                fac_ids = [f[0] for f in fac_combo]
                try:
                    self._aplicar_combo(
                        mov_combo, fac_combo, total_mov,
                        f"combo {n_movs}×{n_facts}",
                    )
                    for m in mov_combo:
                        usados_mov.add(m[0])
                    for f in fac_combo:
                        usadas_fac.add(f[0])
                    resultado.append(AplicacionCreada(
                        movimiento_ids=mov_ids,
                        factura_ids=fac_ids,
                        monto=total_mov,
                        motivo=f"combo {n_movs}×{n_facts}",
                    ))
                    break
                except Exception:
                    db.session.rollback()
                    continue

        return resultado

    # ---------- Persistencia ----------
    def _aplicar(self, mov_id: str, factura_id: str, monto: int, motivo: str) -> None:
        existente = AplicacionPago.query.filter_by(
            movimiento_id=mov_id, factura_id=factura_id, activa=True
        ).first()
        if existente is not None:
            return
        self._aplicar_combo(
            [(mov_id, monto, None)],
            [(factura_id, monto, None)],
            monto, motivo,
        )

    def _aplicar_combo(
        self,
        mov_combo: list[tuple],
        fac_combo: list[tuple],
        monto: int,
        motivo: str,
    ) -> None:
        total_fac = sum(f[1] for f in fac_combo)
        hash_key = "|".join(sorted([m[0] for m in mov_combo] + [f[0] for f in fac_combo]))
        llave_base = f"auto-combo-{hashlib.sha256(hash_key.encode()).hexdigest()[:32]}"

        for f_id, f_saldo, _ in fac_combo:
            proporcion = f_saldo / total_fac if total_fac else 1.0
            monto_factura = int(round(monto * proporcion))

            movs_ord = sorted(mov_combo, key=lambda m: (m[2] or date.min), reverse=True)
            for m_id, m_disp, _ in movs_ord:
                disp_actual = m_disp - self._total_aplicado_mov(m_id)
                if disp_actual <= 0:
                    continue

                ya = AplicacionPago.query.filter_by(
                    movimiento_id=m_id, factura_id=f_id, activa=True
                ).first()
                if ya is not None:
                    continue

                monto_esta = min(monto_factura, disp_actual)
                llave = f"{llave_base}-{m_id[:8]}-{f_id[:8]}"
                existente_llave = AplicacionPago.query.filter_by(
                    llave_idempotencia=llave
                ).first()
                if existente_llave is not None:
                    monto_factura -= monto_esta
                    if monto_factura <= 0:
                        break
                    continue

                try:
                    db.session.add(AplicacionPago(
                        movimiento_id=m_id,
                        factura_id=f_id,
                        monto_aplicado=monto_esta,
                        metodo="automatico",
                        activa=True,
                        fecha_aplicacion=date.today(),
                        llave_idempotencia=llave,
                    ))
                    db.session.flush()
                    monto_factura -= monto_esta
                    if monto_factura <= 0:
                        break
                except Exception:
                    db.session.rollback()
                    continue

        # Aprender asociaciones
        try:
            from app.modules.conciliacion.services.aprendizaje_service import (
                AprendizajeService, CadenaDescubierta,
            )
            svc = AprendizajeService()
            for m_id, _, _ in mov_combo:
                for f_id, _, _ in fac_combo:
                    factura = Factura.query.filter_by(id=f_id).first()
                    if not factura:
                        continue
                    arr = self._inferir_arrendatario(factura)
                    if arr:
                        prop = self._inferir_propiedad(arr, factura)
                        if prop:
                            cadena = CadenaDescubierta(
                                movimiento_id=m_id,
                                arrendatario_id=arr.id,
                                propiedad_id=prop.id,
                                factura_id=f_id,
                                score_total=100,
                            )
                            try:
                                svc.aprender_cadena(cadena, origen="auto")
                            except Exception:
                                pass
        except Exception:
            pass

    # ---------- Helpers ----------
    def _total_aplicado_mov(self, mov_id: str) -> int:
        r = (
            db.session.query(func.coalesce(func.sum(AplicacionPago.monto_aplicado), 0))
            .filter(
                AplicacionPago.movimiento_id == mov_id,
                AplicacionPago.activa.is_(True),
            )
            .scalar()
        )
        return int(r or 0)

    def _total_pagado_factura(self, factura_id: str) -> int:
        r = (
            db.session.query(func.coalesce(func.sum(AplicacionPago.monto_aplicado), 0))
            .filter(
                AplicacionPago.factura_id == factura_id,
                AplicacionPago.activa.is_(True),
            )
            .scalar()
        )
        return int(r or 0)

    def _inferir_arrendatario(self, factura: Factura) -> Optional[Arrendatario]:
        if factura.rut_receptor_normalizado:
            ident = IdentidadTributaria.query.filter_by(
                rut_receptor_normalizado=factura.rut_receptor_normalizado, vigente=True
            ).first()
            if ident:
                return Arrendatario.query.filter_by(id=ident.arrendatario_id).first()
        for asoc in AsociacionFacturaPropiedad.query.filter_by(factura_id=factura.id).all():
            if asoc.propiedad:
                for pa in asoc.propiedad.arrendatarios:
                    return pa.arrendatario
        return None

    def _inferir_propiedad(self, arrendatario, factura: Factura) -> Optional[Propiedad]:
        from app.modules.conciliacion.utils.similitud import similitud_codigo_propiedad
        props = (
            db.session.query(Propiedad)
            .join(PropiedadArrendatario,
                  PropiedadArrendatario.propiedad_id == Propiedad.id)
            .filter(PropiedadArrendatario.arrendatario_id == arrendatario.id)
            .all()
        )
        codigos = [d.codigo for d in factura.detalles if d.codigo]
        if not codigos:
            return props[0] if len(props) == 1 else None
        mejor = None
        mejor_score = 0.0
        for p in props:
            for c in codigos:
                score = similitud_codigo_propiedad(c, p.nombre_original)
                if score > mejor_score:
                    mejor_score = score
                    mejor = p
        return mejor if mejor_score >= 0.8 else None