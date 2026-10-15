"""POST /positions, GET /units/live y GET /routes (docs/api.md)."""
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import load_settings
from ..db import make_session_factory
from ..models import Position, Route
from ..schemas import PositionIn, RouteOut, UnitLiveOut
from ..security import check_rate_limit, get_unit_by_driver_token
from .. import mock

router = APIRouter(tags=["unidades"])


def get_db(request: Request) -> Session:
    factory: make_session_factory = request.app.state.SessionLocal
    db = factory()
    try:
        yield db
    finally:
        db.close()


def unit_id_str(unit_id: int | str) -> str:
    """ID de unidad serializado SIEMPRE como string U-XXX (contrato)."""
    if isinstance(unit_id, str):
        return unit_id
    return f"U-{unit_id:03d}"


@router.post("/positions", status_code=201)
def crear_position(
    data: PositionIn,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    settings = request.app.state.settings
    check_rate_limit(request, settings.rate_limit_per_minute)
    unidad = get_unit_by_driver_token(db, authorization)
    if unit_id_str(unidad.id) != data.unit_id:
        raise HTTPException(status_code=403, detail="El token no corresponde a esta unidad")

    ts = data.timestamp
    if ts:
        try:
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=422, detail="timestamp inválido (formato ISO 8601)") from None
    else:
        timestamp = datetime.now().astimezone()

    posicion = Position(unit_id=data.unit_id, lat=data.lat, lon=data.lon,
                        velocidad=data.velocidad, timestamp=timestamp)
    db.add(posicion)
    db.commit()
    return {"ok": True, "unit_id": data.unit_id}


@router.get("/units/live", response_model=list[UnitLiveOut])
def units_live(request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    if settings.mock_mode:
        return mock.mock_units_live(db)

    # Última posición por unidad: recorremos las posiciones en orden asc y
    # sobrescribimos el dict por unit_id.
    ultimas: dict[str, Position] = {}
    for p in db.query(Position).order_by(Position.timestamp.asc()).all():
        ultimas[p.unit_id] = p

    from ..models import Unit

    salida = []
    for unidad in db.query(Unit).order_by(Unit.id).all():
        uid = unit_id_str(unidad.id)
        p = ultimas.get(uid)
        salida.append({
            "unit_id": uid,
            "nombre": unidad.nombre,
            "route_id": unidad.route_id,
            "posicion": None if p is None else {
                "lat": p.lat, "lon": p.lon, "velocidad": p.velocidad,
                "timestamp": p.timestamp.isoformat().replace("+00:00", "Z"),
            },
        })
    return salida


@router.get("/routes", response_model=list[RouteOut])
def listar_routes(request: Request, db: Session = Depends(get_db)):
    return [
        RouteOut(id=r.id, nombre=r.nombre, trazo=r.trazo, paradas=r.paradas)
        for r in db.query(Route).order_by(Route.id).all()
    ]
