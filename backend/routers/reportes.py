"""POST /reports y GET /reports (docs/api.md).

Foto opcional: data URI base64 en el JSON (evita dependencias de multipart en
el MVP).'backend/uploads/ con nombre determinista y devuelve foto_ref.
"""
import base64
import mimetypes
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..ai import fallback as fb
from ..ai import gemma
from ..ai.prompts import prompt_reporte
from ..models import Report
from ..schemas import ReportIn, ReportOut
from .unidades import get_db

router = APIRouter(tags=["reportes"])


def _reporte_out(r: Report) -> ReportOut:
    return ReportOut(
        id=r.id,
        texto=r.texto,
        categoria_ia=r.categoria_ia,
        descripcion_ia=r.descripcion_ia,
        urgencia_ia=r.urgencia_ia,
        foto_ref=r.foto_ref,
        lat=r.lat,
        lon=r.lon,
        creada_en=r.creada_en.isoformat().replace("+00:00", "Z"),
    )


def _guardar_foto(settings, data_uri: str) -> str | None:
    """Guarda la foto en uploads/ y devuelve la foto_ref; None si falla."""
    if not data_uri or not data_uri.startswith("data:"):
        raise HTTPException(status_code=422, detail="foto_base64 debe ser un data URI")
    try:
        meta, b64 = data_uri.split(",", 1)
        mime = meta[5:].split(";", 1)[0] or "image/jpeg"
        datos = base64.b64decode(b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="foto_base64 inválida") from exc
    if len(datos) > 6 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="La foto no puede pesar más de 6 MB")
    ext = mimetypes.guess_extension(mime) or ".jpg"
    nombre = f"foto_{datetime.now(timezone.utc):%Y%m%d}_{secrets.token_hex(4)}{ext}"
    ruta = f"{settings.uploads_dir}/{nombre}"
    from pathlib import Path

    Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(datos)
    return ruta


@router.post("/reports", status_code=201, response_model=ReportOut)
def crear_reporte(data: ReportIn, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    from ..security import check_rate_limit
    check_rate_limit(request, settings.rate_limit_per_minute)

    if data.texto is None and data.foto_base64 is None:
        raise HTTPException(status_code=422, detail="Se necesita el texto y/o la foto del reporte")

    foto_ref = None
    if data.foto_base64:
        foto_ref = _guardar_foto(settings, data.foto_base64)

    # Categorización IA con respaldo por reglas (misma forma de salida)
    resultado = None
    try:
        resultado = gemma.call_gemma(prompt_reporte(data.texto, foto_ref is not None), settings)
    except Exception:
        resultado = None
    if resultado and all(k in resultado for k in ("categoria", "descripcion", "urgencia")):
        categoria = resultado["categoria"]
        if categoria not in fb.CATEGORIAS_REPORTES:
            categoria = "otro"
        urgencia = resultado["urgencia"] if resultado["urgencia"] in ("baja", "media", "alta") else "media"
        descripcion = resultado["descripcion"]
    else:
        fallback_foto = fb.reporte_fallback(data.texto, foto_ref is not None)
        if foto_ref is not None and not data.texto:
            # Sin texto no hay palabras clave: usa urgencia media si lleva foto
            fallback_foto["urgencia"] = "media" if fallback_foto["urgencia"] == "baja" else fallback_foto["urgencia"]
            fallback_foto["descripcion"] = "Reporte con foto sin texto (Respaldo por reglas: IA no disponible.)"
        categoria = fallback_foto["categoria"]
        urgencia = fallback_foto["urgencia"]
        descripcion = fallback_foto["descripcion"]

    reporte = Report(
        texto=data.texto,
        categoria_ia=categoria,
        descripcion_ia=descripcion,
        urgencia_ia=urgencia,
        foto_ref=foto_ref,
        lat=data.lat,
        lon=data.lon,
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return _reporte_out(reporte)


@router.get("/reports", response_model=list[ReportOut])
def listar_reportes(
    request: Request,
    limite: int = Query(default=200, le=500, alias="limit"),
    db: Session = Depends(get_db),
):
    reportes = db.query(Report).order_by(Report.creada_en.desc(), Report.id.desc()).limit(limite).all()
    return [_reporte_out(r) for r in reportes]
