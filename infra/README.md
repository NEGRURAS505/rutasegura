# Infraestructura (Rol 4)

## Despliegue HTTPS

`docker-compose.yml` usa `backend/Dockerfile` y espera que la raíz tenga `.env`.
El backend queda en una red interna de Compose; Caddy es
el único servicio publicado y obtiene/renueva TLS automáticamente para el
nombre DNS configurado. Antes de levantarlo, apunta el DNS `API_HOST` al
servidor y permite tráfico entrante TCP 80/443.

El proxy usa Caddy 2.11.7 (licencia Apache-2.0, compatible con MIT); revisa
la etiqueta fijada cuando actualices el despliegue. La versión se confirmó
contra la [lista oficial de releases](https://github.com/caddyserver/caddy/releases).

```powershell
$env:API_HOST = "api.ejemplo.org"
docker compose --env-file ..\.env -f .\docker-compose.yml up --build -d
```

El certificado público requiere un dominio alcanzable; para desarrollo local,
usa el backend directamente en `http://127.0.0.1:8000`. No distribuyas esa URL
HTTP en una APK Android de producción. No uses `MOCK_MODE=true` con datos
reales: los registros de demostración no representan vehículos reales.

## Controles mínimos

- Mantén `.env` fuera de Git y limita su lectura al usuario de despliegue.
- Usa tokens distintos por unidad; rota cualquier token expuesto.
- No publiques el puerto 8000 ni el puerto SQLite.
- Restringe 80/443 en el firewall a lo necesario y mantén Docker/host al día.
- Usa datos ficticios en la demo. Las alertas no sustituyen despacho humano.

El rate limiting y la validación de tokens por unidad deben implementarse en
la API; el proxy aquí no define autenticación de aplicación.

El simulador necesita `SIM_DRIVER_TOKEN` de una unidad semilla y el `unit_id`
correspondiente (por defecto `U-001`). La semilla actual genera tokens al
azar; no los pongas en el repositorio ni los envíes por un canal público.

**Pendiente de integración:** el Dockerfile actual ejecuta `uvicorn main:app`,
pero `backend/main.py` usa imports relativos (`from .db ...`). Esa combinación
no arranca como módulo de nivel superior. Rol 1 debe ajustar el comando o el
empaquetado del contenedor antes de que este despliegue sea ejecutable.
