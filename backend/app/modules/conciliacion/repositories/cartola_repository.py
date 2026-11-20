"""Repositorio de cartolas."""
from typing import Optional

from app.core.database import db
from app.modules.conciliacion.models import Cartola, CuentaBancaria


class CartolaRepository:
    def get_cuenta_por_numero(self, numero: str) -> Optional[CuentaBancaria]:
        return CuentaBancaria.query.filter_by(numero_cuenta=numero).first()

    def create_cuenta(self, banco: str, numero: str, moneda: str = "CLP") -> CuentaBancaria:
        obj = CuentaBancaria(banco=banco, numero_cuenta=numero, moneda=moneda)
        db.session.add(obj)
        db.session.flush()
        return obj

    def get_cartola_por_hash(self, archivo_hash: str) -> Optional[Cartola]:
        return Cartola.query.filter_by(archivo_hash=archivo_hash).first()

    def create_cartola(self, **kwargs) -> Cartola:
        obj = Cartola(**kwargs)
        db.session.add(obj)
        db.session.flush()
        return obj

    def list_cartolas(self) -> list[Cartola]:
        return Cartola.query.order_by(Cartola.created_at.desc()).all()

    def get_cartola(self, cartola_id: str) -> Optional[Cartola]:
        return Cartola.query.filter_by(id=cartola_id).first()

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()