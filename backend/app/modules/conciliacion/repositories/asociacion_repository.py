"""Repositorio de asociaciones."""
from typing import Optional

from sqlalchemy import and_

from app.core.database import db
from app.modules.conciliacion.models import (
    AsociacionDepositante,
    AsociacionMovimiento,
    Arrendatario,
    HistorialAsociacion,
    MovimientoBancario,
    Propiedad,
    PropiedadArrendatario,
)


class AsociacionRepository:
    # ---------- Búsquedas ----------
    def get_asociacion_depositante(
        self, depositante_norm: str, arrendatario_id: str
    ) -> Optional[AsociacionDepositante]:
        return AsociacionDepositante.query.filter_by(
            depositante_normalizado=depositante_norm,
            arrendatario_id=arrendatario_id,
        ).first()

    def list_asociaciones_por_depositante(
        self, depositante_norm: str, solo_vigentes: bool = True
    ) -> list[AsociacionDepositante]:
        q = AsociacionDepositante.query.filter_by(
            depositante_normalizado=depositante_norm
        )
        if solo_vigentes:
            q = q.filter(AsociacionDepositante.vigente.is_(True))
        return q.all()

    def get_arrendatario(self, arrendatario_id: str) -> Optional[Arrendatario]:
        return Arrendatario.query.filter_by(id=arrendatario_id).first()

    def get_propiedad(self, propiedad_id: str) -> Optional[Propiedad]:
        return Propiedad.query.filter_by(id=propiedad_id).first()

    def propiedades_de_arrendatario(self, arrendatario_id: str) -> list[Propiedad]:
        """Devuelve propiedades asociadas al arrendatario en el maestro."""
        return (
            db.session.query(Propiedad)
            .join(PropiedadArrendatario,
                  PropiedadArrendatario.propiedad_id == Propiedad.id)
            .filter(PropiedadArrendatario.arrendatario_id == arrendatario_id)
            .all()
        )

    def get_movimiento(self, movimiento_id: str) -> Optional[MovimientoBancario]:
        return MovimientoBancario.query.filter_by(id=movimiento_id).first()

    def asociaciones_de_movimiento(self, movimiento_id: str) -> list[AsociacionMovimiento]:
        return AsociacionMovimiento.query.filter_by(
            movimiento_id=movimiento_id
        ).all()

    # ---------- Creaciones ----------
    def get_or_create_asociacion(
        self, depositante_original: str, depositante_norm: str, arrendatario_id: str
    ) -> AsociacionDepositante:
        obj = self.get_asociacion_depositante(depositante_norm, arrendatario_id)
        if obj is not None:
            obj.vigente = True
            db.session.flush()
            return obj
        obj = AsociacionDepositante(
            depositante_original=depositante_original,
            depositante_normalizado=depositante_norm,
            arrendatario_id=arrendatario_id,
            vigente=True,
        )
        db.session.add(obj)
        db.session.flush()
        return obj

    def create_asociacion_movimiento(
        self, movimiento_id: str, asociacion_id: str, propiedad_id: str,
        conceptos: list[str], estado: str,
    ) -> AsociacionMovimiento:
        obj = AsociacionMovimiento(
            movimiento_id=movimiento_id,
            asociacion_id=asociacion_id,
            propiedad_id=propiedad_id,
            estado=estado,
        )
        obj.set_conceptos(conceptos)
        db.session.add(obj)
        db.session.flush()
        return obj

    def delete_asociaciones_de_movimiento(self, movimiento_id: str) -> None:
        AsociacionMovimiento.query.filter_by(
            movimiento_id=movimiento_id
        ).delete(synchronize_session=False)
        db.session.flush()

    def add_historial(
        self, movimiento_id: str, accion: str, detalle_json: str,
        usuario: str | None = None,
    ) -> HistorialAsociacion:
        h = HistorialAsociacion(
            movimiento_id=movimiento_id,
            accion=accion,
            detalle_json=detalle_json,
            usuario=usuario,
        )
        db.session.add(h)
        db.session.flush()
        return h

    # ---------- Actualizaciones ----------
    def set_estado_movimiento(self, mov: MovimientoBancario, estado: str) -> None:
        mov.estado = estado
        db.session.flush()

    # ---------- Transacciones ----------
    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()