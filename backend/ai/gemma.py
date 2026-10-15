"""Cliente de Gemma a través de la Gemini API (REST generateContent).

- El nombre del modelo SIEMPRE viene de settings.gemma_model (env GEMMA_MODEL).
- Pide JSON estricto con generationConfig.responseMimeType (camelCase).
- Autenticación por header x-goog-api-key (la llave no va en la URL).
- Un reintento ante fallos transitorios; si no hay clave, cuota (429) o red,
  devuelve None para que quien llama use ai/fallback.py.
"""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

TIMEOUT_CALL = 20  # segundos


def call_gemma(prompt: str, settings) -> dict | None:
    """Devuelve el JSON parseado o None si no se pudo (usa fallback)."""
    if not settings.gemini_api_key:
        logger.info("GEMINI_API_KEY vacía: usando fallback por reglas")
        return None

    url = f"{settings.gemini_url}/models/{settings.gemma_model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 512,
        },
    }
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}

    for intento in range(2):
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=TIMEOUT_CALL)
            if r.status_code == 429:
                logger.warning("Gemini API sin cuota (429): usando fallback")
                return None
            r.raise_for_status()
            data = r.json()
            texto = data["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_json(texto)
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Fallo llamando a Gemma (intento %d): %s", intento + 1, exc)
            if intento == 0:
                continue  # un reintento ante fallos transitorios
    return None


def _parse_json(texto: str) -> dict:
    """Acepta JSON puro o JSON rodeado de texto/r bash fences."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        limpio = limpio.strip("`")
        if limpio.startswith("json"):
            limpio = limpio[4:]
        limpio = limpio.strip()
    return json.loads(limpio)
