"""
DroneSync - HTTP API for drone registration and telemetry.
Any drone can connect via simple HTTP requests.
"""
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from dronesync.drone_registry import registry


class DroneAPIHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def _json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            try:
                return json.loads(self.rfile.read(length))
            except Exception:
                pass
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/drones":
            self._json(200, registry.get_active_drones())
        elif parsed.path.startswith("/drones/"):
            drone_id = parsed.path.split("/")[-1]
            d = registry.get_drone(drone_id)
            self._json(200 if d else 404, d or {"error": "not_found"})
        elif parsed.path == "/health":
            self._json(200, {"status": "ok", "drones": registry.count(), "ts": int(time.time())})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._body()

        if parsed.path == "/drones/register":
            drone_id = body.get("drone_id")
            if not drone_id:
                self._json(400, {"error": "drone_id required"})
                return
            result = registry.register(drone_id, source="http_api", metadata=body.get("metadata", {}))
            self._json(200, result)

        elif parsed.path == "/drones/telemetry":
            drone_id = body.get("drone_id")
            if not drone_id:
                self._json(400, {"error": "drone_id required"})
                return
            registry.update_telemetry(drone_id, body)
            self._json(200, {"status": "ok", "drone_id": drone_id})

        elif parsed.path == "/drones/heartbeat":
            drone_id = body.get("drone_id")
            ok = registry.heartbeat(drone_id) if drone_id else False
            self._json(200 if ok else 404, {"status": "ok" if ok else "not_found"})

        elif parsed.path == "/drones/unregister":
            drone_id = body.get("drone_id")
            result = registry.unregister(drone_id) if drone_id else {"error": "drone_id required"}
            self._json(200, result)

        else:
            self._json(404, {"error": "not_found"})


def run_api(host: str = "0.0.0.0", port: int = 8081):
    print(f"[DroneAPI] HTTP API on {host}:{port}")
    server = HTTPServer((host, port), DroneAPIHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_api()
