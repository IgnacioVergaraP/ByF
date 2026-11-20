"""Servicio que arma las columnas del mapa de asociaciones.

Dos vistas posibles:
  - Propiedad ↔ Arrendatario (maestro, solo lectura)
  - Arrendatario ↔ Depositante (aprendida, editable)

La columna de depositantes incluye TODOS los depositantes únicos
de los movimientos bancarios, estén o no asociados.
"""
from sqlalchemy import func

from app.core.database import db
from app.modules.conciliacion.models import (
    Arrendatario,
    AsociacionDepositante,
    MovimientoBancario,
    Propiedad,
    PropiedadArrendatario,
)


class GrafoService:
    def build(self) -> dict:
        # --- Propiedades (columna A del modo 1) ---
        propiedades = Propiedad.query.order_by(Propiedad.nombre_original).all()
        propiedades_out = []
        for p in propiedades:
            centro = p.centro_costo
            propiedades_out.append({
                "id": p.id,
                "nombre_original": p.nombre_original,
                "cc": centro.codigo if centro else None,
            })

        # --- Arrendatarios (columna B en ambos modos) ---
        arrendatarios = Arrendatario.query.order_by(
            Arrendatario.nombre_original
        ).all()
        arrendatarios_out = [
            {
                "id": a.id,
                "nombre_original": a.nombre_original,
                "nombre_normalizado": a.nombre_normalizado,
            }
            for a in arrendatarios
        ]

        # --- Depositantes (columna B del modo 2) ---
        # Todos los depositantes únicos de los movimientos, asociados o no.
        # Agrupamos por nombre normalizado, quedándonos con el original más reciente.
        rows = (
            db.session.query(
                MovimientoBancario.depositante_normalizado,
                MovimientoBancario.depositante_original,
                func.max(MovimientoBancario.created_at).label("ultima"),
            )
            .filter(MovimientoBancario.depositante_normalizado.isnot(None))
            .group_by(
                MovimientoBancario.depositante_normalizado,
                MovimientoBancario.depositante_original,
            )
            .all()
        )
        # Dedup por normalizado (nos quedamos con el último original visto)
        por_norm: dict[str, dict] = {}
        for norm, orig, ultima in rows:
            if not norm:
                continue
            prev = por_norm.get(norm)
            if prev is None or (ultima and prev.get("_ultima") and ultima > prev["_ultima"]):
                por_norm[norm] = {
                    "id": norm,
                    "nombre_original": orig or norm,
                    "nombre_normalizado": norm,
                    "_ultima": ultima,
                }
        depositantes_out = sorted(
            ({k: v for k, v in d.items() if k != "_ultima"} for d in por_norm.values()),
            key=lambda d: d["nombre_original"].lower(),
        )

        # --- Aristas Propiedad ↔ Arrendatario ---
        aristas_pa = []
        for pa in PropiedadArrendatario.query.all():
            aristas_pa.append({
                "propiedad_id": pa.propiedad_id,
                "arrendatario_id": pa.arrendatario_id,
                "tipo": "maestro",
            })

        # --- Aristas Arrendatario ↔ Depositante ---
        asocs = AsociacionDepositante.query.filter_by(vigente=True).all()
        aristas_ad = [
            {
                "id": a.id,
                "arrendatario_id": a.arrendatario_id,
                "depositante_id": a.depositante_normalizado,
                "tipo": "aprendida",
            }
            for a in asocs
        ]

        return {
            "propiedades": propiedades_out,
            "arrendatarios": arrendatarios_out,
            "depositantes": depositantes_out,
            "aristas_propiedad_arrendatario": aristas_pa,
            "aristas_arrendatario_depositante": aristas_ad,
        }