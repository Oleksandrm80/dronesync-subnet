from fastapi import FastAPI
import time

from miner.planner import DronePlanner
from environment.sim import DroneEnvironment
from validator.scorer import DroneEvaluator
from dronesync.verifier import PoPWRecord
from dronesync.reputation import DroneReputation
from dronesync.sensor_bundle import SensorBundle
from validator.scoreroot import ScoreRoot


app = FastAPI(title="DroneSync API", version="1.0")

planner = DronePlanner()
validator = DroneEvaluator()
env = DroneEnvironment()
popw = PoPWRecord()
reputation = DroneReputation("DRONE_001")
scoreroot = ScoreRoot("VALIDATOR_001")


class FakeMission:
    def __init__(self):
        self.mission_id = "DSYNC_" + str(int(time.time()))
        self.origin = type("o", (), {"lat": 47.3769, "lon": 8.5417, "alt": 50, "speed": 5})
        self.waypoints = [type("o", (), {"lat": 47.3780, "lon": 8.5430, "alt": 50, "speed": 5})]
        self.destination = type("o", (), {"lat": 47.3800, "lon": 8.5450, "alt": 50, "speed": 5})
        self.mission_type = type("o", (), {"value": "urban_delivery"})


@app.get("/")
def root():
    return {"name": "DroneSync", "version": "1.0", "status": "online", "network": "konnex-testnet"}


@app.get("/drone/status")
def drone_status():
    status = reputation.get_status()
    return {
        "drone_id": "DRONE_001",
        "reputation_score": status["reputation_score"],
        "tier": status["tier"],
        "on_chain_ready": True,
        "network": "konnex-testnet"
    }


@app.post("/mission/run")
def run_mission():
    mission = FakeMission()
    trajectory = planner.plan_trajectory(mission)
    sensor_data = env.run(trajectory)
    score = validator.score(trajectory, sensor_data)
    record = popw.create_record(mission.mission_id, trajectory, score)

    reputation.record_mission(mission.mission_id, score, True, 7.0)
    scoreroot.add_score(mission.mission_id, score, record["trajectory_hash"], "sensor_hash_001")
    commitment = scoreroot.commit()

    bundle = SensorBundle().pack(mission.mission_id, trajectory, sensor_data, record)
    from dronesync.economics import RewardCalculator
    _calc = RewardCalculator()
    _reward = _calc.calculate(mission.mission_id, score/100.0, "EXCELLENT" if score >= 85 else "GOOD" if score >= 70 else "POOR", "ACTIVE")


    return {
        "mission_id": mission.mission_id,
        "score": score,
        "popw": {
            "trajectory_hash": record["trajectory_hash"][:16] + "...",
            "attestation_id": record["attestation"]["attestation_id"],
            "tee_status": record["attestation"]["status"],
            "on_chain_string": popw.format_for_chain(record)
        },
        "bundle_hash": bundle["bundle_hash"][:16] + "...",
        "score_root": commitment["score_root"][:16] + "...",
        "on_chain_ready": True,
        "reward_knx": _reward.to_dict()
    }


@app.get("/popw/latest")
def popw_latest():
    if not scoreroot.commitments:
        return {"status": "no missions yet"}
    c = scoreroot.commitments[-1]
    return {
        "score_root": c["score_root"],
        "scores_count": c["scores_count"],
        "validator_id": c["validator_id"],
        "on_chain_ready": True
    }


@app.get("/validator/scoreroot")
def get_scoreroot():
    commitment = scoreroot.commit()
    return commitment
