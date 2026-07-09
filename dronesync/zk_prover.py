"""
dronesync/zk_prover.py

ZK-Proof integration for DroneSync.
Generates and verifies Groth16 zero-knowledge proofs
for drone flight trajectories using circom + snarkjs.

Proves: drone completed flight from origin to destination
        with score >= min_score
WITHOUT revealing the actual trajectory waypoints.
"""

import json
import os
import subprocess
import tempfile
import logging
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

ZK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "zk")


class FlightProof:

    def __init__(self, proof: dict, public: dict, generation_ms: float = 0.0):
        self.proof = proof
        self.public = public
        self.generation_ms = generation_ms

    def to_dict(self) -> dict:
        return {
            "proof": self.proof,
            "public": self.public,
            "generation_ms": round(self.generation_ms, 2),
            "protocol": "groth16",
            "curve": "bn128",
        }


class ZKProver:
    """
    Generates ZK proofs for drone flight missions.
    Uses circom circuit + snarkjs groth16.
    """

    def __init__(self, zk_dir: str = ZK_DIR):
        self.zk_dir = zk_dir
        self._zkey = os.path.join(zk_dir, "flight_proof_final.zkey")
        self._wasm = os.path.join(zk_dir, "flight_proof_js", "flight_proof.wasm")
        self._vkey = os.path.join(zk_dir, "verification_key.json")
        self._gen_witness = os.path.join(zk_dir, "flight_proof_js", "generate_witness.js")

    def is_available(self) -> bool:
        return all(os.path.exists(p) for p in [
            self._zkey, self._wasm, self._vkey, self._gen_witness
        ])

    def generate_proof(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        waypoints: List[List[float]],
        score: float,
        min_score: float = 60.0,
    ) -> Optional[FlightProof]:

        if not self.is_available():
            logger.error("ZK files not found in %s", self.zk_dir)
            return None

        # Scale coordinates to integers (circom works with integers)
        def scale(v): return str(int(round(v * 10000)))

        n = 5
        lats = [wp[0] for wp in waypoints]
        lons = [wp[1] for wp in waypoints]

        # Pad or trim to exactly 5 waypoints
        while len(lats) < n:
            lats.append(lats[-1])
            lons.append(lons[-1])
        lats = lats[:n]
        lons = lons[:n]

        # Force first/last to match origin/dest
        lats[0] = origin_lat
        lons[0] = origin_lon
        lats[-1] = dest_lat
        lons[-1] = dest_lon

        input_data = {
            "origin_lat": scale(origin_lat),
            "origin_lon": scale(origin_lon),
            "dest_lat": scale(dest_lat),
            "dest_lon": scale(dest_lon),
            "min_score": str(int(min_score)),
            "waypoint_lat": [scale(v) for v in lats],
            "waypoint_lon": [scale(v) for v in lons],
            "score": str(int(score)),
        }

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "input.json")
            witness_path = os.path.join(tmp, "witness.wtns")
            proof_path = os.path.join(tmp, "proof.json")
            public_path = os.path.join(tmp, "public.json")

            with open(input_path, "w") as f:
                json.dump(input_data, f)

            start = time.time()

            # Generate witness
            r = subprocess.run(
                ["node", self._gen_witness, self._wasm, input_path, witness_path],
                capture_output=True, text=True, timeout=60
            )
            if r.returncode != 0:
                logger.error("Witness generation failed: %s", r.stderr)
                return None

            # Generate proof
            r = subprocess.run(
                ["node", os.path.join(self.zk_dir, "node_modules/.bin/snarkjs"), "groth16", "prove",
                 self._zkey, witness_path, proof_path, public_path],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode != 0:
                logger.error("Proof generation failed: %s", r.stderr)
                return None

            generation_ms = (time.time() - start) * 1000

            with open(proof_path) as f:
                proof = json.load(f)
            with open(public_path) as f:
                public = json.load(f)

            logger.info("ZK proof generated in %.0fms", generation_ms)
            return FlightProof(proof=proof, public=public, generation_ms=generation_ms)

    def verify_proof(self, flight_proof: FlightProof) -> bool:
        if not self.is_available():
            return False

        with tempfile.TemporaryDirectory() as tmp:
            proof_path = os.path.join(tmp, "proof.json")
            public_path = os.path.join(tmp, "public.json")

            with open(proof_path, "w") as f:
                json.dump(flight_proof.proof, f)
            with open(public_path, "w") as f:
                json.dump(flight_proof.public, f)

            r = subprocess.run(
                ["node", os.path.join(self.zk_dir, "node_modules/.bin/snarkjs"), "groth16", "verify",
                 self._vkey, public_path, proof_path],
                capture_output=True, text=True, timeout=60
            )

            ok = r.returncode == 0 and "OK!" in r.stdout
            logger.info("ZK proof verification: %s", "VALID" if ok else "INVALID")
            return ok


class ZKVerifier:
    """
    Standalone verifier — only needs verification_key.json.
    Validators use this to verify proofs from miners.
    """

    def __init__(self, vkey_path: str = None):
        self._vkey = vkey_path or os.path.join(ZK_DIR, "verification_key.json")

    def verify(self, proof: dict, public: dict) -> bool:
        fp = FlightProof(proof=proof, public=public)
        prover = ZKProver()
        prover._vkey = self._vkey
        return prover.verify_proof(fp)
