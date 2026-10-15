"""Autenticación simple y rate limiting básico (MVP Rol 1).

- Token por unidad: header Authorization: Bearer <driver_token> para los
  endpoints que actúan a nombre del conductor.
- Rate limiting: ventana fija por IP + ruta en memoria (suficiente para la
  demo; para despliegue real Rol 4 puede sustituirlo por proxy/nginx).
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .models import Unit

# {ruta: {ip: deque de timestamps}} — memoria del proceso, se reinicia al reiniciar
_VENTANAS: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(deque))


def get_unit_by_driver_token(db: Session, header_auth: str | None) -> Unit:
    """Dependencia de conductor: Bearer <driver_token> válido o 403."""
    if not header_auth or not header_auth.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Falta token de conductor")
    token = header_auth.removeprefix("Bearer ").strip()
    unit = db.query(Unit).filter(Unit.driver_token == token).one_or_none()
    if unit is None:
        raise HTTPException(status_code=403, detail="Token de conductor inválido")
    return unit


def check_rate_limit(request: Request, max_por_minuto: int) -> None:
    """Ventana fija de 60s por (ruta, IP). Láncera 429 si excede."""
    key = request.url.path
    ip = request.client.host if request.client else "desconocido"
    ahora = time.monotonic()
    ventana = _VENTANAS[key][ip]
    ventana.append(ahora)
    while ventana and ahora - ventana[0] > 60.0:
        ventana.popleft()
    if len(ventana) > max_por_minuto:
        raise HTTPException(status_code=429, detail="Demasiadas peticiones; intenta en un minuto")
