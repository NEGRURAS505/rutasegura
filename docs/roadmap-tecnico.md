# Hoja de ruta técnica de infraestructura

Alcance Rol 4: despliegue, HTTPS, seguridad operativa, simulador y preparación
de pruebas de campo. El simulador usa tres trazos ficticios y solo envía datos
de demostración.

## Antes de la prueba de campo

1. Desplegar una API accesible por HTTPS y configurar tokens individuales.
2. Verificar que no se exponen SQLite ni el puerto interno del backend.
3. Confirmar con Roles 1 y 2 el esquema de autenticación y el tratamiento de
   posiciones repetidas (`unit_id` + `timestamp`) antes de probar reintentos.
4. Hacer un recorrido controlado con consentimiento, observador y un canal de
   comunicación alterno; registrar pérdida de red, latencia y batería.
5. Probar el flujo de alerta con datos de prueba y confirmar recepción en el
   panel/Telegram con el equipo responsable.

## Evolución

- Piloto inicial: un teléfono Android y una ruta; medir cobertura, precisión,
  autonomía y frecuencia de posiciones.
- Escala siguiente: tres rutas y nueve unidades; revisar retención de datos,
  monitoreo y recuperación ante reinicios.
- Futuro: evaluar 4G dedicado, LoRa o ESP32 únicamente si las mediciones del
  piloto muestran una necesidad. La integración con cámaras/C4 requiere
  acuerdos, revisión de privacidad y una interfaz autorizada; queda fuera del
  MVP.

## Simulador

Desde la raíz del repositorio:

```powershell
python .\sim\unit_simulator.py --base-url http://127.0.0.1:8000 --count 6
python .\sim\unit_simulator.py --base-url https://api.ejemplo.org --unit-id U-001 --token $env:SIM_DRIVER_TOKEN --count 6 --panic
```

El segundo comando crea una alerta de demostración después de las posiciones.
Los campos corresponden al contrato proporcionado en `CONTEXT.md`; si el
contrato compartido cambia, actualizar el simulador coordinando con Rol 1.
