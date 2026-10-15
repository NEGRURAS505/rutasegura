"""POST /alerts (pánico), GET /alerts y PATCH /alerts/{id} (docs/api.md).

POST dispara: triage con Gemma (o respaldo por reglas) + aviso a Telegram.
La decisión final siempre es humana (operador en el panel).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..ai import fallback as fb
from ..ai import gemma
from ..ai.prompts import prompt_triage
from ..models import Alert, Position, Unit
from ..schemas import AlertEstadoIn, AlertIn, AlertOut
from ..telegram import notificar_panico
from .unidades import get_db, unit_id_str

router = APIRouter(tags=["alertas"])


def _alerta_out(alerta: Alert) -> AlertOut:
    return AlertOut(
        id=alerta.id,
        origen=alerta.origen,
        unit_id=alerta.unit_id,
        lat=alerta.lat,
        lon=alerta.lon,
        texto=alerta.texto,
        severidad_ia=alerta.severidad_ia,
        resumen_ia=alerta.resumen_ia,
        accion_sugerida=alerta.accion_sugerida,
        estado=alerta.estado,
        creada_en=alerta.creada_en.isoformat().replace("+00:00", "Z"),
    )


@router.post("/alerts", status_code=201, response_model=AlertOut)
def crear_alerta(data: AlertIn, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    from ..security import check_rate_limit
    check_rate_limit(request, settings.rate_limit_alerts_per_minute)

    # Token de conductor obligatorio si el pánico viene de la app del conductor
    if data.origen == "conductor":
        token = request.headers.get("authorization")
        unidad_token = _unidad_por_token(db, token)
        if unidad_token is None:
            raise HTTPException(status_code=403, detail="Token de conductor inválido")
        if data.unit_id and unit_id_str(unidad_token.id) != data.unit_id:
            raise HTTPException(status_code=403, detail="El token no corresponde a esta unidad")
        data.unit_id = data.unit_id or unit_id_str(unidad_token.id)

    # Velocidad actual de la unidad y alerta previa del pasajero (contexto IA)
    velocidad: float | None = None
    coincide_pasajero = False
    if data.unit_id:
        ult = (
            db.query(Position)
            .filter(Position.unit_id == data.unit_id)
            .order_by(Position.timestamp.desc())
            .first()
        )
        if ult:
            velocidad = ult.velocidad
        previa = (
            db.query(Alert)
            .filter(Alert.unit_id == data.unit_id, Alert.origen == "pasajero",
                    Alert.estado == "abierta")
            .order_by(Alert.creada_en.desc())
            .first()
        )
        coincide_pasajero = previa is not None

    # 1) Triage IA (con reintento interno) 2) respaldo por reglas si falla
    resultado = _triage(settings, data, velocidad, coincide_pasajero)

    alerta = Alert(
        origen=data.origen,
        unit_id=data.unit_id,
        lat=data.lat,
        lon=data.lon,
        texto=data.texto,
        severidad_ia=resultado["severidad"],
        resumen_ia=resultado["resumen"],
        accion_sugerida=resultado["accion_sugerida"],
        estado="abierta",
    )
    db.add(alerta)
    db.commit()
    db.refresh(alerta)

    out = _alerta_out(alerta)
    notificar_panico(settings, out.model_dump())
    return out


def _triage(settings, data: AlertIn, velocidad: float | None, coincide: bool) -> dict:
    prompt = prompt_triage(data.texto, data.origen, velocidad, coincide)
    try:
        resultado = gemma.call_gemma(prompt, settings)
    except Exception:  # protección extra: la IA nunca rompe el flujo
        resultado = None
    if resultado and all(k in resultado for k in ("severidad", "resumen", "accion_sugerida")):
        return resultado
    return fb.triage_fallback(data.texto, data.origen, velocidad, coincide)


def _unidad_por_token(db: Session, header: str | None) -> Unit | None:
    if not header or not header.startswith("Bearer "):
        return None
    token = header.removeprefix("Bearer ").strip()
    return db.query(Unit).filter(Unit.driver_token == token).one_or_none()


@router.get("/alerts", response_model=list[AlertOut])
def listar_alertas(
    request: Request,
    estado: str | None = Query(default=None),
    route_id: int | None = Query(default=None),
    limit: int = Query(default=200, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Alert)
    if estado:
        q = q.filter(Alert.estado == estado)
    alertas = q.order_by(Alert.creada_en.desc(), Alert.id.desc()).limit(limit).all()
    if route_id is not None:
        # Filtramos por ruta vía las unidades de esa ruta (mock y DB real)
        uids = {unit_id_str(u.id) for u in db.query(Unit).filter(Unit.route_id == route_id).all()}
        alertas = [a for a in alertas if a.unit_id in uids]
    return [_alerta_out(a) for a in alertas]


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def actualizar_alerta(
    alert_id: int,
    data: AlertEstadoIn,
    request: Request,
    db: Session = Depends(get_db),
):
    alerta = db.query(Alert).filter(Alert.id == alert_id).one_or_none()
    if alerta is None:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    alerta.estado = data.estado
    db.commit()
    db.refresh(alerta)
    return _alerta_out(alerta)
