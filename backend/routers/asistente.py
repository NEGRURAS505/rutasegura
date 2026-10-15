"""POST /assistant (docs/api.md): asistente en español con datos reales.

Arma un CONTEXTO con las posiciones y rutas actuales, llama a Gemma y aplica
respaldo por reglas si falla (fallo=true en la respuesta).
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..ai import fallback as fb
from ..ai import gemma
from ..ai.prompts import prompt_asistente
from ..models import Position, Route, Unit
from ..schemas import AssistantIn, AssistantOut
from .unidades import get_db, unit_id_str

router = APIRouter(tags=["asistente"])


def _construir_contexto(db: Session, mock_mode: bool = False) -> str:
    """Últimas posiciones por unidad + nombres de rutas. NO incluye datos personales."""
    if mock_mode:
        from .. import mock
        return "\n".join(
            f"{u['nombre']} (id {u['unit_id']}): lat {u['posicion']['lat']:.5f}, "
            f"lon {u['posicion']['lon']:.5f}, velocidad {u['posicion']['velocidad']:.0f} km/h"
            for u in mock.mock_units_live(db)
        )
    ultimas: dict[str, Position] = {}
    for p in db.query(Position).order_by(Position.timestamp.asc()).all():
        ultimas[p.unit_id] = p

    lineas = []
    for unidad in db.query(Unit).order_by(Unit.id).all():
        uid = unit_id_str(unidad.id)
        p = ultimas.get(uid)
        if p:
            lineas.append(
                f"{unidad.nombre} (id {uid}): lat {p.lat:.5f}, lon {p.lon:.5f}, "
                f"velocidad {p.velocidad:.0f} km/h"
            )
        else:
            lineas.append(f"{unidad.nombre} (id {uid}): sin posición reportada")
    ruta_lineas = [
        f"Ruta {r.id}: {r.nombre} con {len(r.paradas)} paradas"
        for r in db.query(Route).order_by(Route.id).all()
    ]
    return "\n".join(lineas + ruta_lineas)


@router.post("/assistant", response_model=AssistantOut)
def consultar(request: Request, data: AssistantIn, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    from ..security import check_rate_limit
    check_rate_limit(request, settings.rate_limit_per_minute)

    contexto = _construir_contexto(db, mock_mode=settings.mock_mode)
    resultado = None
    try:
        resultado = gemma.call_gemma(prompt_asistente(data.pregunta, contexto), settings)
    except Exception:
        resultado = None

    if resultado and isinstance(resultado.get("respuesta"), str) and resultado["respuesta"].strip():
        return AssistantOut(respuesta=resultado["respuesta"].strip(), fallo=False)
    fb_resp = fb.asistente_fallback(data.pregunta)
    return AssistantOut(respuesta=fb_resp["respuesta"], fallo=True)
