"""App FastAPI de RutaSegura Carmen (backend).

Correr en dev: `uvicorn main:app --reload --port 8000` (desde backend/)
Documentación interactiva: http://localhost:8000/docs  (OpenAPI del contrato)
"""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .db import make_engine, make_session_factory
from .models import Base
from .routers import alertas, asistente, reportes, unidades, viajes
from .seed import seed_if_empty

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    from .config import load_settings

    settings = load_settings()
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)

    app = FastAPI(
        title="RutaSegura Carmen API",
        version="0.1.0",
        description=(
            "Seguridad y seguimiento para el transporte urbano de Ciudad del "
            "Carmen. IA: Gemma a través de la Gemini API."
        ),
    )
    app.state.settings = settings
    app.state.SessionLocal = SessionLocal

    # CORS abierto para la demo (app móvil y panel). Rol 4 lo ajustará en deploy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Seed idempotente al arrancar (rutas + unidades si están vacías)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()

    app.include_router(unidades.router)
    app.include_router(viajes.router)
    app.include_router(alertas.router)
    app.include_router(reportes.router)
    app.include_router(asistente.router)

    @app.get("/", tags=["root"])
    def raiz():
        return {
            "proyecto": "RutaSegura Carmen",
            "docs": "/docs",
            "mock_mode": settings.mock_mode,
            "gemma_model": settings.gemma_model,
        }

    @app.get("/files/{path:path}", include_in_schema=False)
    def descargar_archivo(request: Request, path: str):
        """Sirve reportes de fotos guardadas (uploads) para el panel."""
        ruta = (Path(settings.uploads_dir) / path).resolve()
        if not str(ruta).startswith(str(Path(settings.uploads_dir).resolve())) or not ruta.is_file():
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        return FileResponse(ruta)

    return app


app = create_app()
