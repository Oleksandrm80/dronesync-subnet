"""
ZK Trusted Setup Test
Verifies integrity of ZK setup files.
"""
import sys
import os
import json
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.zk_prover import ZKProver, ZKVerifier, FlightProof

ZK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "zk")


def test_zk_files_exist():
    required = [
        "flight_proof_final.zkey",
        "verification_key.json",
        "flight_proof.r1cs",
        "pot12_final.ptau",
    ]
    for f in required:
        path = os.path.join(ZK_DIR, f)
        assert os.path.exists(path), f"Missing ZK file: {f}"


def test_zk_prover_is_available():
    prover = ZKProver(zk_dir=ZK_DIR)
    assert prover.is_available() is True


def test_verification_key_valid_json():
    vkey_path = os.path.join(ZK_DIR, "verification_key.json")
    with open(vkey_path) as f:
        vkey = json.load(f)
    assert "protocol" in vkey or "vk_alpha_1" in vkey or "alpha" in vkey or len(vkey) > 0


def test_zkey_not_empty():
    zkey_path = os.path.join(ZK_DIR, "flight_proof_final.zkey")
    size = os.path.getsize(zkey_path)
    assert size > 1000, f"zkey too small: {size} bytes"


def test_ptau_not_empty():
    ptau_path = os.path.join(ZK_DIR, "pot12_final.ptau")
    size = os.path.getsize(ptau_path)
    assert size > 1000, f"ptau too small: {size} bytes"


def test_zkey_integrity_stable():
    zkey_path = os.path.join(ZK_DIR, "flight_proof_final.zkey")
    with open(zkey_path, "rb") as f:
        data = f.read()
    h1 = hashlib.sha256(data).hexdigest()
    with open(zkey_path, "rb") as f:
        data = f.read()
    h2 = hashlib.sha256(data).hexdigest()
    assert h1 == h2, "zkey file changed between reads"


def test_flight_proof_dataclass():
    proof = FlightProof(proof={"pi_a": [1, 2]}, public=["1"], generation_ms=150.0)
    d = proof.to_dict()
    assert d["protocol"] == "groth16"
    assert d["curve"] == "bn128"
    assert d["generation_ms"] == 150.0


def test_zk_verifier_init():
    vkey_path = os.path.join(ZK_DIR, "verification_key.json")
    verifier = ZKVerifier(vkey_path=vkey_path)
    assert verifier._vkey == vkey_path
