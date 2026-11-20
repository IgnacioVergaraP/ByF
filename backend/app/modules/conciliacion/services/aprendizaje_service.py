"""Servicio de descubrimiento y aprendizaje de cadenas de conciliación."""
import json
from dataclasses import dataclass, field
from datetime import date

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
from app.modules.conciliacion.utils.similitud import (
    similitud_codigo_propiedad,
    similitud_razon_social,
)


@dataclass
class CadenaDescubierta:
    movimiento_id: str
    arrendatario_id: str | None = None
    arrendatario_nombre: str | None = None
    arrendatario_score: float = 0.0
    propiedad_id: str | None = None
    propiedad_nombre: str | None = None
    propiedad_score: float = 0.0
    factura_id: str | None = None
    factura_folio: str | None = None
    factura_saldo: int = 0
    monto_disponible: int = 0
    score_total: int = 0
    motivo: list[str] = field(default_factory=list)


@dataclass
class ReconocerResult:
    procesadas: int = 0
    autoaplicadas: int = 0
    sugeridas: int = 0
    errores: list[str] = field(default_factory=list)


class AprendizajeService:
    # ---------- Descubrimiento ----------
    def descubrir_cadenas_para_movimiento(
        self, movimiento_id: str
    ) -> list[CadenaDescubierta]:
        mov = MovimientoBancario.query.filter_by(id=movimiento_id).first()
        if mov is None:
            return []

        disponible = int(mov.monto) - self._total_aplicado_movimiento(movimiento_id)
        if disponible <= 0:
            return []

        facturas_con_saldo = []
        for f in Factura.query.filter_by(estado="procesada").all():
            saldo = int(f.total or 0) - self._total_pagado_factura(f.id)
            if saldo > 0:
                facturas_con_saldo.append((f, saldo))
        if not facturas_con_saldo:
            return []

        cadenas: list[CadenaDescubierta] = []
        dep_norm = (mov.depositante_normalizado or "").strip()

        for factura, saldo in facturas_con_saldo:
            arr_match = self._mejor_arrendatario_para_factura(factura)
            if arr_match is None:
                continue
            arr, arr_score_receptor = arr_match

            prop_match = self._mejor_propiedad_para_factura(arr.id, factura)
            if prop_match is None:
                continue
            prop, prop_score_codigo = prop_match

            dep_arr_score = similitud_razon_social(dep_norm, arr.nombre_original)
            dep_rec_score = similitud_razon_social(
                dep_norm, factura.razon_social_receptor or ""
            )

            # Filtro duro: solo cadenas con al menos una coincidencia real
            if (arr_score_receptor < 0.55
                    and dep_rec_score < 0.65
                    and dep_arr_score < 0.65):
                continue

            base = 0
            motivos = []

            if arr_score_receptor >= 0.55:
                base += 40
                motivos.append(f"receptor↔arrendatario ({arr_score_receptor:.2f})")
            elif dep_rec_score >= 0.65:
                base += 40
                motivos.append(f"depositante↔receptor ({dep_rec_score:.2f})")

            if dep_arr_score >= 0.65:
                base += 20
                motivos.append(f"depositante↔arrendatario ({dep_arr_score:.2f})")
            elif dep_rec_score >= 0.65:
                base += 20
                motivos.append(f"depositante↔receptor2 ({dep_rec_score:.2f})")

            if prop_score_codigo >= 0.8:
                base += 30
                motivos.append(f"código↔propiedad ({prop_score_codigo:.2f})")

            if disponible == saldo:
                base += 20
                motivos.append("monto exacto")
            elif disponible >= saldo:
                base += 10
                motivos.append("monto suficiente")

            cadenas.append(CadenaDescubierta(
                movimiento_id=movimiento_id,
                arrendatario_id=arr.id,
                arrendatario_nombre=arr.nombre_original,
                arrendatario_score=max(arr_score_receptor, dep_rec_score, dep_arr_score),
                propiedad_id=prop.id,
                propiedad_nombre=prop.nombre_original,
                propiedad_score=prop_score_codigo,
                factura_id=factura.id,
                factura_folio=factura.folio,
                factura_saldo=saldo,
                monto_disponible=disponible,
                score_total=base,
                motivo=motivos,
            ))

        cadenas.sort(key=lambda c: c.score_total, reverse=True)
        return cadenas

    def descubrir_cadenas_para_factura(self, factura_id: str) -> list[CadenaDescubierta]:
        factura = Factura.query.filter_by(id=factura_id).first()
        if factura is None:
            return []
        saldo = int(factura.total or 0) - self._total_pagado_factura(factura_id)
        if saldo <= 0:
            return []

        arr_match = self._mejor_arrendatario_para_factura(factura)
        if arr_match is None:
            return []
        arr, arr_score = arr_match

        prop_match = self._mejor_propiedad_para_factura(arr.id, factura)
        if prop_match is None:
            return []
        prop, prop_score = prop_match

        cadenas = []
        for m in MovimientoBancario.query.all():
            disponible = int(m.monto) - self._total_aplicado_movimiento(m.id)
            if disponible <= 0:
                continue

            dep_norm = (m.depositante_normalizado or "").strip()
            dep_arr = similitud_razon_social(dep_norm, arr.nombre_original)
            dep_rec = similitud_razon_social(
                dep_norm, factura.razon_social_receptor or ""
            )

            # FILTRO DURO: solo movimientos del mismo arrendatario/receptor
            if dep_arr < 0.65 and dep_rec < 0.65:
                continue

            base = 0
            motivos = []
            if arr_score >= 0.55:
                base += 40
                motivos.append(f"receptor↔arrendatario ({arr_score:.2f})")
            elif dep_rec >= 0.65:
                base += 40
                motivos.append(f"depositante↔receptor ({dep_rec:.2f})")

            if dep_arr >= 0.65:
                base += 20
                motivos.append(f"depositante↔arrendatario ({dep_arr:.2f})")
            elif dep_rec >= 0.65:
                base += 20
                motivos.append(f"depositante↔receptor2 ({dep_rec:.2f})")

            if prop_score >= 0.8:
                base += 30
                motivos.append(f"código↔propiedad ({prop_score:.2f})")

            if disponible == saldo:
                base += 20
                motivos.append("monto exacto")
            elif disponible >= saldo:
                base += 10
                motivos.append("monto suficiente")

            cadenas.append(CadenaDescubierta(
                movimiento_id=m.id,
                arrendatario_id=arr.id,
                arrendatario_nombre=arr.nombre_original,
                arrendatario_score=max(arr_score, dep_rec, dep_arr),
                propiedad_id=prop.id,
                propiedad_nombre=prop.nombre_original,
                propiedad_score=prop_score,
                factura_id=factura_id,
                factura_folio=factura.folio,
                factura_saldo=saldo,
                monto_disponible=disponible,
                score_total=base,
                motivo=motivos,
            ))

        cadenas.sort(key=lambda c: c.score_total, reverse=True)
        return cadenas

    # ---------- Inferencia de propiedad por código ----------
    def inferir_propiedad_para_factura(self, factura_id: str) -> bool:
        """Si la factura tiene identidad tributaria y no tiene AsociacionFacturaPropiedad,
        intenta asignar la propiedad por código de línea.
        """
        factura = Factura.query.filter_by(id=factura_id).first()
        if factura is None:
            return False

        # Si ya tiene propiedad, no hacemos nada
        existentes = AsociacionFacturaPropiedad.query.filter_by(factura_id=factura_id).count()
        if existentes > 0:
            return True

        # Necesita identidad tributaria
        if not factura.rut_receptor_normalizado:
            return False
        ident = IdentidadTributaria.query.filter_by(
            rut_receptor_normalizado=factura.rut_receptor_normalizado, vigente=True
        ).first()
        if ident is None:
            return False

        arr = Arrendatario.query.filter_by(id=ident.arrendatario_id).first()
        if arr is None:
            return False

        prop_match = self._mejor_propiedad_para_factura(arr.id, factura)
        if prop_match is None:
            return False
        prop, score = prop_match
        if score < 0.8:
            return False

        # Crear la asociación
        conceptos = []
        for d in factura.detalles:
            desc = (d.descripcion or "").lower()
            if "arriendo" in desc and "Arriendo" not in conceptos:
                conceptos.append("Arriendo")
            if "ggcc" in desc and "GGCC" not in conceptos:
                conceptos.append("GGCC")

        asoc = AsociacionFacturaPropiedad(
            factura_id=factura_id,
            propiedad_id=prop.id,
            centro_costo_id=prop.centro_costo_id,
            estado="asociada_automatica",
            metodo="por_codigo_linea",
        )
        asoc.set_conceptos(conceptos)
        db.session.add(asoc)
        factura.estado_asociacion = "asociada_automatica"
        db.session.flush()
        return True

    # ---------- Matching interno ----------
    def _mejor_arrendatario_para_factura(
        self, factura: Factura
    ) -> tuple[Arrendatario, float] | None:
        if factura.rut_receptor_normalizado:
            ident = IdentidadTributaria.query.filter_by(
                rut_receptor_normalizado=factura.rut_receptor_normalizado,
                vigente=True,
            ).first()
            if ident:
                arr = Arrendatario.query.filter_by(id=ident.arrendatario_id).first()
                if arr:
                    if self._arrendatario_matchea_codigos(arr.id, factura):
                        return (arr, 1.0)

        receptor = factura.razon_social_receptor or ""
        if not receptor:
            return None
        mejor: tuple[Arrendatario, float] | None = None
        for arr in Arrendatario.query.all():
            score = similitud_razon_social(receptor, arr.nombre_original)
            if mejor is None or score > mejor[1]:
                mejor = (arr, score)
        if mejor is None or mejor[1] < 0.5:
            return None
        return mejor

    def _arrendatario_matchea_codigos(self, arrendatario_id: str, factura: Factura) -> bool:
        props = (
            db.session.query(Propiedad)
            .join(PropiedadArrendatario,
                  PropiedadArrendatario.propiedad_id == Propiedad.id)
            .filter(PropiedadArrendatario.arrendatario_id == arrendatario_id)
            .all()
        )
        if not props:
            return False
        codigos = [d.codigo for d in factura.detalles if d.codigo]
        if not codigos:
            return len(props) == 1
        for p in props:
            for c in codigos:
                if similitud_codigo_propiedad(c, p.nombre_original) >= 0.8:
                    return True
        return False

    def _mejor_propiedad_para_factura(
        self, arrendatario_id: str, factura: Factura
    ) -> tuple[Propiedad, float] | None:
        props = (
            db.session.query(Propiedad)
            .join(PropiedadArrendatario,
                  PropiedadArrendatario.propiedad_id == Propiedad.id)
            .filter(PropiedadArrendatario.arrendatario_id == arrendatario_id)
            .all()
        )
        if not props:
            return None

        codigos = [d.codigo for d in factura.detalles if d.codigo]
        if not codigos:
            if len(props) == 1:
                return (props[0], 1.0)
            return None

        mejor: tuple[Propiedad, float] | None = None
        for p in props:
            score = max(
                (similitud_codigo_propiedad(c, p.nombre_original) for c in codigos),
                default=0.0,
            )
            if mejor is None or score > mejor[1]:
                mejor = (p, score)
        if mejor is None or mejor[1] < 0.5:
            return None
        return mejor

    # ---------- Persistencia ----------
    def aprender_cadena(self, cadena: CadenaDescubierta, origen: str = "auto") -> None:
        if cadena.arrendatario_id:
            mov = MovimientoBancario.query.filter_by(id=cadena.movimiento_id).first()
            if mov and mov.depositante_normalizado:
                existe = AsociacionDepositante.query.filter_by(
                    depositante_normalizado=mov.depositante_normalizado,
                    arrendatario_id=cadena.arrendatario_id,
                ).first()
                if existe is None:
                    db.session.add(AsociacionDepositante(
                        depositante_original=mov.depositante_original or "",
                        depositante_normalizado=mov.depositante_normalizado,
                        arrendatario_id=cadena.arrendatario_id,
                        vigente=True,
                    ))
                else:
                    existe.vigente = True
                db.session.flush()

        if cadena.factura_id and cadena.arrendatario_id:
            factura = Factura.query.filter_by(id=cadena.factura_id).first()
            if factura and factura.rut_receptor_normalizado:
                existe = IdentidadTributaria.query.filter_by(
                    rut_receptor_normalizado=factura.rut_receptor_normalizado
                ).first()
                if existe is None:
                    db.session.add(IdentidadTributaria(
                        rut_receptor_normalizado=factura.rut_receptor_normalizado,
                        razon_social_original=factura.razon_social_receptor,
                        arrendatario_id=cadena.arrendatario_id,
                        vigente=True,
                        origen=origen,
                    ))
                else:
                    existe.arrendatario_id = cadena.arrendatario_id
                    existe.vigente = True
                db.session.flush()

        if cadena.factura_id and cadena.propiedad_id:
            existe = AsociacionFacturaPropiedad.query.filter_by(
                factura_id=cadena.factura_id,
                propiedad_id=cadena.propiedad_id,
            ).first()
            if existe is None:
                prop = Propiedad.query.filter_by(id=cadena.propiedad_id).first()
                factura = Factura.query.filter_by(id=cadena.factura_id).first()
                conceptos = []
                if factura:
                    for d in factura.detalles:
                        desc = (d.descripcion or "").lower()
                        if "arriendo" in desc and "Arriendo" not in conceptos:
                            conceptos.append("Arriendo")
                        if "ggcc" in desc and "GGCC" not in conceptos:
                            conceptos.append("GGCC")
                obj = AsociacionFacturaPropiedad(
                    factura_id=cadena.factura_id,
                    propiedad_id=cadena.propiedad_id,
                    centro_costo_id=prop.centro_costo_id if prop else None,
                    estado="asociada_automatica" if origen == "auto" else "asociada_manual",
                    metodo="por_rut_aprendido",
                )
                obj.set_conceptos(conceptos)
                db.session.add(obj)
                db.session.flush()

            factura = Factura.query.filter_by(id=cadena.factura_id).first()
            if factura:
                factura.estado_asociacion = (
                    "asociada_automatica" if origen == "auto" else "asociada_manual"
                )
                db.session.flush()

    # ---------- Reconocimiento ----------
    def reconocer_todos(self) -> ReconocerResult:
        res = ReconocerResult()

        # Antes de procesar: inferir propiedades para facturas que tengan
        # identidad tributaria pero no AsociacionFacturaPropiedad.
        facturas_sin_prop = (
            Factura.query
            .filter(Factura.estado == "procesada")
            .all()
        )
        for f in facturas_sin_prop:
            try:
                self.inferir_propiedad_para_factura(f.id)
            except Exception:
                pass
        db.session.commit()

        movs = MovimientoBancario.query.all()
        for mov in movs:
            disponible = int(mov.monto) - self._total_aplicado_movimiento(mov.id)
            if disponible <= 0:
                continue
            res.procesadas += 1

            cadenas = self.descubrir_cadenas_para_movimiento(mov.id)
            altas = [c for c in cadenas if c.score_total >= 90]
            if len(altas) != 1:
                if altas:
                    res.sugeridas += len(altas)
                continue

            cadena = altas[0]
            try:
                self.aprender_cadena(cadena, origen="auto")
                monto_aplicar = min(cadena.monto_disponible, cadena.factura_saldo)
                db.session.add(AplicacionPago(
                    movimiento_id=cadena.movimiento_id,
                    factura_id=cadena.factura_id,
                    monto_aplicado=int(monto_aplicar),
                    metodo="automatico",
                    activa=True,
                    fecha_aplicacion=date.today(),
                    llave_idempotencia=f"auto-{cadena.movimiento_id}-{cadena.factura_id}",
                ))
                db.session.flush()
                res.autoaplicadas += 1
            except Exception as exc:
                db.session.rollback()
                res.errores.append(f"Mov {mov.id}: {exc}")

        db.session.commit()
        return res

    # ---------- Helpers ----------
    def _total_aplicado_movimiento(self, movimiento_id: str) -> int:
        result = (
            db.session.query(func.coalesce(func.sum(AplicacionPago.monto_aplicado), 0))
            .filter(
                AplicacionPago.movimiento_id == movimiento_id,
                AplicacionPago.activa.is_(True),
            )
            .scalar()
        )
        return int(result or 0)

    def _total_pagado_factura(self, factura_id: str) -> int:
        result = (
            db.session.query(func.coalesce(func.sum(AplicacionPago.monto_aplicado), 0))
            .filter(
                AplicacionPago.factura_id == factura_id,
                AplicacionPago.activa.is_(True),
            )
            .scalar()
        )
        return int(result or 0)