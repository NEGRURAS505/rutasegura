"""Esquemas pydantic (validación estricta de entradas) según docs/api.md."""
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Lat = Field(ge=-90.0, le=90.0)
Lon = Field(ge=-180.0, le=180.0)


class PositionIn(BaseModel):
    unit_id: str = Field(min_length=1, max_length=64)
    lat: float = Lat
    lon: float = Lon
    velocidad: float = Field(default=0.0, ge=0.0, le=200.0)  # km/h
    timestamp: Optional[str] = None  # ISO 8601; si se omite usa hora del servidor


class Point(BaseModel):
    lat: float = Lat
    lon: float = Lon


class StopOut(BaseModel):
    nombre: str
    lat: float
    lon: float


class RouteOut(BaseModel):
    id: int
    nombre: str
    trazo: list[Point]
    paradas: list[StopOut]


class UnitLiveOut(BaseModel):
    unit_id: str
    nombre: str
    route_id: Optional[int] = None
    posicion: Optional[dict] = None  # {lat, lon, velocidad, timestamp}


class TripIn(BaseModel):
    qr_token: str = Field(min_length=1, max_length=64)
    lat: Optional[float] = None
    lon: Optional[float] = None
    alias: Optional[str] = Field(default=None, max_length=80)


class TripOut(BaseModel):
    id: int
    unit_id: str
    nombre_unidad: str
    route_id: Optional[int] = None
    nombre_ruta: Optional[str] = None
    timestamp: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    alias: Optional[str] = None


class AlertIn(BaseModel):
    origen: Literal["conductor", "pasajero"]
    unit_id: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    texto: Optional[str] = Field(default=None, max_length=500)

    @field_validator("texto")
    @classmethod
    def no_vacio(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            return None
        return v


class AlertOut(BaseModel):
    id: int
    origen: str
    unit_id: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    texto: Optional[str] = None
    severidad_ia: Optional[str] = None
    resumen_ia: Optional[str] = None
    accion_sugerida: Optional[str] = None
    estado: str
    creada_en: str


class AlertEstadoIn(BaseModel):
    estado: Literal["atendida", "falsa_alarma"]


class ReportIn(BaseModel):
    texto: Optional[str] = Field(default=None, max_length=1000)
    foto_base64: Optional[str] = None  # data URI opcional: data:image/jpeg;base64,...
    lat: Optional[float] = None
    lon: Optional[float] = None


class ReportOut(BaseModel):
    id: int
    texto: Optional[str] = None
    categoria_ia: str
    descripcion_ia: Optional[str] = None
    urgencia_ia: str
    foto_ref: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    creada_en: str


class AssistantIn(BaseModel):
    pregunta: str = Field(min_length=1, max_length=500)


class AssistantOut(BaseModel):
    respuesta: str
    fallo: bool  # true = se usó el respaldo por reglas
