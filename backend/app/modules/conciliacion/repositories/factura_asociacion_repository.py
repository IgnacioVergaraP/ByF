"""Repositorio de asociaciones de facturas."""
from typing import Optional

from sqlalchemy import or_

from app.core.database import db
from app.modules.conciliacion.models import (
    Arrendatario,
    AsociacionFacturaPropiedad,
    Factura,
    HistorialAsociacionFactura,
    IdentidadTributaria,
    Propiedad,
    PropiedadArrendatario,
)


class FacturaAsociacionRepository:
    # ---------- Identidad tributaria ----------
    def get_identidad(self, rut_norm: str) -> Optional[IdentidadTributaria]:
        return IdentidadTributaria.query.filter_by(
            rut_receptor_normalizado=rut_norm, vigente=True
        ).first()

    def list_identidades(self) -> list[IdentidadTributaria]:
        return IdentidadTributaria.query.order_by(
            IdentidadTributaria.rut_receptor_normalizado
        ).all()

    def upsert_identidad(
        self, rut_norm: str, razon_social: str | None, arrendatario_id: str,
        origen: str = "manual",
    ) -> IdentidadTributaria:
        existente = IdentidadTributaria.query.filter_by(
            rut_receptor_normalizado=rut_norm
        ).first()
        if existente:
            existente.arrendatario_id = arrendatario_id
            existente.vigente = True
            existente.origen = origen
            if razon_social:
                existente.razon_social_original = razon_social
            db.session.flush()
            return existente
        obj = IdentidadTributaria(
            rut_receptor_normalizado=rut_norm,
            razon_social_original=razon_social,
            arrendatario_id=arrendatario_id,
            vigente=True,
            origen=origen,
        )
        db.session.add(obj)
        db.session.flush()
        return obj

    # ---------- Asociaciones factura → propiedad ----------
    def get_factura(self, factura_id: str) -> Optional[Factura]:
        return Factura.query.filter_by(id=factura_id).first()

    def asociaciones_de_factura(self, factura_id: str) -> list[AsociacionFacturaPropiedad]:
        return AsociacionFacturaPropiedad.query.filter_by(factura_id=factura_id).all()

    def limpiar_asociaciones_factura(self, factura_id: str) -> None:
        AsociacionFacturaPropiedad.query.filter_by(
            factura_id=factura_id
        ).delete(synchronize_session=False)
        db.session.flush()

    def create_asociacion(
        self, factura_id: str, propiedad_id: str, centro_costo_id: str | None,
        conceptos: list[str], estado: str, metodo: str,
    ) -> AsociacionFacturaPropiedad:
        obj = AsociacionFacturaPropiedad(
            factura_id=factura_id,
            propiedad_id=propiedad_id,
            centro_costo_id=centro_costo_id,
            estado=estado,
            metodo=metodo,
        )
        obj.set_conceptos(conceptos)
        db.session.add(obj)
        db.session.flush()
        return obj

    def set_estado_factura(self, factura: Factura, estado: str) -> None:
        factura.estado_asociacion = estado
        db.session.flush()

    # ---------- Búsquedas para sugerencias ----------
    def buscar_arrendatarios_por_nombre(self, termino: str) -> list[Arrendatario]:
        if not termino:
            return []
        t = f"%{termino.lower()}%"
        return Arrendatario.query.filter(
            or_(
                Arrendatario.nombre_normalizado.ilike(t),
                Arrendatario.nombre_original.ilike(t),
            )
        ).limit(20).all()

    def get_arrendatario(self, arr_id: str) -> Optional[Arrendatario]:
        return Arrendatario.query.filter_by(id=arr_id).first()

    def propiedades_de_arrendatario(self, arr_id: str) -> list[Propiedad]:
        return (
            db.session.query(Propiedad)
            .join(PropiedadArrendatario,
                  PropiedadArrendatario.propiedad_id == Propiedad.id)
            .filter(PropiedadArrendatario.arrendatario_id == arr_id)
            .all()
        )

    def get_propiedad(self, prop_id: str) -> Optional[Propiedad]:
        return Propiedad.query.filter_by(id=prop_id).first()

    # ---------- Historial ----------
    def add_historial(
        self, factura_id: str, accion: str, detalle_json: str | None,
        usuario: str | None = None,
    ) -> HistorialAsociacionFactura:
        obj = HistorialAsociacionFactura(
            factura_id=factura_id,
            accion=accion,
            detalle_json=detalle_json,
            usuario=usuario,
        )
        db.session.add(obj)
        db.session.flush()
        return obj

    def list_historial(self, factura_id: str) -> list[HistorialAsociacionFactura]:
        return HistorialAsociacionFactura.query.filter_by(
            factura_id=factura_id
        ).order_by(HistorialAsociacionFactura.created_at.desc()).all()

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()