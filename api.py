from fastapi import FastAPI, HTTPException, Depends, Security, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dronesync.auth import get_auth_db, Client
from pydantic import BaseModel, Field, field_validator
from typing import List
import uuid

from miner.planner import DronePlanner
from environment.sim import DroneEnvironment
from validator.scorer import DroneEvaluator
from dronesync.verifier import PoPWRecord
from dronesync.reputation import DroneReputation
from dronesync.sensor_bundle import SensorBundle
from validator.scoreroot import ScoreRoot
from dronesync.identity import DRONE_ID, VALIDATOR_ID
from dronesync.webhook import send_webhook


app = FastAPI(title="DroneSync API", version="1.0")
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: __import__("fastapi").responses.JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}))
app.add_middleware(SlowAPIMiddleware)

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


class LiveMissionRequest(BaseModel):
    manufacturer: str = Field(default="mavlink")
    connection: str = Field(default="udp:127.0.0.1:14550")
    duration_seconds: int = Field(default=30, ge=5, le=60)
    poll_hz: int = Field(default=5, ge=1, le=20)

    @field_validator("manufacturer")
    @classmethod
    def validate_manufacturer(cls, v: str) -> str:
        allowed = {"mavlink", "dji", "ros2"}
        if v not in allowed:
            raise ValueError(f"manufacturer must be one of {allowed}")
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
def drone_status(client: Client = Depends(require_permission("mission:read"))):
    status = reputation.get_status()
    return {
        "drone_id": DRONE_ID,
        "reputation_score": status["reputation_score"],
        "tier": status["tier"],
        "on_chain_ready": True,
        "network": "konnex-testnet"
    }


@app.post("/mission/run")
@limiter.limit("10/minute")
def run_mission(request: Request, req: MissionRequest, client: Client = Depends(require_permission("mission:run"))):
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

    send_webhook(client.client_id, "mission.completed", {"mission_id": mission.mission_id, "score": score, "on_chain_ready": True})
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


@app.post("/mission/run-live")
@limiter.limit("5/minute")
def run_mission_live(request: Request, req: LiveMissionRequest, client: Client = Depends(require_permission("mission:run"))):
    """
    Runs a mission from a REAL connected drone (MAVLink/DJI/ROS2) instead of
    the simulator. Blocks for req.duration_seconds while recording telemetry
    (capped at 60s) -- FastAPI runs sync endpoints in a threadpool, so this
    does not block other requests.
    """
    from dronesync.drone_connector import DroneConnector

    connector = DroneConnector(manufacturer=req.manufacturer, connection=req.connection)

    try:
        connected = connector.connect()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Drone connection error: {e}")

    if not connected:
        raise HTTPException(status_code=502, detail="Could not connect to drone (no heartbeat within timeout)")

    try:
        trajectory, sensor_data = connector.record_mission(
            duration_seconds=req.duration_seconds, poll_hz=req.poll_hz
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Telemetry recording failed: {e}")
    finally:
        connector.disconnect()

    if not trajectory.positions:
        raise HTTPException(status_code=422, detail="No GPS telemetry captured during recording window")

    score = validator.score(trajectory, sensor_data)
    mission_id = "DSYNC_LIVE_" + uuid.uuid4().hex[:12].upper()
    record = popw.create_record(mission_id, trajectory, score)

    reputation.record_mission(mission_id, score, True, 7.0)
    scoreroot.add_score(mission_id, score, record["trajectory_hash"], "sensor_hash_001")
    commitment = scoreroot.commit()

    bundle = SensorBundle().pack(mission_id, trajectory, sensor_data, record)
    from dronesync.economics import RewardCalculator
    _calc = RewardCalculator()
    tier = "EXCELLENT" if score >= 85 else "GOOD" if score >= 70 else "POOR"
    _reward = _calc.calculate(mission_id, score / 100.0, tier, "ACTIVE")

    send_webhook(client.client_id, "mission.completed", {
        "mission_id": mission_id, "score": score, "on_chain_ready": True,
        "source": req.manufacturer,
    })

    return {
        "mission_id": mission_id,
        "source": req.manufacturer,
        "telemetry": {
            "frame_count": trajectory.metadata.get("frame_count", len(trajectory.positions)),
            "duration_s": trajectory.metadata.get("duration_s", 0),
            "max_altitude": trajectory.metadata.get("max_altitude", 0),
            "max_speed": trajectory.metadata.get("max_speed", 0),
            "avg_battery": trajectory.metadata.get("avg_battery", 0),
        },
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
def popw_latest(client: Client = Depends(require_permission("mission:read"))):
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
def get_scoreroot(client: Client = Depends(require_permission("validator:read"))):
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


# ── Webhook endpoints ──────────────────────────────────────────────────────

class WebhookRegisterRequest(BaseModel):
    url: str
    secret: str

@app.post("/webhooks/register")
def register_webhook(req: WebhookRegisterRequest, client: Client = Depends(verify_token)):
    from dronesync.webhook import get_webhook_db
    result = get_webhook_db().register(client.client_id, req.url, req.secret)
    return result

@app.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: int, client: Client = Depends(verify_token)):
    from dronesync.webhook import get_webhook_db
    if not get_webhook_db().deactivate(webhook_id, client.client_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deactivated", "webhook_id": webhook_id}

@app.get("/webhooks")
def list_webhooks(client: Client = Depends(verify_token)):
    from dronesync.webhook import get_webhook_db
    hooks = get_webhook_db().get_webhooks(client.client_id)
    return [{"id": h["id"], "url": h["url"]} for h in hooks]


# ── Proof of Delivery ──────────────────────────────────────────────────────

class DeliveryRequest(BaseModel):
    mission_id: str
    destination_lat: float = Field(..., ge=-90, le=90)
    destination_lon: float = Field(..., ge=-180, le=180)
    actual_lat: float = Field(..., ge=-90, le=90)
    actual_lon: float = Field(..., ge=-180, le=180)
    altitude: float = Field(default=50.0, gt=0)
    camera_detections: list = Field(default_factory=list)

@app.post("/delivery/prove")
def prove_delivery(req: DeliveryRequest, client: Client = Depends(require_permission("mission:run"))):
    from dronesync.proof_of_delivery import ProofOfDelivery
    pod = ProofOfDelivery()
    snapshot = pod.create_snapshot(
        mission_id=req.mission_id,
        destination_lat=req.destination_lat,
        destination_lon=req.destination_lon,
        actual_lat=req.actual_lat,
        actual_lon=req.actual_lon,
        altitude=req.altitude,
        camera_detections=req.camera_detections,
    )
    proof = pod.prove(snapshot)
    send_webhook(client.client_id, "delivery.proved", proof.to_dict())
    return proof.to_dict()
