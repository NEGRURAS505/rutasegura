"""Modelos SQLAlchemy según docs/api.md.
Tablas: units, routes, positions, trips, alerts, reports.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    """Serializa datetime a ISO 8601 UTC con sufijo Z (contrato docs/api.md)."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Unit(Base):
    __tablename__ = "units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id"), nullable=True)
    qr_token: Mapped[str] = mapped_column(String(64), unique=True)
    driver_token: Mapped[str] = mapped_column(String(64), unique=True)


class Route(Base):
    __tablename__ = "routes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    # JSON: listas de {lat, lon} para trazo y {nombre, lat, lon} para paradas
    trazo: Mapped[list] = mapped_column(JSON, default=list)
    paradas: Mapped[list] = mapped_column(JSON, default=list)


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(64), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    velocidad: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(64), index=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    alias_opcional: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origen: Mapped[str] = mapped_column(String(20))  # conductor | pasajero
    unit_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    severidad_ia: Mapped[str | None] = mapped_column(String(10), nullable=True)
    resumen_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    accion_sugerida: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default="abierta", index=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    categoria_ia: Mapped[str] = mapped_column(String(40), default="otro")
    descripcion_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgencia_ia: Mapped[str] = mapped_column(String(10), default="media")
    foto_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
