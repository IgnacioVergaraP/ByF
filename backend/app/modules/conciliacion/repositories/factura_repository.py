"""Repositorio de facturas."""
from typing import Optional

from app.core.database import db
from app.modules.conciliacion.models import (
    DetalleFactura, Factura, ImportacionFactura,
)


class FacturaRepository:
    def get_por_hash(self, archivo_hash: str) -> Optional[Factura]:
        return Factura.query.filter_by(archivo_hash=archivo_hash).first()

    def get_por_identidad(
        self, rut_emisor_norm: str, tipo: str, folio: str
    ) -> Optional[Factura]:
        return Factura.query.filter_by(
            rut_emisor_normalizado=rut_emisor_norm,
            tipo_documento=tipo,
            folio=folio,
        ).first()

    def get_factura(self, factura_id: str) -> Optional[Factura]:
        return Factura.query.filter_by(id=factura_id).first()

    def list_facturas(self) -> list[Factura]:
        return Factura.query.order_by(Factura.created_at.desc()).all()

    def list_importaciones(self) -> list[ImportacionFactura]:
        return ImportacionFactura.query.order_by(
            ImportacionFactura.created_at.desc()
        ).all()

    def create_importacion(self, **kwargs) -> ImportacionFactura:
        obj = ImportacionFactura(**kwargs)
        db.session.add(obj)
        db.session.flush()
        return obj

    def create_factura(self, **kwargs) -> Factura:
        obj = Factura(**kwargs)
        db.session.add(obj)
        db.session.flush()
        return obj

    def actualizar_factura(self, factura: Factura, **kwargs) -> Factura:
        """Reemplaza la extracción y sus detalles dentro de la misma transacción."""
        for campo, valor in kwargs.items():
            setattr(factura, campo, valor)
        factura.detalles.clear()
        factura.errores_json = None
        db.session.flush()
        return factura

    def create_detalle(self, factura_id: str, **kwargs) -> DetalleFactura:
        obj = DetalleFactura(factura_id=factura_id, **kwargs)
        db.session.add(obj)
        db.session.flush()
        return obj

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()