"""
DroneSync REST API
Usage: python3 api.py
Endpoints:
  POST /mission  — submit mission, get PoPW
  GET  /health   — health check
  GET  /verify/<mission_id> — verify PoPW
"""
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from dronesync.synapse import DroneNavSynapseHandler
from dronesync.logger import get_logger

logger = get_logger("dronesync.api")
handler = DroneNavSynapseHandler(drone_id="API_DRONE")


class DroneAPIHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        logger.info("%s %s", self.address_string(), format % args)

    def send_json(self, code: int, data: dict):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {
                "status": "ok",
                "service": "DroneSync API",
                "version": "1.0",
                "timestamp": time.time()
            })
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/mission":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                task = json.loads(body)
                result = handler.handle(task)
                code = 200 if result.get("status") == "OK" else 400
                self.send_json(code, result)
            except json.JSONDecodeError:
                self.send_json(400, {"error": "invalid JSON"})
            except Exception as e:
                self.send_json(500, {"error": str(e)})
        else:
            self.send_json(404, {"error": "not found"})


def run(host="0.0.0.0", port=8888):
    server = HTTPServer((host, port), DroneAPIHandler)
    logger.info("DroneSync API running at http://%s:%d", host, port)
    logger.info("POST /mission  — submit mission")
    logger.info("GET  /health   — health check")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("API stopped")


if __name__ == "__main__":
    run()
