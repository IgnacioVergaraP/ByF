"""Repositorio de acceso a datos del maestro de arrendatarios."""
from typing import Optional

from app.core.database import db
from app.modules.conciliacion.models import (
    Arrendatario,
    CentroCosto,
    Concepto,
    Propiedad,
    PropiedadArrendatario,
    PropiedadConcepto,
)


class MaestroRepository:
    def get_centro_by_codigo(self, codigo: str) -> Optional[CentroCosto]:
        # Buscar por código normalizado para evitar duplicados por case
        from app.modules.conciliacion.utils.normalization import normalize_text
        norm = normalize_text(codigo)
        return CentroCosto.query.filter_by(nombre_normalizado=norm).first()

    def get_propiedad(self, centro_id: str, nombre_norm: str) -> Optional[Propiedad]:
        return Propiedad.query.filter_by(
            centro_costo_id=centro_id, nombre_normalizado=nombre_norm
        ).first()

    def get_arrendatario(self, nombre_norm: str) -> Optional[Arrendatario]:
        return Arrendatario.query.filter_by(nombre_normalizado=nombre_norm).first()

    def get_concepto(self, nombre_norm: str) -> Optional[Concepto]:
        return Concepto.query.filter_by(nombre_normalizado=nombre_norm).first()

    def create_centro(self, codigo: str, nombre_original: str,
                      nombre_normalizado: str) -> CentroCosto:
        obj = CentroCosto(
            codigo=codigo,
            nombre_original=nombre_original,
            nombre_normalizado=nombre_normalizado,
        )
        db.session.add(obj)
        db.session.flush()
        return obj

    def create_propiedad(self, nombre_original: str, nombre_normalizado: str,
                         centro_id: str) -> Propiedad:
        obj = Propiedad(
            nombre_original=nombre_original,
            nombre_normalizado=nombre_normalizado,
            centro_costo_id=centro_id,
        )
        db.session.add(obj)
        db.session.flush()
        return obj

    def create_arrendatario(self, nombre_original: str,
                            nombre_normalizado: str) -> Arrendatario:
        obj = Arrendatario(
            nombre_original=nombre_original,
            nombre_normalizado=nombre_normalizado,
        )
        db.session.add(obj)
        db.session.flush()
        return obj

    def create_concepto(self, nombre: str, nombre_normalizado: str) -> Concepto:
        obj = Concepto(nombre=nombre, nombre_normalizado=nombre_normalizado)
        db.session.add(obj)
        db.session.flush()
        return obj

    def link_propiedad_arrendatario(self, propiedad_id: str,
                                    arrendatario_id: str) -> None:
        exists = PropiedadArrendatario.query.filter_by(
            propiedad_id=propiedad_id, arrendatario_id=arrendatario_id
        ).first()
        if not exists:
            db.session.add(PropiedadArrendatario(
                propiedad_id=propiedad_id, arrendatario_id=arrendatario_id
            ))
            db.session.flush()

    def link_propiedad_concepto(self, propiedad_id: str, concepto_id: str) -> None:
        exists = PropiedadConcepto.query.filter_by(
            propiedad_id=propiedad_id, concepto_id=concepto_id
        ).first()
        if not exists:
            db.session.add(PropiedadConcepto(
                propiedad_id=propiedad_id, concepto_id=concepto_id
            ))
            db.session.flush()

    def list_propiedades(self) -> list[Propiedad]:
        return Propiedad.query.order_by(Propiedad.nombre_original).all()

    def list_arrendatarios(self) -> list[Arrendatario]:
        return Arrendatario.query.order_by(Arrendatario.nombre_original).all()

    def list_centros(self) -> list[CentroCosto]:
        return CentroCosto.query.order_by(CentroCosto.codigo).all()

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()