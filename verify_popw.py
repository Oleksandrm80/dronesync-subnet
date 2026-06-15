"""
DroneSync — PoPW External Verifier
Usage: python3 verify_popw.py <popw.json>
"""
import sys
import json
import hashlib


def verify(record: dict) -> dict:
    results = []
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            results.append(f"  PASS  {name}" + (f" ({detail})" if detail else ""))
        else:
            failed += 1
            results.append(f"  FAIL  {name}" + (f" ({detail})" if detail else ""))

    # 1. Version
    check("PoPW version", record.get("popw_version") == "2.0", record.get("popw_version", "?"))

    # 2. Mission ID present
    check("Mission ID present", bool(record.get("mission_id")), record.get("mission_id", "?"))

    # 3. Trajectory hash present
    traj_hash = record.get("trajectory_hash", "")
    check("Trajectory hash present", len(traj_hash) == 64, traj_hash[:16] + "...")

    # 4. Score valid
    score = record.get("score", -1)
    check("Score valid (0-100)", 0 <= score <= 100, str(score))

    # 5. Attestation present
    att = record.get("attestation", {})
    check("Attestation present", bool(att))

    # 6. TEE signed
    check("TEE status SIGNED", att.get("status") == "SIGNED", att.get("status", "?"))

    # 7. Attestation trajectory hash matches
    check("Attestation hash matches",
          att.get("trajectory_hash") == traj_hash,
          "consistent" if att.get("trajectory_hash") == traj_hash else "MISMATCH")

    # 8. Attestation mission_id matches
    check("Attestation mission_id matches",
          att.get("mission_id") == record.get("mission_id"),
          "consistent" if att.get("mission_id") == record.get("mission_id") else "MISMATCH")

    # 9. Signature present
    check("PoPW signature present", bool(record.get("popw_signature")))

    # 10. On chain ready
    check("On-chain ready", record.get("on_chain_ready") is True)

    return {
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
        "results": results,
        "verdict": "VERIFIED" if failed == 0 else "INVALID"
    }


def main():
    print("\n" + "=" * 55)
    print("  DRONESYNC — PoPW EXTERNAL VERIFIER")
    print("=" * 55 + "\n")

    if len(sys.argv) < 2:
        # Demo mode — generate and verify a fresh PoPW
        print("No file provided — running demo verification...\n")
        try:
            from miner.planner import DronePlanner
            from environment.sim import DroneEnvironment
            from validator.scorer import DroneEvaluator
            from dronesync.verifier import PoPWRecord

            class M:
                mission_id = "VERIFY_DEMO"
                origin = type("o", (), {"lat": 47.37, "lon": 8.54, "alt": 50, "speed": 5})
                waypoints = [type("o", (), {"lat": 47.38, "lon": 8.54, "alt": 50, "speed": 5})]
                destination = type("o", (), {"lat": 47.39, "lon": 8.55, "alt": 50, "speed": 5})
                mission_type = type("o", (), {"value": "urban_delivery"})

            m = M()
            traj = DronePlanner().plan_trajectory(m)
            sensor = DroneEnvironment().run(traj)
            score = DroneEvaluator().score(traj, sensor)
            record = PoPWRecord().create_record(m.mission_id, traj, score)
        except Exception as e:
            print(f"Error generating demo PoPW: {e}")
            sys.exit(1)
    else:
        path = sys.argv[1]
        try:
            with open(path) as f:
                record = json.load(f)
            print(f"Verifying: {path}\n")
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)

    print(f"  mission_id:       {record.get('mission_id')}")
    print(f"  trajectory_hash:  {record.get('trajectory_hash','')[:24]}...")
    print(f"  score:            {record.get('score')}")
    print(f"  tee_status:       {record.get('attestation', {}).get('status')}")
    print()
    print("Checks:")

    result = verify(record)
    for line in result["results"]:
        print(line)

    print()
    print(f"  {result['passed']}/{result['total']} checks passed")
    print()
    print("=" * 55)
    print(f"  VERDICT: {result['verdict']}")
    print("=" * 55 + "\n")

    sys.exit(0 if result["verdict"] == "VERIFIED" else 1)


if __name__ == "__main__":
    main()
