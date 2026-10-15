"""Datos semilla: 3 rutas ficticias de Ciudad del Carmen, 3 unidades por ruta.

Nombres genéricos (Parada N), sin datos reales de personas. Tokens de demo en
.py para arrancar; en producción/deploy real deben rotarse.
"""
import secrets

from sqlalchemy.orm import Session

from .models import Route, Unit

# Coordenadas aproximadas del centro de Ciudad del Carmen (sin datos de personas)
BASE_LAT, BASE_LON = 18.6469, -91.8350


def _trazo_ruta(delta_lat: float, delta_lon: float) -> list[dict]:
    """Trazo simple en zig-zag de 6 puntos cerca del centro de la ciudad."""
    return [
        {"lat": round(BASE_LAT + delta_lat, 5), "lon": round(BASE_LON + delta_lon, 5)},
        {"lat": round(BASE_LAT + delta_lat + 0.003, 5), "lon": round(BASE_LON + delta_lon + 0.002, 5)},
        {"lat": round(BASE_LAT + delta_lat + 0.006, 5), "lon": round(BASE_LON + delta_lon, 5)},
        {"lat": round(BASE_LAT + delta_lat + 0.006, 5), "lon": round(BASE_LON + delta_lon - 0.003, 5)},
        {"lat": round(BASE_LAT + delta_lat + 0.003, 5), "lon": round(BASE_LON + delta_lon - 0.005, 5)},
        {"lat": round(BASE_LAT + delta_lat, 5), "lon": round(BASE_LON + delta_lon, 5)},
    ]


def _paradas(delta_lat: float, delta_lon: float) -> list[dict]:
    """3 paradas de ejemplo sobre el trazo con nombres genéricos."""
    trazo = _trazo_ruta(delta_lat, delta_lon)
    return [
        {"nombre": "Parada 1 - Centro", "lat": trazo[0]["lat"], "lon": trazo[0]["lon"]},
        {"nombre": "Parada 2 - Mercado", "lat": trazo[2]["lat"], "lon": trazo[2]["lon"]},
        {"nombre": "Parada 3 - Terminal", "lat": trazo[4]["lat"], "lon": trazo[4]["lon"]},
    ]


RUTAS_SEMILLA = [
    {"nombre": "Ruta 1 - Centro", "delta": (0.000, 0.000)},
    {"nombre": "Ruta 2 - Libertad", "delta": (0.008, 0.004)},
    {"nombre": "Ruta 3 - Bahía", "delta": (-0.008, -0.004)},
]

UNIDADES_POR_RUTA = 3


def seed_if_empty(db: Session) -> None:
    """Crea rutas y unidades solo si las tablas están vacías (idempotente)."""
    if db.query(Route).count() == 0:
        for i, cfg in enumerate(RUTAS_SEMILLA, start=1):
            d_lat, d_lon = cfg["delta"]
            db.add(Route(
                nombre=cfg["nombre"],
                trazo=_trazo_ruta(d_lat, d_lon),
                paradas=_paradas(d_lat, d_lon),
            ))
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
