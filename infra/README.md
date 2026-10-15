# Infraestructura (Rol 4)

## Desarrollo local

El comando de la guía del equipo (`docker compose up --build`) usa el
`docker-compose.yml` de la raíz y publica HTTP en `localhost:8000`; úsalo solo
para desarrollo local. Desde la raíz:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Para simular posiciones, el backend exige el token Bearer de una unidad:

```powershell
$env:SIM_DRIVER_TOKEN = "<token-de-U-001>"
python .\sim\unit_simulator.py --base-url http://127.0.0.1:8000 --unit-id U-001 --count 6
```

La semilla actual genera tokens de conductor aleatorios y no ofrece una ruta
para consultarlos por API. Rol 1 debe proporcionar un método seguro de obtener
el token de demo o permitir configurarlo desde el entorno; no lo guardes en el
repositorio.

## Despliegue HTTPS

`docker-compose.yml` usa `infra/Dockerfile` y espera que la raíz tenga `.env`.
El backend queda en una red interna de Compose; Caddy es el único servicio
publicado y obtiene/renueva TLS automáticamente para el nombre DNS
configurado. Antes de levantarlo, apunta el DNS `API_HOST` al servidor y
permite tráfico entrante TCP 80/443.

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

El Dockerfile de `infra/` copia el backend como paquete `backend` y ejecuta
`uvicorn backend.main:app`, por lo que sus imports relativos funcionan sin
alterar archivos propiedad del Rol 1. El Compose de la raíz expone HTTP solo
para desarrollo local; este archivo publica el backend únicamente a través de
Caddy/HTTPS.

El panel y la aplicación móvil aún no están en el repositorio. Cuando Rol 5
entregue el panel, debe añadirse como servicio web en este Compose; la app móvil
se compila como APK y consume el dominio HTTPS.
