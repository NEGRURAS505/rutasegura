"""Telegram: aviso de pánico al bot que simula a la policía.

Si TELEGRAM_TOKEN / TELEGRAM_CHAT_ID no están configurados solo registra en el
log (para demo/local). Nunca se bloquea el flujo del backend ante fallos.
"""
import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_TIMEOUT = 10


def notificar_panico(settings, alerta_dict: dict) -> bool:
    """Envía el resumen de la alerta al chat configurado. Devuelve ok/fail."""
    if not settings.telegram_token or not settings.telegram_chat_id:
        logger.info("TELEGRAM sin configurar; alerta id=%s solo queda en el panel.",
                    alerta_dict.get("id"))
        return False

    texto = (
        f"🚨 PÁNICO — RutaSegura\n"
        f"Origen: {alerta_dict.get('origen', '?')}\n"
        f"Unidad: {alerta_dict.get('unit_id') or 'no indicada'}\n"
        f"Severidad (IA): {alerta_dict.get('severidad_ia') or 's/d'}\n"
        f"Resumen: {alerta_dict.get('resumen_ia') or '-'}\n"
        f"Acción sugerida: {alerta_dict.get('accion_sugerida') or '-'}\n"
        f"Ubicación: {alerta_dict.get('lat')}, {alerta_dict.get('lon')}"
    )
    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    try:
        r = httpx.post(url, json={"chat_id": settings.telegram_chat_id, "text": texto},
                       timeout=TELEGRAM_TIMEOUT)
        r.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("No se pudo enviar a Telegram: %s", exc)
        return False
