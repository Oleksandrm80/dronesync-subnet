from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dronesync.auth import get_auth_db, Client, ROLE_PERMISSIONS
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import time
import uuid

from miner.planner import DronePlanner
from environment.sim import DroneEnvironment
from validator.scorer import DroneEvaluator
from dronesync.verifier import PoPWRecord
from dronesync.reputation import DroneReputation
from dronesync.sensor_bundle import SensorBundle
from validator.scoreroot import ScoreRoot
from dronesync.identity import DRONE_ID, VALIDATOR_ID


app = FastAPI(title="DroneSync API", version="1.0")

_security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(_security)) -> Client:
    client = get_auth_db().verify_key(credentials.credentials)
    if not client:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return client

def require_permission(permission: str):
    def checker(client: Client = Depends(verify_token)) -> Client:
        if permission not in client.permissions:
            raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
        return client
    return checker

planner = DronePlanner()
validator = DroneEvaluator()
env = DroneEnvironment()
popw = PoPWRecord()
reputation = DroneReputation(DRONE_ID)
scoreroot = ScoreRoot(VALIDATOR_ID)


class Waypoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    alt: float = Field(..., gt=0)
    speed: float = Field(default=5.0, gt=0)


class MissionRequest(BaseModel):
    origin: Waypoint
    destination: Waypoint
    waypoints: List[Waypoint] = Field(default_factory=list)
    drone_id: str = Field(default=DRONE_ID)
    mission_type: str = Field(default="urban_delivery")

    @field_validator("mission_type")
    @classmethod
    def validate_mission_type(cls, v: str) -> str:
        allowed = {"urban_delivery", "survey", "inspection", "emergency", "cargo"}
        if v not in allowed:
            raise ValueError(f"mission_type must be one of {allowed}")
        return v


class _WP:
    def __init__(self, lat, lon, alt, speed):
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.speed = speed


class _Mission:
    def __init__(self, req: MissionRequest):
        self.mission_id = "DSYNC_" + uuid.uuid4().hex[:12].upper()
        self.origin = _WP(req.origin.lat, req.origin.lon, req.origin.alt, req.origin.speed)
        self.destination = _WP(req.destination.lat, req.destination.lon, req.destination.alt, req.destination.speed)
        self.waypoints = [_WP(w.lat, w.lon, w.alt, w.speed) for w in req.waypoints]
        self.mission_type = type("MT", (), {"value": req.mission_type})
        self.drone_id = req.drone_id


@app.get("/")
def root():
    return {"name": "DroneSync", "version": "1.0", "status": "online", "network": "konnex-testnet"}


@app.get("/drone/status")
def drone_status():
    status = reputation.get_status()
    return {
        "drone_id": DRONE_ID,
        "reputation_score": status["reputation_score"],
        "tier": status["tier"],
        "on_chain_ready": True,
        "network": "konnex-testnet"
    }


@app.post("/mission/run")
def run_mission(req: MissionRequest):
    mission = _Mission(req)
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
    tier = "EXCELLENT" if score >= 85 else "GOOD" if score >= 70 else "POOR"
    _reward = _calc.calculate(mission.mission_id, score / 100.0, tier, "ACTIVE")

    return {
        "mission_id": mission.mission_id,
        "drone_id": mission.drone_id,
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

# ── Admin endpoints — управление клиентами ─────────────────────────────────

class CreateClientRequest(BaseModel):
    name: str
    role: str  # admin | fleet_manager | operator | validator | customer

@app.post("/admin/clients/create")
def create_client(req: CreateClientRequest, client: Client = Depends(require_permission("admin:all"))):
    try:
        result = get_auth_db().create_client(req.name, req.role)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/clients")
def list_clients(client: Client = Depends(require_permission("admin:all"))):
    return get_auth_db().list_clients()

@app.post("/admin/clients/{client_id}/revoke")
def revoke_client(client_id: str, client: Client = Depends(require_permission("admin:all"))):
    get_auth_db().revoke_client(client_id)
    return {"status": "revoked", "client_id": client_id}

@app.get("/admin/stats")
def get_stats(client: Client = Depends(require_permission("admin:all"))):
    return get_auth_db().get_stats()

@app.get("/me")
def get_me(client: Client = Depends(verify_token)):
    return {
        "client_id": client.client_id,
        "name": client.name,
        "role": client.role,
        "permissions": list(client.permissions),
        "request_count": client.request_count,
    }
