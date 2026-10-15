"""Rutas de demostración para Ciudad del Carmen.

Los recorridos se trazan de forma aproximada a partir de referencias públicas:
la UNACAR describe el itinerario de Campus III y notas periodísticas confirman
la operación de Costera y la existencia de Laguna & Términos. No se publicaron
trazos GPS oficiales; los puntos son referencias de mapa, no paraderos oficiales.
"""
import json
import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from .models import Route, Unit


def _points(values: list[tuple[float, float]]) -> list[dict]:
    """Convierte pares (latitud, longitud) al formato de la API."""
    return [{"lat": lat, "lon": lon} for lat, lon in values]


def _references(values: list[tuple[str, float, float]]) -> list[dict]:
    return [
        {"nombre": f"Referencia aprox. · {name}", "lat": lat, "lon": lon}
        for name, lat, lon in values
    ]


# Waypoints cartográficos aproximados, en orden de recorrido. Campus III sigue
# el itinerario publicado por UNACAR; los otros dos siguen referencias costeras
# visibles en materiales de Amor x Carmen y cobertura reportada, por validar.
RUTAS_SEMILLA = [
    {
        "nombre": "Ruta Costera · trazo aproximado",
        "trazo": _points([
            (18.6752, -91.7825), (18.6705, -91.7928), (18.6645, -91.7965),
            (18.6685, -91.8255), (18.6562, -91.8392), (18.6462, -91.8398),
            (18.6392, -91.8365),
        ]),
        "paradas": _references([
            ("Bivalvo", 18.6752, -91.7825),
            ("Tierra y Libertad", 18.6705, -91.7928),
            ("Malecón Costero", 18.6685, -91.8255),
            ("Calle 26", 18.6562, -91.8392),
            ("Malecón del Centro", 18.6462, -91.8398),
        ]),
    },
    {
        "nombre": "Ruta Campus III · trazo aproximado",
        "trazo": _points([
            (18.6552, -91.8148), (18.6495, -91.8112), (18.6480, -91.8152),
            (18.6512, -91.8180), (18.6558, -91.8208), (18.6602, -91.8228),
            (18.6652, -91.8165), (18.6615, -91.8060), (18.6618, -91.8012),
            (18.6518, -91.7968), (18.6455, -91.7852), (18.6368, -91.7782),
            (18.6485, -91.7798), (18.6555, -91.7718), (18.6632, -91.7598),
        ]),
        "paradas": _references([
            ("Av. Corregidora · Campus II / Zentralia", 18.6552, -91.8148),
            ("Av. 31 / Periférica Norte", 18.6558, -91.8208),
            ("Malecón de la Obrera", 18.6652, -91.8165),
            ("Boquerón del Palmar", 18.6618, -91.8012),
            ("Mercado Chechén", 18.6518, -91.7968),
            ("Renovación", 18.6455, -91.7852),
            ("Av. Contadores / Jardín Botánico", 18.6485, -91.7798),
            ("Av. Central", 18.6555, -91.7718),
            ("UNACAR Campus III", 18.6632, -91.7598),
        ]),
    },
    {
        "nombre": "Ruta Laguna & Términos · trazo esquemático",
        "trazo": _points([
            (18.6455, -91.8398), (18.6318, -91.8295), (18.6348, -91.8262),
            (18.6415, -91.8152), (18.6352, -91.8202), (18.6322, -91.8185),
            (18.6395, -91.8118), (18.6432, -91.8058),
        ]),
        "paradas": _references([
            ("Mercado AFA", 18.6455, -91.8398),
            ("La Puntilla", 18.6318, -91.8295),
            ("Miguel de la Madrid", 18.6348, -91.8262),
            ("Salitral", 18.6415, -91.8152),
            ("Manigua", 18.6322, -91.8185),
            ("Benito Juárez", 18.6432, -91.8058),
        ]),
    },
]

with (Path(__file__).with_name("route_traces.json")).open(encoding="utf-8") as _file:
    TRAZOS_CALZADOS = json.load(_file)

UNIDADES_POR_RUTA = 3


def seed_if_empty(db: Session) -> None:
    """Sincroniza rutas de demo para que DB persistentes reciban los trazos nuevos."""
    existentes = db.query(Route).order_by(Route.id).all()
    for route_id, cfg in enumerate(RUTAS_SEMILLA, start=1):
        ruta = next((r for r in existentes if r.id == route_id), None)
        if ruta is None:
            ruta = Route(id=route_id, nombre=cfg["nombre"])
            db.add(ruta)
        ruta.nombre = cfg["nombre"]
        ruta.trazo = TRAZOS_CALZADOS.get(cfg["nombre"], cfg["trazo"])
        ruta.paradas = cfg["paradas"]
    db.commit()

    if db.query(Unit).count() == 0:
        for route_id in range(1, len(RUTAS_SEMILLA) + 1):
            for n in range(1, UNIDADES_POR_RUTA + 1):
                db.add(Unit(
                    nombre=f"Unidad {((route_id - 1) * UNIDADES_POR_RUTA) + n}",
                    route_id=route_id,
                    qr_token=secrets.token_hex(6).upper(),
                    driver_token=secrets.token_hex(16),
                ))
        db.commit()
