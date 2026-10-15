# RutaSegura Carmen 🚌🛡️

Prototipo de hackathon: plataforma de seguridad y seguimiento para el
transporte urbano de Ciudad del Carmen, Campeche, México. Sustituye al boleto
de papel por un comprobante digital de viaje, rastrea la unidad en tiempo real
y conecta conductores y pasajeros con el operador a través de botones de
pánico e IA que triagea los eventos.

## Modelo de IA

El núcleo de IA del proyecto usa **Gemma** a través de la **Gemini API**.

- Modelo por defecto: [`gemma-4-31b-it`](https://ai.google.dev/gemma/docs/core/model_card_4)
  (configurable con la variable `GEMMA_MODEL`; el nombre no está fijo en el código).
- Licencia: [Apache 2.0](https://ai.google.dev/gemma/apache_2) — el modelo es
  una parte importante del proyecto: triage de pánicos, categorización de
  reportes ciudadanos y asistente en español.
- La decisión final ante una alerta siempre es humana (el operador del panel).

> ⏳ README final pendiente de Rol 5 (diagrama de arquitectura, guion y video).

## Cómo correr el backend

```bash
cp .env.example .env      # agrega tus llaves (no las subas al repo)
docker compose up --build
# API: http://localhost:8000/docs  (Swagger/OpenAPI)
```

Con `MOCK_MODE=true` el backend responde con datos de ejemplo sin necesidad de
base de datos poblada ni dispositivos reales (ver docs/api.md).

## Estructura del repo

```
backend/   FastAPI + SQLite + IA (Rol 1)      ← este PR
app/       Capacitor Android (Roles 2 y 3)    ← pendiente
dashboard/ Panel del operador (Rol 5)         ← pendiente
sim/       Simulador de unidades (Rol 4)      ← pendiente
infra/     Despliegue y HTTPS (Rol 4)         ← pendiente
docs/      api.md (contrato), arquitectura    ← pendiente
```

## Limitaciones conocidas (MVP)

- Piloto pensado para 1 camión en 1 ruta; los datos semilla son ficticios.
- No hay pagos, saldos, NFC, RFID ni hardware ESP32 en el MVP — todo con celulares.
- Autenticación simple por token por unidad; sin roles por usuario todavía.
- HTTPS lo añade el despliegue (Rol 4); Android no acepta HTTP plano por defecto.

## Licencia

MIT — ver [LICENSE](LICENSE).
