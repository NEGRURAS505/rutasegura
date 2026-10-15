# Amor X Carmen Movi App

APK piloto de Android con modos Pasajero y Conductor. El modo Pasajero incluye
mapa en vivo, escaneo QR/check-in, alerta, reporte y asistente. El modo
Conductor transmite GPS con servicio en primer plano, cola local de posiciones
sin conexión y botón de pánico con confirmación de dos segundos.

## APK de demostración

El APK debug está en:

`android/app/build/outputs/apk/debug/app-debug.apk`

Instálalo en Android y permite la instalación desde esa fuente si el sistema lo
solicita. La primera vez, concede cámara al escanear un QR y ubicación; para el
modo Conductor configura la ubicación como **Permitir siempre** y permite las
notificaciones para mantener visible el servicio.

## Backend

El APK apunta por defecto a `http://10.0.2.2:8000` (backend en el host cuando se
usa el emulador Android). En un teléfono real, usa ⚙ en la app para ingresar la
dirección LAN de la computadora que ejecuta el backend, por ejemplo
`http://192.168.1.20:8000`. El permiso HTTP plano solo está habilitado en el
build debug; un despliegue real debe usar HTTPS.

El modo Conductor requiere el token asignado a la unidad. La cola guarda puntos
por clave `unit_id + timestamp` y los reenvía en orden al recuperar conexión.

## Compilar

Requisitos: Node.js, JDK 17 o superior, Android SDK con Platform 35 y Build
Tools 34.0.0. Configura `JAVA_HOME` y `ANDROID_HOME`, instala dependencias y
compila:

```powershell
npm ci
npm run apk:debug
```

El APK resultante es una build debug firmada automáticamente para demostración;
no es un paquete de release para distribución en tiendas.
