"""
demo_zk_proof.py

Demo: Zero-Knowledge Proof for drone flight
Proves mission completed WITHOUT revealing trajectory.

Run:
    python3 demo_zk_proof.py
"""

import time
from dronesync.zk_prover import ZKProver, ZKVerifier


def main():
    print(f"\n{'='*60}")
    print("DroneSync — Zero-Knowledge Flight Proof")
    print("Proves mission completed WITHOUT revealing trajectory")
    print(f"{'='*60}")

    prover = ZKProver()

    if not prover.is_available():
        print("ERROR: ZK files not found. Run circom setup first.")
        return

    print("\n[1] Mission parameters (PUBLIC — visible to everyone):")
    origin = (0.0, 0.0)
    dest = (0.05, 0.05)
    min_score = 60.0
    print(f"    Origin:    {origin[0]}, {origin[1]}")
    print(f"    Dest:      {dest[0]}, {dest[1]}")
    print(f"    Min score: {min_score}")

    print("\n[2] Secret trajectory (PRIVATE — never revealed):")
    waypoints = [
        [0.0, 0.0],
        [0.01, 0.01],
        [50.4510, 30.5242],
        [50.4515, 30.5246],
        [0.05, 0.05],
    ]
    score = 87.0
    for i, wp in enumerate(waypoints):
        print(f"    Waypoint {i+1}: {wp[0]}, {wp[1]}")
    print(f"    Score: {score}")

    print("\n[3] Generating ZK proof...")
    proof = prover.generate_proof(
        origin_lat=origin[0],
        origin_lon=origin[1],
        dest_lat=dest[0],
        dest_lon=dest[1],
        waypoints=waypoints,
        score=score,
        min_score=min_score,
    )

    if not proof:
        print("ERROR: Proof generation failed.")
        return

    print(f"    Generated in {proof.generation_ms:.0f}ms")
    print(f"    Protocol: {proof.to_dict()['protocol']}")
    print(f"    Curve:    {proof.to_dict()['curve']}")
    print(f"    Proof pi_a: {str(proof.proof.get('pi_a', ['?'])[0])[:32]}...")

    print("\n[4] Verifying proof (validator side)...")
    verifier = ZKVerifier()
    valid = verifier.verify(proof.proof, proof.public)

    if valid:
        print("    ✅ PROOF VALID — Mission verified without revealing trajectory")
    else:
        print("    ❌ PROOF INVALID")

    print("\n[5] Testing with tampered proof...")
    tampered = dict(proof.proof)
    tampered["pi_a"] = ["0x1234", "0x5678", "0x1"]
    valid_tampered = verifier.verify(tampered, proof.public)
    if not valid_tampered:
        print("    ✅ Tampered proof correctly rejected")
    else:
        print("    ❌ Tampered proof incorrectly accepted")

    print(f"\n{'='*60}")
    print("✅ ZK-Proof complete — trajectory stays private forever")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
