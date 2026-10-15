import { Capacitor, CapacitorHttp, registerPlugin } from '@capacitor/core';
import { LocalNotifications } from '@capacitor/local-notifications';
import { CapacitorBarcodeScanner, CapacitorBarcodeScannerCameraDirection, CapacitorBarcodeScannerTypeHint } from '@capacitor/barcode-scanner';
import type { BackgroundGeolocationPlugin, Location as DeviceLocation, CallbackError } from '@capacitor-community/background-geolocation';
import { Map as MapLibreMap, Marker, NavigationControl, Popup, type GeoJSONSource, type Map as LibreMap, type Marker as MapMarker } from 'maplibre-gl';
import './style.css';

type UnitLive = {
  unit_id: string;
  nombre: string;
  route_id: number | null;
  posicion: { lat: number; lon: number; velocidad: number; timestamp: string } | null;
};
type Route = { id: number; nombre: string; trazo: { lat: number; lon: number }[]; paradas: { nombre: string; lat: number; lon: number }[] };
type PositionPayload = { unit_id: string; lat: number; lon: number; velocidad: number; timestamp: string };
type QueuedPosition = { key: string; queuedAt: number; payload: PositionPayload };
type ApiRequest = { method: 'GET' | 'POST' | 'PATCH'; path: string; body?: unknown; token?: string };
type MapPoint = { lat: number; lon: number };
type NamedStop = MapPoint & { nombre: string };

const BackgroundGeolocation = registerPlugin<BackgroundGeolocationPlugin>('BackgroundGeolocation');
const routeColors = ['#e6007e', '#007fae', '#b56b00'];
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const apiState = $('api-state');
const backendInput = $('api-base-url') as HTMLInputElement;
const settingsDialog = $('settings-dialog') as HTMLDialogElement;
const defaultApi = import.meta.env.VITE_API_BASE_URL || 'http://10.0.2.2:8000';
let apiBase = localStorage.getItem('rutasegura.api') || defaultApi;
let liveUnits: UnitLive[] = [];
let routes: Route[] = [];
let map: LibreMap | null = null;
const unitMarkers = new Map<string, MapMarker>();
const stopMarkers = new Map<string, MapMarker>();
let passengerMarker: MapMarker | null = null;
let passengerLocationWatch: number | null = null;
let passengerPosition: MapPoint | null = null;
let routesFit = false;
let trackingId: string | null = null;
let lastLocation: DeviceLocation | null = null;
let currentUnit = localStorage.getItem('rutasegura.unit') || 'U-001';
let currentRoute = Number(localStorage.getItem('rutasegura.route') || 1);
let driverToken = localStorage.getItem('rutasegura.driver-token') || '';
let shiftTimer: number | null = null;
let gpsFixTimeout: number | null = null;
let queueDb: IDBDatabase | null = null;
let lastPositionKey = '';
let flushBusy = false;

function nativeRequest<T>(request: ApiRequest): Promise<T> {
  const url = `${apiBase.replace(/\/$/, '')}${request.path}`;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (request.body !== undefined) headers['Content-Type'] = 'application/json';
  if (request.token) headers.Authorization = `Bearer ${request.token}`;
  if (Capacitor.isNativePlatform()) {
    return CapacitorHttp.request({
      url,
      method: request.method,
      headers,
      data: request.body,
      connectTimeout: 10000,
      readTimeout: 15000,
    }).then((response) => {
      if (response.status < 200 || response.status >= 300) {
        throw new Error(`HTTP ${response.status}: ${JSON.stringify(response.data)}`);
      }
      return response.data as T;
    });
  }
  return fetch(url, {
    method: request.method,
    headers,
    body: request.body === undefined ? undefined : JSON.stringify(request.body),
  }).then(async (response) => {
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${JSON.stringify(data)}`);
    return data as T;
  });
}

function toast(message: string): void {
  const element = $('toast');
  element.textContent = message;
  element.classList.remove('hidden');
  window.setTimeout(() => element.classList.add('hidden'), 3600);
}

function setApiStatus(online: boolean): void {
  apiState.textContent = online ? 'conectada' : 'sin conexión';
  apiState.parentElement?.classList.toggle('online', online);
}

async function checkApi(): Promise<void> {
  try {
    await nativeRequest({ method: 'GET', path: '/' });
    setApiStatus(true);
  } catch {
    setApiStatus(false);
  }
}

function initMap(): void {
  if (map) return;
  map = new MapLibreMap({
    container: 'map',
    center: [-91.835, 18.647],
    zoom: 12,
    style: {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '© OpenStreetMap contributors',
        },
      },
      layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
    },
    attributionControl: {},
  });
  map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
  map.on('load', () => {
    ensureRoutesVisible();
    renderStopMarkers();
    renderUnitMarkers();
    fitRoutesOnMap();
  });
}

function addRouteLayer(route: Route): void {
  if (!map?.isStyleLoaded() || route.trazo.length < 2) return;
  const currentMap = map;
  const sourceId = `route-${route.id}`;
  const geojson = {
    type: 'Feature' as const,
    properties: { name: route.nombre },
    geometry: { type: 'LineString' as const, coordinates: route.trazo.map((point) => [point.lon, point.lat]) },
  };
  const existing = currentMap.getSource(sourceId) as GeoJSONSource | undefined;
  if (existing) {
    existing.setData(geojson);
  } else {
    currentMap.addSource(sourceId, { type: 'geojson', data: geojson });
  }
  const color = routeColors[(route.id - 1) % routeColors.length];
  const casingId = `route-casing-${route.id}`;
  if (!currentMap.getLayer(casingId)) {
    currentMap.addLayer({ id: casingId, source: sourceId, type: 'line', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#211238', 'line-width': 11, 'line-opacity': 0.88 } });
  }
  if (!currentMap.getLayer(sourceId)) {
    currentMap.addLayer({ id: sourceId, source: sourceId, type: 'line', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': color, 'line-width': 6, 'line-opacity': 1 } });
  }
}

function ensureRoutesVisible(): void {
  if (!map) return;
  if (!map.isStyleLoaded()) {
    map.once('idle', ensureRoutesVisible);
    return;
  }
  routes.forEach(addRouteLayer);
  renderStopMarkers();
  fitRoutesOnMap();
}

function renderRouteLegend(): void {
  $('route-legend').innerHTML = routes.map((route) => {
    const color = routeColors[(route.id - 1) % routeColors.length];
    return `<span><i style="background:${color}"></i>${escapeHtml(route.nombre)}</span>`;
  }).join('');
}

function fitRoutesOnMap(): void {
  if (!map || routesFit) return;
  const points = routes.flatMap((route) => route.trazo);
  if (!points.length) return;
  const lngs = points.map((point) => point.lon);
  const lats = points.map((point) => point.lat);
  map.fitBounds([[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]], { padding: 34, maxZoom: 14, duration: 500 });
  routesFit = true;
}

function renderStopMarkers(): void {
  if (!map) return;
  routes.forEach((route) => route.paradas.forEach((stop, index) => {
    const key = `${route.id}:${index}`;
    const marker = stopMarkers.get(key);
    const point: [number, number] = [stop.lon, stop.lat];
    if (marker) {
      marker.setLngLat(point);
      return;
    }
    const el = document.createElement('div');
    el.className = 'stop-marker';
    el.innerHTML = `<span>${index + 1}</span>`;
    el.setAttribute('aria-label', `${stop.nombre}, ${route.nombre}`);
    const created = new Marker({ element: el, anchor: 'center' })
      .setLngLat(point)
      .setPopup(new Popup({ offset: 13 }).setText(`${stop.nombre} · ${route.nombre}`))
      .addTo(map!);
    stopMarkers.set(key, created);
  }));
}

function renderUnitMarkers(): void {
  if (!map) return;
  for (const unit of liveUnits) {
    if (!unit.posicion) continue;
    const lngLat: [number, number] = [unit.posicion.lon, unit.posicion.lat];
    const marker = unitMarkers.get(unit.unit_id);
    if (marker) {
      marker.setLngLat(lngLat);
    } else {
      const el = document.createElement('div');
      el.textContent = '🚌';
      el.className = 'bus-marker';
      el.setAttribute('aria-label', unit.unit_id);
      const routeName = routes.find((route) => route.id === unit.route_id)?.nombre || `Ruta ${unit.route_id ?? '—'}`;
      const created = new Marker({ element: el, anchor: 'center' }).setLngLat(lngLat).setPopup(new Popup({ offset: 20 }).setText(`${unit.unit_id} · ${unit.nombre} · ${routeName}`)).addTo(map);
      unitMarkers.set(unit.unit_id, created);
    }
  }
  const list = $('units-list');
  const live = liveUnits.filter((unit) => unit.posicion);
  list.innerHTML = live.length ? live.map((unit) => `<div class="unit-row"><span><strong>${escapeHtml(unit.unit_id)}</strong> <small>${escapeHtml(unit.nombre)} · Ruta ${unit.route_id ?? '—'}</small></span><span class="unit-live">● ${unit.posicion!.velocidad.toFixed(0)} km/h</span></div>`).join('') : '<p class="muted">Sin posiciones reportadas todavía.</p>';
  renderNearbyInfo();
}

function distanceMeters(a: MapPoint, b: MapPoint): number {
  const radians = (degrees: number) => degrees * Math.PI / 180;
  const lat1 = radians(a.lat), lat2 = radians(b.lat);
  const dLat = lat2 - lat1, dLon = radians(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

function formatDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60), remainder = total % 60;
  return minutes ? `${minutes} min ${remainder} s` : `${remainder} s`;
}

function travelTime(distance: number, kmh: number): string {
  return kmh > 0.5 ? formatDuration(distance / (kmh * 1000 / 3600)) : 'sin estimar (autobús detenido)';
}

function renderNearbyInfo(): void {
  const box = $('nearby-info');
  if (!passengerPosition) {
    box.innerHTML = '<p class="muted">Permite la ubicación del celular para ver qué autobús y referencia de ruta están más cerca.</p>';
    return;
  }
  const buses = liveUnits.filter((unit) => unit.posicion).map((unit) => ({
    unit,
    meters: distanceMeters(passengerPosition!, unit.posicion!),
  })).sort((a, b) => a.meters - b.meters);
  const stops: { stop: NamedStop; route: Route; meters: number }[] = routes.flatMap((route) => route.paradas.map((stop) => ({
    stop, route, meters: distanceMeters(passengerPosition!, stop),
  }))).sort((a, b) => a.meters - b.meters);
  const nearestBus = buses[0];
  const nearestStop = stops[0];
  const busStop = nearestBus ? routes.find((route) => route.id === nearestBus.unit.route_id)?.paradas
    .map((stop) => ({ stop, meters: distanceMeters(nearestBus.unit.posicion!, stop) }))
    .sort((a, b) => a.meters - b.meters)[0] : undefined;
  const busSpeed = nearestBus?.unit.posicion?.velocidad ?? 0;
  const busEta = nearestBus ? travelTime(nearestBus.meters, busSpeed) : 'sin unidades';
  const stopEta = nearestStop ? formatDuration(nearestStop.meters / (4.5 * 1000 / 3600)) : '—';
  const busStopEta = busStop ? travelTime(busStop.meters, busSpeed) : 'sin referencias de ruta';
  box.innerHTML = `<article class="distance-tile"><span>Conductor / autobús más cercano</span><strong>${nearestBus ? `${escapeHtml(nearestBus.unit.unit_id)} · ${formatDistance(nearestBus.meters)}` : 'Sin unidades'}</strong><small>${nearestBus ? `Llegada aprox.: ${busEta}` : 'No hay posiciones disponibles'}</small></article><article class="distance-tile"><span>Referencia de ruta más cercana</span><strong>${nearestStop ? escapeHtml(nearestStop.stop.nombre) : 'Sin referencias'}</strong><small>${nearestStop ? `${formatDistance(nearestStop.meters)} · a pie aprox. ${stopEta}` : 'No hay referencias disponibles'}</small></article><article class="distance-tile"><span>Referencia de ruta más cercana al autobús</span><strong>${busStop ? escapeHtml(busStop.stop.nombre) : '—'}</strong><small>${busStop ? `${formatDistance(busStop.meters)} · llegada aprox.: ${busStopEta}` : '—'}</small></article><p class="distance-note">Las rutas y referencias mostradas son aproximadas y no confirman paraderos oficiales. Distancias en línea recta; tiempos estimados sin considerar calles ni tráfico.</p>`;
}

function startPassengerLocation(): void {
  if (!navigator.geolocation) {
    toast('Este dispositivo no permite obtener la ubicación. Revisa los permisos de Android.');
    return;
  }
  if (passengerLocationWatch !== null) return;
  passengerLocationWatch = navigator.geolocation.watchPosition((position) => {
    if (!map) return;
    const point: [number, number] = [position.coords.longitude, position.coords.latitude];
    passengerPosition = { lat: position.coords.latitude, lon: position.coords.longitude };
    if (!passengerMarker) {
      const el = document.createElement('div');
      el.setAttribute('aria-label', 'Tu ubicación');
      el.style.cssText = 'width:20px;height:20px;border:3px solid white;border-radius:50%;background:#1687ff;box-shadow:0 0 0 7px #1687ff55,0 1px 5px #0009;';
      passengerMarker = new Marker({ element: el }).setLngLat(point).setPopup(new Popup({ offset: 15 }).setText('Tu ubicación')).addTo(map);
      map.easeTo({ center: point, zoom: 15 });
    } else {
      passengerMarker.setLngLat(point);
    }
    renderNearbyInfo();
  }, (error) => {
    if (passengerLocationWatch !== null) navigator.geolocation.clearWatch(passengerLocationWatch);
    passengerLocationWatch = null;
    const detail = error.code === error.PERMISSION_DENIED
      ? 'Permite la ubicación para Amor X Carmen Movi App en Ajustes de Android.'
      : error.code === error.POSITION_UNAVAILABLE ? 'Activa la ubicación/GPS del celular.' : 'No se pudo obtener tu ubicación; intenta de nuevo.';
    toast(detail);
  }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 });
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]!);
}

async function loadPassengerData(): Promise<void> {
  try {
    const [units, routeList] = await Promise.all([
      nativeRequest<UnitLive[]>({ method: 'GET', path: '/units/live' }),
      nativeRequest<Route[]>({ method: 'GET', path: '/routes' }),
    ]);
    liveUnits = units;
    routes = routeList;
    renderRouteLegend();
    setApiStatus(true);
    ensureRoutesVisible();
    renderUnitMarkers();
    renderRouteSelect();
  } catch (error) {
    setApiStatus(false);
    $('units-list').innerHTML = '<p class="muted">No se pudo conectar con el backend. Revisa la dirección en ⚙.</p>';
  }
}

function renderRouteSelect(): void {
  const select = $('driver-route') as HTMLSelectElement;
  if (!routes.length) return;
  select.innerHTML = routes.map((route) => `<option value="${route.id}">${escapeHtml(route.nombre)}</option>`).join('');
  select.value = String(currentRoute);
}

function renderUnitSelect(): void {
  const select = $('driver-unit') as HTMLSelectElement;
  const fromApi = liveUnits.map((unit) => `<option value="${escapeHtml(unit.unit_id)}">${escapeHtml(unit.unit_id)} · ${escapeHtml(unit.nombre)}</option>`);
  select.innerHTML = fromApi.length ? fromApi.join('') : '<option value="U-001">U-001 · Unidad de demostración</option>';
  if (!Array.from(select.options).some((option) => option.value === currentUnit)) currentUnit = select.options[0]?.value || 'U-001';
  select.value = currentUnit;
}

async function scanQrAndCheckIn(): Promise<void> {
  try {
    const result = await CapacitorBarcodeScanner.scanBarcode({
      hint: CapacitorBarcodeScannerTypeHint.QR_CODE,
      scanInstructions: 'Apunta al QR pegado dentro de la unidad',
      scanText: 'Escaneando QR',
      scanButton: false,
      cameraDirection: CapacitorBarcodeScannerCameraDirection.BACK,
    });
    const token = result.ScanResult.trim();
    if (!token) return;
    const receipt = await nativeRequest<{ id: number; unit_id: string; nombre_ruta: string; timestamp: string }>({
      method: 'POST', path: '/trips', body: { qr_token: token },
    });
    const card = $('trip-receipt');
    card.innerHTML = `<strong>Comprobante #${receipt.id}</strong><br>${escapeHtml(receipt.unit_id)} · ${escapeHtml(receipt.nombre_ruta || 'Ruta')}<br>${new Date(receipt.timestamp).toLocaleString('es-MX')}`;
    card.classList.remove('hidden');
    toast('Viaje registrado. Guarda tu comprobante digital.');
  } catch (error) {
    toast(`No se pudo registrar el viaje: ${errorMessage(error)}`);
  }
}

async function sendPassengerPanic(): Promise<void> {
  const unit = liveUnits.find((item) => item.posicion);
  try {
    await nativeRequest({ method: 'POST', path: '/alerts', body: {
      origen: 'pasajero',
      unit_id: unit?.unit_id ?? null,
      lat: unit?.posicion?.lat ?? null,
      lon: unit?.posicion?.lon ?? null,
      texto: 'Alerta de ayuda enviada desde la app pasajero',
    } });
    toast('Alerta enviada al operador. La atención es humana.');
  } catch (error) {
    toast(`No se pudo enviar la alerta: ${errorMessage(error)}`);
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Error inesperado';
}

function openQueueDb(): Promise<IDBDatabase> {
  if (queueDb) return Promise.resolve(queueDb);
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('rutasegura-position-queue', 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains('positions')) {
        const store = db.createObjectStore('positions', { keyPath: 'key' });
        store.createIndex('queuedAt', 'queuedAt');
      }
    };
    request.onsuccess = () => { queueDb = request.result; resolve(request.result); };
    request.onerror = () => reject(request.error || new Error('No se pudo abrir la cola offline'));
  });
}

async function queuePosition(payload: PositionPayload): Promise<void> {
  const key = `${payload.unit_id}:${payload.timestamp}`;
  if (key === lastPositionKey) return;
  lastPositionKey = key;
  const db = await openQueueDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction('positions', 'readwrite');
    tx.objectStore('positions').put({ key, queuedAt: Date.now(), payload } satisfies QueuedPosition);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error('No se pudo guardar la posición sin conexión'));
  });
  await updateQueueCount();
  await flushQueue();
}

async function queuedPositions(): Promise<QueuedPosition[]> {
  const db = await openQueueDb();
  return new Promise((resolve, reject) => {
    const request = db.transaction('positions', 'readonly').objectStore('positions').index('queuedAt').getAll();
    request.onsuccess = () => resolve(request.result as QueuedPosition[]);
    request.onerror = () => reject(request.error || new Error('No se pudo leer la cola offline'));
  });
}

async function removeQueuedPosition(key: string): Promise<void> {
  const db = await openQueueDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction('positions', 'readwrite');
    tx.objectStore('positions').delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error('No se pudo confirmar la posición'));
  });
}

async function updateQueueCount(): Promise<void> {
  try {
    const queue = await queuedPositions();
    $('queue-count').textContent = `${queue.length} pendientes`;
  } catch {
    $('queue-count').textContent = 'cola sin leer';
  }
}

async function flushQueue(): Promise<void> {
  if (flushBusy || !driverToken || !navigator.onLine) return;
  flushBusy = true;
  try {
    const queue = await queuedPositions();
    for (const item of queue) {
      try {
        await nativeRequest({ method: 'POST', path: '/positions', body: item.payload, token: driverToken });
        await removeQueuedPosition(item.key);
      } catch (error) {
        const message = errorMessage(error);
        if (/HTTP 401|HTTP 403/.test(message)) {
          setDriverStatus('error', 'Token rechazado · revisa unidad/token');
        } else if (/HTTP 4\d\d/.test(message)) {
          setDriverStatus('error', 'Backend rechazó la posición');
        } else {
          setDriverStatus('offline', 'Sin señal · guardando posiciones');
        }
        break;
      }
    }
    await updateQueueCount();
  } finally {
    flushBusy = false;
  }
}

function setDriverStatus(state: 'idle' | 'waiting' | 'active' | 'offline' | 'error', label?: string): void {
  const element = $('driver-status');
  element.className = `status-pill status-${state}`;
  const labels = { idle: 'Turno detenido', waiting: 'Esperando GPS', active: 'Transmitiendo', offline: 'Sin señal', error: 'Error' };
  element.innerHTML = `<i></i> ${escapeHtml(label || labels[state])}`;
}

function updatePositionDisplay(location: DeviceLocation): void {
  lastLocation = location;
  $('last-position').textContent = `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}`;
  $('last-position-time').textContent = new Date(location.time || Date.now()).toLocaleTimeString('es-MX');
}

function makePosition(location: DeviceLocation): PositionPayload {
  return {
    unit_id: currentUnit,
    lat: location.latitude,
    lon: location.longitude,
    velocidad: Math.max(0, (location.speed || 0) * 3.6),
    timestamp: new Date(location.time || Date.now()).toISOString(),
  };
}

async function sampleAndQueuePosition(): Promise<void> {
  if (!lastLocation || !trackingId) return;
  try {
    setDriverStatus(navigator.onLine ? 'active' : 'offline', navigator.onLine ? undefined : 'Sin señal · guardando posiciones');
    await queuePosition(makePosition(lastLocation));
  } catch (error) {
    setDriverStatus('error', 'Error al guardar posición');
    toast(errorMessage(error));
  }
}

async function ensureNotificationsAllowed(): Promise<void> {
  const permission = await LocalNotifications.requestPermissions();
  if (permission.display !== 'granted') throw new Error('Permite las notificaciones para mantener visible el seguimiento.');
}

async function startShift(): Promise<void> {
  saveDriverSettings();
  if (!currentUnit || !driverToken) {
    toast('Selecciona la unidad e ingresa su token de conductor.');
    return;
  }
  try {
    await ensureNotificationsAllowed();
    lastLocation = null;
    const id = await BackgroundGeolocation.addWatcher({
      backgroundMessage: `Transmitiendo ubicación de la unidad ${currentUnit}`,
      backgroundTitle: 'Amor X Carmen · turno activo',
      requestPermissions: true,
      stale: false,
      distanceFilter: 0,
    }, (position?: DeviceLocation, error?: CallbackError) => {
      if (error) {
        setDriverStatus('error', error.message || 'Error GPS');
        return;
      }
      if (position) {
        const firstFix = !lastLocation;
        updatePositionDisplay(position);
        if (firstFix && trackingId) {
          if (gpsFixTimeout !== null) window.clearTimeout(gpsFixTimeout);
          gpsFixTimeout = null;
          lastSampleAt = Date.now();
          $('location-detail').textContent = `GPS activo · enviando ${currentUnit} · Ruta ${currentRoute}`;
          void sampleAndQueuePosition();
        }
        void flushQueue();
      }
    });
    trackingId = id;
    $('start-shift').setAttribute('disabled', 'true');
    $('stop-shift').removeAttribute('disabled');
    if (lastLocation) {
      setDriverStatus('active');
      $('location-detail').textContent = `GPS activo · enviando ${currentUnit} · Ruta ${currentRoute}`;
      lastSampleAt = Date.now();
    } else {
      setDriverStatus('waiting', 'Esperando señal GPS…');
      $('location-detail').textContent = 'Turno iniciado; esperando la primera ubicación del teléfono.';
      gpsFixTimeout = window.setTimeout(() => {
        if (trackingId && !lastLocation) {
          setDriverStatus('error', 'Sin señal GPS · revisa permisos/Ubicación');
          $('location-detail').textContent = 'Activa Ubicación precisa y permite acceso “siempre” para Amor X Carmen Movi App en Ajustes de Android.';
        }
      }, 25000);
    }
    await sampleAndQueuePosition();
    shiftTimer = window.setInterval(() => {
      const moving = (lastLocation?.speed || 0) > 0.7;
      const interval = moving ? 5000 : 15000;
      if (Date.now() - lastSampleAt >= interval) {
        lastSampleAt = Date.now();
        void sampleAndQueuePosition();
      }
    }, 1000);
    void flushQueue();
  } catch (error) {
    trackingId = null;
    setDriverStatus('error', 'No se pudo iniciar GPS');
    toast(`Revisa permisos de ubicación y notificaciones. ${errorMessage(error)}`);
  }
}

let lastSampleAt = 0;

async function stopShift(): Promise<void> {
  if (trackingId) await BackgroundGeolocation.removeWatcher({ id: trackingId }).catch(() => undefined);
  trackingId = null;
  lastLocation = null;
  if (gpsFixTimeout !== null) window.clearTimeout(gpsFixTimeout);
  gpsFixTimeout = null;
  if (shiftTimer !== null) window.clearInterval(shiftTimer);
  shiftTimer = null;
  $('start-shift').removeAttribute('disabled');
  $('stop-shift').setAttribute('disabled', 'true');
  $('location-detail').textContent = 'Turno terminado. La cola pendiente queda guardada.';
  setDriverStatus('idle');
}

function saveDriverSettings(): void {
  currentUnit = ($('driver-unit') as HTMLSelectElement).value;
  currentRoute = Number(($('driver-route') as HTMLSelectElement).value);
  driverToken = ($('driver-token') as HTMLInputElement).value.trim() || driverToken;
  localStorage.setItem('rutasegura.unit', currentUnit);
  localStorage.setItem('rutasegura.route', String(currentRoute));
  if (driverToken) localStorage.setItem('rutasegura.driver-token', driverToken);
  $('driver-token').setAttribute('placeholder', driverToken ? 'Token guardado en este dispositivo' : 'Pega el token seguro de la unidad');
  toast('Configuración del conductor guardada en este dispositivo.');
}

async function sendDriverPanic(): Promise<void> {
  try {
    await nativeRequest({ method: 'POST', path: '/alerts', token: driverToken, body: {
      origen: 'conductor', unit_id: currentUnit,
      lat: lastLocation?.latitude ?? null, lon: lastLocation?.longitude ?? null,
      texto: 'Alerta de pánico del conductor',
    } });
    toast('Alerta enviada al operador. La atención es humana.');
  } catch (error) {
    toast(`No se pudo enviar el pánico: ${errorMessage(error)}`);
  }
}

function bindPanicHold(): void {
  const button = $('driver-panic') as HTMLButtonElement;
  const progress = $('hold-progress') as HTMLSpanElement;
  const label = $('panic-label');
  let start = 0;
  let timer: number | null = null;
  let fired = false;
  const cancel = () => {
    if (timer !== null) window.clearInterval(timer);
    timer = null;
    progress.style.width = '0%';
    if (!fired) label.textContent = 'Mantener para alertar';
    fired = false;
  };
  button.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    button.setPointerCapture(event.pointerId);
    start = Date.now();
    label.textContent = 'Sigue presionando…';
    timer = window.setInterval(() => {
      const pct = Math.min(100, ((Date.now() - start) / 2000) * 100);
      progress.style.width = `${pct}%`;
      if (pct >= 100 && !fired) {
        fired = true;
        if (timer !== null) window.clearInterval(timer);
        timer = null;
        label.textContent = 'Alerta enviada';
        void sendDriverPanic();
      }
    }, 50);
  });
  button.addEventListener('pointerup', cancel);
  button.addEventListener('pointercancel', cancel);
  button.addEventListener('lostpointercapture', cancel);
}

async function submitReport(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const text = ($('report-text') as HTMLTextAreaElement).value.trim();
  if (!text) return;
  try {
    await nativeRequest({ method: 'POST', path: '/reports', body: { texto: text } });
    ($('report-text') as HTMLTextAreaElement).value = '';
    toast('Reporte enviado para revisión del operador.');
  } catch (error) {
    toast(`No se pudo enviar el reporte: ${errorMessage(error)}`);
  }
}

async function submitAssistantQuestion(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const question = ($('assistant-question') as HTMLInputElement).value.trim();
  if (!question) return;
  const answer = $('assistant-answer');
  answer.textContent = 'Consultando…';
  answer.classList.remove('hidden');
  try {
    const result = await nativeRequest<{ respuesta: string; fallo: boolean }>({ method: 'POST', path: '/assistant', body: { pregunta: question } });
    answer.textContent = result.respuesta + (result.fallo ? ' (respuesta de respaldo)' : '');
  } catch (error) {
    answer.textContent = `No se pudo consultar el asistente: ${errorMessage(error)}`;
  }
}

function setMode(mode: 'passenger' | 'driver'): void {
  document.querySelectorAll<HTMLButtonElement>('.mode-button').forEach((button) => button.classList.toggle('active', button.dataset.mode === mode));
  $('passenger-mode').classList.toggle('hidden', mode !== 'passenger');
  $('driver-mode').classList.toggle('hidden', mode !== 'driver');
  if (mode === 'passenger') {
    initMap();
    window.setTimeout(() => map?.resize(), 100);
    startPassengerLocation();
    void loadPassengerData();
  } else {
    renderUnitSelect();
    renderRouteSelect();
    ($('driver-unit') as HTMLSelectElement).value = currentUnit;
    ($('driver-route') as HTMLSelectElement).value = String(currentRoute);
    ($('driver-token') as HTMLInputElement).value = driverToken;
    void updateQueueCount();
  }
}

document.querySelectorAll<HTMLButtonElement>('.mode-button').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.mode as 'passenger' | 'driver')));
$('refresh-map').addEventListener('click', () => void loadPassengerData());
$('my-location').addEventListener('click', () => {
  startPassengerLocation();
  if (passengerMarker && map) map.easeTo({ center: passengerMarker.getLngLat(), zoom: 16 });
});
$('scan-qr').addEventListener('click', () => void scanQrAndCheckIn());
$('passenger-panic').addEventListener('click', () => {
  if (window.confirm('¿Enviar una alerta al operador?')) void sendPassengerPanic();
});
$('report-form').addEventListener('submit', (event) => void submitReport(event as SubmitEvent));
$('assistant-form').addEventListener('submit', (event) => void submitAssistantQuestion(event as SubmitEvent));
$('save-driver-settings').addEventListener('click', saveDriverSettings);
$('start-shift').addEventListener('click', () => void startShift());
$('stop-shift').addEventListener('click', () => void stopShift());
bindPanicHold();
$('open-app-settings').addEventListener('click', () => void BackgroundGeolocation.openSettings());
$('settings-open').addEventListener('click', () => {
  backendInput.value = apiBase;
  settingsDialog.showModal();
});
$('settings-save').addEventListener('click', () => {
  const value = backendInput.value.trim().replace(/\/$/, '');
  if (!/^https?:\/\//.test(value)) {
    $('settings-message').textContent = 'Ingresa una URL http:// o https:// válida.';
    return;
  }
  apiBase = value;
  localStorage.setItem('rutasegura.api', apiBase);
  settingsDialog.close();
  void checkApi();
  void loadPassengerData();
  toast('Dirección del backend guardada.');
});
$('test-connection').addEventListener('click', async () => {
  apiBase = backendInput.value.trim().replace(/\/$/, '');
  $('settings-message').textContent = 'Probando…';
  try {
    await nativeRequest({ method: 'GET', path: '/' });
    $('settings-message').textContent = 'Conexión exitosa con el backend.';
  } catch (error) {
    $('settings-message').textContent = `No se pudo conectar: ${errorMessage(error)}`;
  }
});
window.addEventListener('online', () => { setApiStatus(true); setDriverStatus(trackingId ? 'active' : 'idle'); void flushQueue(); });
window.addEventListener('offline', () => { setApiStatus(false); if (trackingId) setDriverStatus('offline', 'Sin señal · guardando posiciones'); });
window.addEventListener('beforeunload', () => {
  if (trackingId) void BackgroundGeolocation.removeWatcher({ id: trackingId });
});

backendInput.value = apiBase;
($('driver-unit') as HTMLSelectElement).value = currentUnit;
($('driver-route') as HTMLSelectElement).value = String(currentRoute);
($('driver-token') as HTMLInputElement).value = driverToken;
initMap();
void checkApi();
void loadPassengerData();
void updateQueueCount();
window.setInterval(() => void loadPassengerData(), 10000);
