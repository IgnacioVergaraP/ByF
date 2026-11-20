"""Configuración de SQLAlchemy para SQLite y PostgreSQL."""
from contextvars import ContextVar
import sqlite3

from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session
from sqlalchemy import event
from sqlalchemy.engine import Engine

motor_solicitud: ContextVar[Engine | None] = ContextVar("motor_solicitud", default=None)


class SesionConciliacion(Session):
    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        if bind is None:
            bind = motor_solicitud.get()
        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)


db = SQLAlchemy(session_options={"class_": SesionConciliacion})


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Habilita claves foráneas en SQLite (deshabilitadas por defecto)."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db(app) -> None:
    """Inicializa SQLAlchemy y crea las tablas en el entorno local SQLite."""
    from app.modules.conciliacion import models  # noqa: F401

    db.init_app(app)
    if app.config["CREATE_TABLES"]:
        with app.app_context():
            db.create_all()
