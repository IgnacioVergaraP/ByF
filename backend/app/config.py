"""Configuración de la aplicación basada en variables de entorno."""
import os
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

BASE_DIR = Path(__file__).resolve().parent.parent
POSTGRES_SCHEMA = "inmobiliaria"
POSTGRES_SCHEMA_MAP = {None: POSTGRES_SCHEMA}


def postgres_url(value: str):
    url = make_url(value)
    if url.drivername not in ("postgres", "postgresql", "postgresql+psycopg2"):
        raise RuntimeError("DATABASE_URL debe apuntar a PostgreSQL.")
    url = url.set(drivername="postgresql+psycopg2")
    if "sslmode" not in url.query:
        url = url.update_query_dict({"sslmode": "require"})
    return url


class Config:
    """Configuración base."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:4200,http://127.0.0.1:4200"
    ).split(",")

    # Base de datos
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    USE_DATA_API = False

    def __init__(self):
        self.USE_DATA_API = self.USE_DATA_API or os.getenv("USE_DATA_API") == "true"
        self.SQLALCHEMY_ENGINE_OPTIONS = {}
        if self.USE_DATA_API:
            self.SQLALCHEMY_DATABASE_URI = "sqlite://"
            self.CREATE_TABLES = False
            return
        database_url = os.getenv("DATABASE_URL")
        self.SQLALCHEMY_DATABASE_URI = database_url or f"sqlite:///{BASE_DIR / 'instance' / 'conciliacion.db'}"
        self.CREATE_TABLES = make_url(self.SQLALCHEMY_DATABASE_URI).get_backend_name() == "sqlite"
        if not self.CREATE_TABLES:
            self.SQLALCHEMY_DATABASE_URI = postgres_url(self.SQLALCHEMY_DATABASE_URI)
            self.SQLALCHEMY_ENGINE_OPTIONS = {
                "poolclass": NullPool,
                "execution_options": {"schema_translate_map": POSTGRES_SCHEMA_MAP},
                "hide_parameters": True,
            }


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    PRIVATE_ACCESS = True
    USE_DATA_API = True

    def __init__(self):
        super().__init__()
        self.APP_USERNAME = os.getenv("APP_USERNAME")
        self.APP_PASSWORD = os.getenv("APP_PASSWORD")
        if not self.APP_USERNAME or not self.APP_PASSWORD:
            raise RuntimeError("Configura APP_USERNAME y APP_PASSWORD para producción.")


def get_config() -> Config:
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production" or os.getenv("VERCEL"):
        return ProductionConfig()
    return DevelopmentConfig()
