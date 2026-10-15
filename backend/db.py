"""Base de datos SQLAlchemy (SQLite) para RutaSegura Carmen.

Rol: 1. Simple y con state en app.state para poder correr tests aislados.
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DEFAULT_DB_URL = "sqlite:///./data/rutasegura.db"


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str = DEFAULT_DB_URL):
    if database_url.startswith("sqlite"):
        # SQLite no crea el directorio padre; lo garantizamos (data/db, /data, etc.)
        ruta_archivo = database_url.split("sqlite:///", 1)[-1]
        if ruta_archivo.startswith("/"):
            ruta_archivo = ruta_archivo[1:]
        padre = Path(ruta_archivo).parent
        if str(padre) not in ("", "."):
            padre.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI corre endpoints sync en un threadpool.
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
