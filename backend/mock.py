"""MOCK_MODE: respuestas de ejemplo sin depender del backend real.

Genera unidades ficticias moviéndose a lo largo del trazo de su ruta
(deterministas respecto del tiempo) para que app y panel avancen en Fase A.
"""
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .models import Route, Unit

VELOCIDAD_MOCK = 12.0  # km/h de vista para la demo
SEGUNDOS_POR_TRAMO = 25.0


def _punto_en_trazo(trazo: list[dict], indice: float) -> dict:
    """Interpola linealmente el índice continuo `indice` sobre el trazo (ciclo)."""
    if len(trazo) < 2:
        return {"lat": 18.6469, "lon": -91.8350}
    n = len(trazo) - 1
    pos = indice % n
    i0 = int(pos)
    i1 = min(i0 + 1, n)
    f = pos - i0
    a, b = trazo[i0], trazo[i1]
    return {
        "lat": round(a["lat"] + f * (b["lat"] - a["lat"]), 5),
        "lon": round(a["lon"] + f * (b["lon"] - a["lon"]), 5),
    }


def mock_units_live(db: Session) -> list[dict]:
    """GET /units/live en MOCK_MODE: unidades ficticias moviéndose.

    El punto de cada unidad depende del tiempo con un desfase por unidad, para
    que se vean desincronizadas y el mapa aparezca vivo.

    Devuelve objetos con el mismo shape que producida la DB real: unit_id es
    string ("U-001") según el contrato docs/api.md.
    """
    units = db.query(Unit).order_by(Unit.id).all()
    routes = {r.id: r for r in db.query(Route).all()}
    now = time.time()
    salida = []
    for i, u in enumerate(units):
        r = routes.get(u.route_id)
        trazo = r.trazo if r else []
        # Desfase por unidad; un tramo del trazo dura SEGUNDOS_POR_TRAMO
        indice = (now / SEGUNDOS_POR_TRAMO) + i * 2.0
        punto = _punto_en_trazo(trazo, indice)
        ahora_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        salida.append({
            "unit_id": f"U-{u.id:03d}",
            "nombre": u.nombre,
            "route_id": u.route_id,
            "posicion": {
                "lat": punto["lat"],
                "lon": punto["lon"],
                "velocidad": VELOCIDAD_MOCK,
                "timestamp": ahora_iso,
            },
        })
    return salida
