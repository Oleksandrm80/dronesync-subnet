"""
DroneSync - PoPW Export API
Exports proof in standard format for external validation (Konnex, etc.)
"""
import json
import hashlib
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


_popw_store = {}


def submit_popw(mission_id: str, drone_id: str, score: float,
                bundle_hash: str, ed25519_sig: str,
                trajectory_hash: str, telemetry: dict) -> dict:
    """Store a PoPW proof for external verification."""
    proof = {
        "version":         "1.0",
        "protocol":        "DroneSync-PoPW",
        "mission_id":      mission_id,
        "drone_id":        drone_id,
        "score":           score,
        "bundle_hash":     bundle_hash,
        "trajectory_hash": trajectory_hash,
        "ed25519_sig":     ed25519_sig,
        "telemetry":       telemetry,
        "submitted_at":    int(time.time()),
        "proof_hash":      hashlib.sha256(
            f"{mission_id}{drone_id}{bundle_hash}{trajectory_hash}".encode()
        ).hexdigest()
    }
    _popw_store[mission_id] = proof
    return proof


def verify_popw(mission_id: str) -> dict:
    """Verify a stored PoPW proof."""
    proof = _popw_store.get(mission_id)
    if not proof:
        return {"valid": False, "error": "proof_not_found"}

    expected_hash = hashlib.sha256(
        f"{proof['mission_id']}{proof['drone_id']}{proof['bundle_hash']}{proof['trajectory_hash']}".encode()
    ).hexdigest()

    valid = proof["proof_hash"] == expected_hash and proof["score"] >= 60

    return {
        "valid":        valid,
        "mission_id":   mission_id,
        "drone_id":     proof["drone_id"],
        "score":        proof["score"],
        "proof_hash":   proof["proof_hash"],
        "verified_at":  int(time.time())
    }


class PoPWExportHandler(BaseHTTPRequestHandler):

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
        if parsed.path == "/popw":
            self._json(200, {"proofs": len(_popw_store), "missions": list(_popw_store.keys())})
        elif parsed.path.startswith("/popw/verify/"):
            mission_id = parsed.path.split("/")[-1]
            self._json(200, verify_popw(mission_id))
        elif parsed.path.startswith("/popw/proof/"):
            mission_id = parsed.path.split("/")[-1]
            proof = _popw_store.get(mission_id)
            self._json(200 if proof else 404, proof or {"error": "not_found"})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/popw/submit":
            body = self._body()
            proof = submit_popw(
                mission_id=body.get("mission_id", ""),
                drone_id=body.get("drone_id", ""),
                score=body.get("score", 0),
                bundle_hash=body.get("bundle_hash", ""),
                ed25519_sig=body.get("ed25519_sig", ""),
                trajectory_hash=body.get("trajectory_hash", ""),
                telemetry=body.get("telemetry", {})
            )
            self._json(200, proof)
        else:
            self._json(404, {"error": "not_found"})


def run_popw_api(host: str = "0.0.0.0", port: int = 8083):
    print(f"[PoPW API] Running on {host}:{port}")
    server = HTTPServer((host, port), PoPWExportHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_popw_api()
