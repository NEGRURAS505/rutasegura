#!/usr/bin/env python3
"""Send deterministic demo positions to RutaSegura's POST /positions endpoint.

Uses only the Python standard library so it can run before the app dependencies
are installed. Coordinates below are fictional demo data, not actual routes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


ROUTES = {
    "demo-norte": [
        (18.6469, -91.8350), (18.6499, -91.8330),
        (18.6529, -91.8350), (18.6529, -91.8380),
        (18.6499, -91.8400), (18.6469, -91.8350),
    ],
    "demo-centro": [
        (18.6549, -91.8310), (18.6579, -91.8290),
        (18.6609, -91.8310), (18.6609, -91.8340),
        (18.6579, -91.8360), (18.6549, -91.8310),
    ],
    "demo-sur": [
        (18.6389, -91.8390), (18.6419, -91.8370),
        (18.6449, -91.8390), (18.6449, -91.8420),
        (18.6419, -91.8440), (18.6389, -91.8390),
    ],
}


def post_json(url: str, payload: dict, token: str | None, timeout: float) -> None:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            print(f"{response.status} {url}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo conectar: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--route", choices=ROUTES, default="demo-norte")
    parser.add_argument("--unit-id", default=os.getenv("SIM_UNIT_ID", "U-001"))
    parser.add_argument("--token", default=os.getenv("SIM_DRIVER_TOKEN"))
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--count", type=int, default=0, help="0 runs until Ctrl+C")
    parser.add_argument("--panic", action="store_true", help="send one demo passenger panic alert")
    args = parser.parse_args()
    if args.interval <= 0 or args.count < 0:
        parser.error("--interval must be positive and --count cannot be negative")
    if not args.base_url.startswith(("http://", "https://")):
        parser.error("--base-url must start with http:// or https://")

    points = ROUTES[args.route]
    endpoint = args.base_url.rstrip("/")
    sent = 0
    print(f"Simulando {args.unit_id} en {args.route}; Ctrl+C para detener.")
    try:
        while args.count == 0 or sent < args.count:
            lat, lon = points[sent % len(points)]
            payload = {
                "unit_id": args.unit_id,
                "lat": lat,
                "lon": lon,
                "velocidad": 18.0 if sent % 4 else 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            post_json(f"{endpoint}/positions", payload, args.token, timeout=10)
            sent += 1
            if sent < args.count or args.count == 0:
                time.sleep(args.interval)

        if args.panic:
            alert = {
                "origen": "pasajero",
                "unit_id": args.unit_id,
                "lat": points[(sent - 1) % len(points)][0],
                "lon": points[(sent - 1) % len(points)][1],
                "texto": "Alerta de demostración del simulador",
            }
            post_json(f"{endpoint}/alerts", alert, None, timeout=10)
    except KeyboardInterrupt:
        print("Simulación detenida.")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
