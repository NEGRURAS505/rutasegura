# Trazos de rutas de demostración

La API entrega trazos dibujados sobre vialidades y referencias aproximadas para
que el mapa de la app muestre las tres rutas identificadas para Amor x Carmen.
**No es un inventario de paraderos oficiales ni una digitalización de pósteres
municipales**: no se encontró una imagen pública legible con el mapa completo.
Confirma ubicaciones y paraderos con el operador antes de usarlos para viajes.

## Referencias usadas

- **Campus III:** la [UNACAR describe el itinerario](https://www.unacar.mx/comunicacion_social_unacar/unacar/noticia_unacar.php?not=aDhTdDJYRTR4ZHM9) desde Av. Corregidora / Campus II y Zentralia, por Av. 31, Periférica Norte, Malecón de la Obrera, Boquerón del Palmar, Mercado Chechén, Isla de Tris, Renovación, Contadores y Av. Central, hasta Campus III. Sus nombres se muestran como referencias, no como paradas certificadas.
- **Costera:** notas periodísticas confirman el servicio de Malecón Costero y su conexión entre malecones ([La Jornada Maya](https://www.lajornadamaya.mx/campeche/232625/amor-x-carmen-no-tiene-permiso-para-transitar-en-rutas-ocupadas-transporte-publico-ciudad-del-carmen), [La Chispa](https://lachispa.mx/fiesta-del-mar-atrajo-a-mas-de-12-mil-turistas-en-cada-concierto/)); no publican una lista completa de calles ni paraderos.
- **Laguna & Términos:** una [nota de Por Esto!](https://www.poresto.com/media/2025/11/11/impreso-campeche-08112025_MASTER.pdf) documenta un letrero de parada con el nombre de la ruta, pero no permite recuperar el itinerario desde la foto.
- Los waypoints secundarios de Costera y Laguna & Términos son aproximaciones cartográficas de los materiales disponibles en el proyecto; no se atribuyen a un mapa municipal oficial.
- Las líneas de `backend/route_traces.json` se ajustaron a la red vial de OpenStreetMap con el servicio de ruteo OSRM. No se consulta dicho servicio al arrancar la API; los puntos están guardados localmente. Mapa y trazos llevan atribución a OpenStreetMap.

## Datos y actualización

`backend/seed.py` sincroniza las tres rutas al arrancar el backend, incluso si la
base SQLite ya tenía las rutas genéricas previas. Conserva unidades y sus
tokens; las unidades continúan ligadas a los IDs 1, 2 y 3.

Para reemplazar estas estimaciones por los recorridos correctos, se necesitan
los pósteres oficiales o una lista validada de calles y paraderos. Entonces se
actualizan `backend/route_traces.json` y `backend/seed.py` y se reconstruye el
APK para incluir los nombres de ruta recibidos por la API.
