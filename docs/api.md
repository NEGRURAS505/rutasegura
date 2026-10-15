# Contrato de la API — RutaSegura Carmen

Fuente de verdad de la API del backend. La especificación viva (OpenAPI JSON)
se sirve automáticamente en `http://localhost:8000/docs` (Swagger UI) y
`/openapi.json`. **Prohibido cambiar campos de un endpoint sin actualizar este
documento y avisar al equipo en el canal de Discord.**

- Base URL local: `http://localhost:8000` (producción vía HTTPS, desplegada por Rol 4)
- Formato: JSON UTF-8 en todas las respuestas.
- Errores: forma estándar de FastAPI `{"detail": "mensaje"}` con códigos 400/401/404/422.
- Fechas: ISO 8601 UTC (ej. `2026-10-15T18:03:00Z`).
- Los IDs son enteros autoincrementales; `unit_id` de unidades ficticias usa
  identificadores tipo `"U-001"` (string) para MOCK_MODE.

## Autenticación (simple, MVP)

- Solo los endpoints que escriben posición o pánico en nombre de una unidad
  requieren token: header `Authorization: Bearer <driver_token>`.
  - `POST /positions`
  - `POST /alerts` cuando `origen == "conductor"`
- El token por unidad se define en la tabla `units.driver_token` (datos semilla
  para demo; cada token se entrega al conductor con su unidad).
- Los endpoints del pasajero (`/trips`, `/reports`, `/assistant`, `/alerts` con
  `origen == "pasajero"`) no requieren token en el MVP. El rate limiting básico
  (`60 peticiones/minuto por IP en POST`) está activo en el backend.

## Variables de entorno relevantes (Ver `.env.example`)

| Variable | Uso |
|---|---|
| `GEMINI_API_KEY` | Llave para llamar a Gemma vía Gemini API |
| `GEMMA_MODEL` | Nombre del modelo Gemma (p. ej. `gemma-4-31b-it`) |
| `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID` | Bot de alertas |
| `MOCK_MODE` | `true` = datos de ejemplo; el backend no necesita DB poblada |
| `DATABASE_URL` | Por defecto `sqlite:////data/rutasegura.db` (en local: `./data/rutasegura.db`) |

---

## Endpoints

### POST /positions

Transmite la posición de una unidad. Requiere token de conductor.

```jsonc
// Request
{
  "unit_id": "U-001",          // string: id de la unidad
  "lat": 18.6469,              // -90..90
  "lon": -91.835,              // -180..180
  "velocidad": 12.5,           // km/h (número >= 0)
  "timestamp": "2026-10-15T18:03:00Z" // ISO 8601; si se omite usa hora del servidor
}
```

- `201` → `{"ok": true, "unit_id": "U-001"}`
- `403` token de conductor inválido · `422` validación · `401` sin header.
- Deduplicación: clave `unit_id + timestamp` (cola offline sin duplicados).

### GET /units/live

Última posición conocida de cada unidad.

```jsonc
// 200
[
  {
    "unit_id": "U-001",
    "nombre": "Unidad 1",
    "route_id": 1,
    "posicion": { "lat": 18.6469, "lon": -91.835, "velocidad": 12.5, "timestamp": "2026-10-15T18:03:00Z" }
  }
]
```

- En `MOCK_MODE=true` devuelve 3 unidades ficticias moviéndose sin depender de
  la base de datos.
- Los recorridos demo usan trazos aproximados ajustados a vialidades de
  OpenStreetMap. Las referencias no son paraderos oficiales verificados; ver
  [docs/rutas.md](rutas.md).

### GET /routes

Rutas con su trazo y paradas.

```jsonc
// 200
[
  {
    "id": 1,
    "nombre": "Ruta Costera · trazo aproximado",
    "trazo": [{ "lat": 18.646, "lon": -91.834 }],
    "paradas": [{ "nombre": "Referencia aprox. · Malecón Costero", "lat": 18.646, "lon": -91.834 }]
  }
]
```

### POST /trips

Check-in del pasajero vía QR.

```jsonc
// Request
{ "qr_token": "ABC123", "lat": 18.6469, "lon": -91.835, "alias": "Ana" }
// 201 (comprobante digital)
{
  "id": 17,
  "unit_id": "U-001",
  "nombre_unidad": "Unidad 1",
  "route_id": 1,
  "nombre_ruta": "Ruta Costera · trazo aproximado",
  "timestamp": "2026-10-15T18:11:22Z",
  "lat": 18.6469,
  "lon": -91.835,
  "alias": "Ana"
}
```

- `404` si el `qr_token` no corresponde a ninguna unidad.

### GET /trips/{id}

Devuelve el mismo objeto del comprobante · `404` si no existe.

### POST /alerts

Botón de pánico (conductor o pasajero). Dispara el triage con Gemma y el
aviso a Telegram. Si `origen == "conductor"` requiere token de conductor.

```jsonc
// Request
{ "origen": "pasajero", "unit_id": "U-001", "lat": 18.6469, "lon": -91.835, "texto": "me siento amenazado" }
// 201
{
  "id": 5,
  "origen": "pasajero",
  "unit_id": "U-001",
  "lat": 18.6469, "lon": -91.835,
  "texto": "me siento amenazado",
  "severidad_ia": "alta",            // baja | media | alta
  "resumen_ia": "Pánico confiado en la unidad…",
  "accion_sugerida": "Llamar a la unidad por radio…",
  "estado": "abierta",               // abierta | atendida | falsa_alarma
  "creada_en": "2026-10-15T18:12:00Z"
}
```

- La decisión final es del operador; el backend nunca despacha nada solo.
- Si Gemma no está disponible (sin API key, cuota o red), el triage usa el
  respaldo por reglas de `ai/fallback.py` y los campos `*_ia` **no** cambian de forma.

### GET /alerts

Lista de alertas para el panel, más nuevas primero. Filtros opcionales:
`?estado=abierta`, `?route_id=1`.

### PATCH /alerts/{id}

Estado del operador: `{"estado": "atendida"}` o `{"estado": "falsa_alarma"}`.
Devuelve la alerta actualizada · `404` si no existe · `422` estado inválido.

### POST /reports

Reporte ciudadano; categorizado por Gemma.

```jsonc
// Request (JSON, MVP; foto opcional como data URI base64)
{ "texto": "paradero con escombro", "lat": 18.647, "lon": -91.836,
  "foto_base64": "data:image/jpeg;base64,..." }
// 201
{
  "id": 9,
  "texto": "paradero con escombro",
  "categoria_ia": "infraestructura",   // infraestructura | unidad_en_mal_estado | seguridad | otro
  "descripcion_ia": "Alumbrado/caída en paradero…",
  "urgencia_ia": "media",              // baja | media | alta
  "foto_ref": "/files/reports/foto_20261015_ab12.jpg", // null si no lleva foto
  "lat": 18.647, "lon": -91.836,
  "creada_en": "2026-10-15T18:30:00Z"
}
```

- La foto se guarda en el disco del servidor (`backend/uploads/`); el campo
  `foto_ref` es la ruta relativa para que el panel la muestre. Categoría y
  urgencia con respaldo por reglas si Gemma falla.

### GET /reports

Lista de reportes para el panel (igual a la salida del POST), más nuevos primero.

### POST /assistant

Asistente en español con IA.

```jsonc
// Request
{ "pregunta": "¿dónde está la unidad 1?" }
// 200
{ "respuesta": "La Unidad 1 va por Av. Central cerca de la Parada 3…", "fallo": false }
```

- `fallo=false`: respondió Gemma · `fallo=true`: se usó el respaldo (la
  respuesta advierte que el asistente no tiene datos completos).
- El asistente recibe como contexto las posiciones y rutas actuales y **no
  inventa** datos que no estén ahí.

---

## Datos semilla (backend/seed.py)

Se crean automáticamente si las tablas están vacías:

- `units`: 3 unidades ficticias por ruta (9 en total) con tokens (`driver_token`,
  `qr_token`) de demo.
- `routes`: 3 trazos aproximados de Ciudad del Carmen con referencias
  cartográficas, no paraderos oficiales verificados (ver `docs/rutas.md`).
- `alerts`: vacía · `trips`: vacía · `reports`: vacía.

## Cambios de contrato

1. Propón el cambio a Rol 1 y, de acuerdo, actualiza `docs/api.md` y el OpenAPI resultante de FastAPI.
2. Actualiza los tests básicos de `backend/tests/`.
3. Avisa al equipo para que roles 2, 3 y 5 ajusten sus clientes; nadie cambia campos por su cuenta.
