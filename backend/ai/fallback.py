"""Respaldo por reglas simples si la Gemma API falla (sin key, cuota o red).

Mismas llaves de salida que la IA para que el contrato no cambie de forma.
"""

_KEYWORDS_ALTA = ["arma", "pistola", "punalada", "sangre", "golpe", "muerto",
                  "mata", "secuestro", "amenaz"]
_KEYWORDS_MEDIA = ["quita el dinero", "manosea", "sigue", "robar",
                   "peligro", "pelea", "borracho", "susto", "ayuda"]
_KEYWORDS_BAJO = ["prueba", "mira", "hola", "no pasa nada", "equipo"]


def _severidad_por_texto(texto: str | None, base: str) -> str:
    t = (texto or "").lower()
    if any(k in t for k in _KEYWORDS_ALTA):
        return "alta"
    if any(k in t for k in _KEYWORDS_MEDIA):
        return "media"
    if any(k in t for k in _KEYWORDS_BAJO):
        return "baja"
    return base


def triage_fallback(texto: str | None, origen: str, velocidad: float | None,
                    coincide_con_pasajero: bool) -> dict:
    """Triage por reglas: mismas llaves que Gemma (severidad, resumen, accion)."""
    if coincide_con_pasajero:
        base = "alta"
        resumen = (f"Pánico {origen}: coincide con una alerta previa del pasajero "
                   "de la misma unidad; posible conflicto en curso.")
    elif origen == "conductor":
        base = "media"
        resumen = "Pánico del conductor de la unidad; motivo sin descripción clara."
    else:
        base = "media"
        resumen = "Pánico del pasajero; sin descripción detallada del episodio."
    if velocidad is not None and velocidad > 40:
        resumen += " La unidad va a alta velocidad."

    severidad = _severidad_por_texto(texto, base)
    acciones = {
        "alta": "Contactar por radio a la unidad y avisar a la policía con el mapa abierto.",
        "media": "Llamar a la unidad por radio y observar el mapa unos minutos.",
        "baja": "Preguntar por radio; alertar solo si algo confirma el riesgo.",
    }
    return {
        "severidad": severidad,
        "resumen": resumen + " (Respaldo por reglas: IA no disponible.)",
        "accion_sugerida": acciones[severidad],
    }


CATEGORIAS_REPORTES = ("infraestructura", "unidad_en_mal_estado", "seguridad", "otro")


def reporte_fallback(texto: str | None, con_foto: bool) -> dict:
    """Categoriza por palabras clave con la regla simple y misma forma de la IA."""
    t = (texto or "").lower()
    if any(k in t for k in ["alumbrado", "coladera", "bache", "señal", "paradero", "escombro", "lámpara"]):
        categoria = "infraestructura"
    elif any(k in t for k in ["asiento roto", "unidad", "camión", "camion", "motor", "puerta", "fuego"]):
        categoria = "unidad_en_mal_estado"
    elif any(k in t for k in ["robo", "amenaza", "borracho", "pelea", "armado", "sigue"]):
        categoria = "seguridad"
    else:
        categoria = "otro"
    if any(k in t for k in ["robo", "armado", "peligro", "fuego"]):
        urgencia = "alta"
    elif any(k in t for k in ["bache", "señal", "pelea", "borracho"]):
        urgencia = "media"
    else:
        urgencia = "baja"
    return {
        "categoria": categoria,
        "descripcion": (texto or "")[:200] + (" (con foto)" if con_foto else "") +
                       " (Respaldo por reglas: IA no disponible.)",
        "urgencia": urgencia,
    }


def asistente_fallback(pregunta: str) -> dict:
    return {
        "respuesta": (f"Preguntaste: \"{pregunta}\". En este momento el asistente "
                      "no tiene datos completos (IA sin conexión), así que no puedo "
                      "confirmar posiciones exactas de las unidades."),
        "fallo": True,
    }
