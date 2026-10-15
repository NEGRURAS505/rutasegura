"""Tests básicos del contrato docs/api.md.

Se construye la app por request a un archivo SQLite temporal con MOCK_MODE=true
y sin GEMINI_API_KEY (así el triage debe ir por el fallback de reglas).
"""
import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Debe configurarse ANTES de importar main (pydantic-settings lee .env/env)
TESTS_DIR = Path(__file__).parent


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("datos")
    assets = tmp_path_factory.mktemp("assets")

    import os

    os.environ["MOCK_MODE"] = "true"
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["GEMMA_MODEL"] = "gemma-4-31b-it"
    os.environ["TELEGRAM_TOKEN"] = ""
    os.environ["TELEGRAM_CHAT_ID"] = ""
    os.environ["DATABASE_URL"] = f"sqlite:///./{(tmp / 'rutasegura.db')}"

    # Recarga de módulos para que la app tome los env de prueba
    import sys

    for mod in [m for m in sys.modules if m.startswith("backend")]:
        del sys.modules[mod]
    from backend.main import create_app

    app = create_app()
    app.state.settings.uploads_dir = str(assets)
    with TestClient(app) as c:
        yield c


def _token_conductor(client) -> str:
    """Sujeta el driver_token de la primera unidad vía DB (fixture helper)."""
    from backend.config import load_settings
    from backend.db import make_engine, make_session_factory
    from backend.models import Unit

    settings = load_settings()
    engine = make_engine(settings.database_url)
    db = make_session_factory(engine)()
    unidad = db.query(Unit).order_by(Unit.id).first()
    token = unidad.driver_token
    db.close()
    return token


def test_raiz_y_mock_mode(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["mock_mode"] is True


def test_lista_rutas_semilla(client):
    r = client.get("/routes")
    assert r.status_code == 200
    rutas = r.json()
    assert len(rutas) == 3
    for ruta in rutas:
        assert ruta["trazo"] and ruta["paradas"]
        assert all("nombre" in p and "lat" in p and "lon" in p for p in ruta["paradas"])


def test_units_live_mock(client):
    r = client.get("/units/live")
    assert r.status_code == 200
    unidades = r.json()
    assert len(unidades) >= 3
    for u in unidades:
        assert u["unit_id"].startswith("U-")
        assert u["posicion"] is not None
        assert -90 <= u["posicion"]["lat"] <= 90


def test_positions_requiere_token(client):
    payload = {"unit_id": "U-001", "lat": 18.6469, "lon": -91.835, "velocidad": 10}
    assert client.post("/positions", json=payload).status_code == 403


def test_positions_ok_y_sin_duplicados_sobre_unit_invalida(client):
    token = _token_conductor(client)
    # La unidad real del token es la 1; con otro unit_id no corresponde: 403
    r = client.post(
        "/positions",
        json={"unit_id": "U-002", "lat": 18.6, "lon": -91.8, "velocidad": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403

    r = client.post(
        "/positions",
        json={"unit_id": "U-001", "lat": 18.6469, "lon": -91.835, "velocidad": 12.5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201 and r.json() == {"ok": True, "unit_id": "U-001"}


def test_trip_checkin_y_comprobante(client):
    # qr_token de demo se tomo de datos semilla vía DB
    from backend.config import load_settings
    from backend.db import make_engine, make_session_factory
    from backend.models import Unit

    settings = load_settings()
    db = make_session_factory(make_engine(settings.database_url))()
    qr = db.query(Unit).order_by(Unit.id).first().qr_token
    db.close()

    r = client.post("/trips", json={"qr_token": qr, "lat": 18.6469, "lon": -91.835, "alias": "Ana"})
    assert r.status_code == 201
    comprobante = r.json()
    assert comprobante["nombre_unidad"].startswith("Unidad")
    assert comprobante["alias"] == "Ana"
    trip_id = comprobante["id"]

    r = client.get(f"/trips/{trip_id}")
    assert r.status_code == 200 and r.json()["id"] == trip_id
    assert client.get("/trips/99999").status_code == 404
    assert client.post("/trips", json={"qr_token": "NOEXISTE"}).status_code == 404


def test_alerta_panico_triage_fallback_y_estados(client):
    # Pánico de pasajero (unidades mock no requieren token)
    r = client.post("/alerts", json={
        "origen": "pasajero", "unit_id": "U-001",
        "lat": 18.6469, "lon": -91.835, "texto": "alguien me amenazó en el camión",
    })
    assert r.status_code == 201
    a = r.json()
    assert a["estado"] == "abierta"
    assert a["severidad_ia"] in ("baja", "media", "alta")
    assert "Respaldo por reglas" in a["resumen_ia"]  # sin API key => fallback
    alert_id = a["id"]

    r = client.patch(f"/alerts/{alert_id}", json={"estado": "atendida"})
    assert r.status_code == 200 and r.json()["estado"] == "atendida"
    r = client.patch(f"/alerts/{alert_id}", json={"estado": "falsa_alarma"})
    assert r.json()["estado"] == "falsa_alarma"
    assert client.patch("/alerts/9999", json={"estado": "atendida"}).status_code == 404

    # Conductor sin token: 403
    assert client.post("/alerts", json={"origen": "conductor", "texto": "prueba"}).status_code == 403


def test_alerta_conductor_con_token_usa_su_unidad(client):
    token = _token_conductor(client)
    r = client.post(
        "/alerts",
        json={"origen": "conductor", "texto": "prueba de radio"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    assert r.json()["unit_id"] == "U-001"


def test_reporte_con_y_sin_foto(client):
    # Solo texto
    r = client.post("/reports", json={"texto": "hay un bache enorme en la parada", "lat": 18.647, "lon": -91.836})
    assert r.status_code == 201
    rep = r.json()
    assert rep["categoria_ia"] in ("infraestructura", "unidad_en_mal_estado", "seguridad", "otro")
    assert rep["urgencia_ia"] in ("baja", "media", "alta")

    # Con foto (data URI mínima PNG 1x1)
    png = base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode()
    r = client.post("/reports", json={"texto": "puerta de la unidad dañada", "foto_base64": "data:image/png;base64," + png})
    assert r.status_code == 201
    rep = r.json()
    assert rep["foto_ref"] is not None
    # Descarga de foto servida por /files
    nombre = rep["foto_ref"].split("/")[-1]
    assert client.get(f"/files/{nombre}").status_code == 200

    # Nada de texto ni foto: 422
    assert client.post("/reports", json={"lat": 18.6, "lon": -91.8}).status_code == 422


def test_asistente_responde_en_espanol(client):
    r = client.post("/assistant", json={"pregunta": "¿dónde pasa la unidad 1?"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["respuesta"], str) and len(data["respuesta"]) > 5
    assert data["fallo"] is True  # sin API key: respaldo honesto
