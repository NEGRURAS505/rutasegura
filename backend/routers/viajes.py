"""POST /trips (check-in con qr_token) y GET /trips/{id} (docs/api.md)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..models import Route, Trip, Unit
from ..schemas import TripIn, TripOut
from .unidades import get_db, unit_id_str

router = APIRouter(tags=["viajes"])


def _comprobante(db: Session, trip: Trip) -> TripOut:
    """Arma el comprobante digital con nombres de unidad y ruta."""
    unidad = db.query(Unit).filter(Unit.id == _unit_int(trip.unit_id)).one_or_none()
    ruta = db.query(Route).filter(Route.id == trip.route_id).one_or_none() if trip.route_id else None
    return TripOut(
        id=trip.id,
        unit_id=trip.unit_id,
        nombre_unidad=unidad.nombre if unidad else (trip.unit_id or "?"),
        route_id=trip.route_id,
        nombre_ruta=ruta.nombre if ruta else None,
        timestamp=trip.timestamp.isoformat().replace("+00:00", "Z"),
        lat=trip.lat,
        lon=trip.lon,
        alias=trip.alias_opcional,
    )


def _unit_int(unit_id: str) -> int:
    """'U-003' -> 3. Si no trae formato, falla con ValueError."""
    return int(str(unit_id).removeprefix("U-"))


@router.post("/trips", status_code=201, response_model=TripOut)
def crear_trip(data: TripIn, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    check_rate_limit_dep(request, settings)
    unidad = db.query(Unit).filter(Unit.qr_token == data.qr_token.upper()).one_or_none()
    if unidad is None:
        raise HTTPException(status_code=404, detail="QR no corresponde a ninguna unidad")

    trip = Trip(
        unit_id=unit_id_str(unidad.id),
        route_id=unidad.route_id,
        lat=data.lat,
        lon=data.lon,
        alias_opcional=data.alias,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return _comprobante(db, trip)


@router.get("/trips/{trip_id}", response_model=TripOut)
def obtener_trip(trip_id: int, request: Request, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    return _comprobante(db, trip)


def check_rate_limit_dep(request: Request, settings) -> None:
    from ..security import check_rate_limit
    check_rate_limit(request, settings.rate_limit_per_minute)
