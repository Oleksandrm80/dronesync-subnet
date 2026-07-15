# DroneSync API Reference

Two API surfaces exist in this codebase:

- **REST API** (`api.py`) — the public HTTP interface. This is what external
  clients (dashboards, partner integrations, testers) actually talk to.
- **Synapse handler** (`dronesync/synapse.py`) — the internal Konnex
  validator-task interface used by miner/validator nodes directly, not over
  HTTP. See "Internal Synapse Handler" below.

---

## REST API (`api.py`)

Base URL: `http://<host>:8080` (as run by `main.py` / the `miner` Docker
service; not currently served by `main.py` itself — run via
`uvicorn api:app` or similar ASGI server).

### Authentication

Every endpoint except `/` requires an API key, sent as a Bearer token:

    Authorization: Bearer ds_<your_api_key>

Keys are created via `POST /admin/clients/create` (admin only) and are
tied to a **role**, which grants a fixed set of permissions:

| Role | Permissions |
|------|-------------|
| `admin` | `mission:run`, `mission:read`, `fleet:manage`, `validator:vote`, `admin:all` |
| `fleet_manager` | `mission:run`, `mission:read`, `fleet:manage` |
| `operator` | `mission:run`, `mission:read` |
| `validator` | `mission:read`, `validator:vote` |
| `customer` | `delivery:track` |

A request without a valid key returns `401`; a valid key lacking the
required permission for an endpoint returns `403`.

Rate limits: 60 requests/minute per client by default, `/mission/run` is
additionally capped at 10/minute.

### `GET /`

No auth required. Health/status check.

    { "name": "DroneSync", "version": "1.0", "status": "online", "network": "konnex-testnet" }

### `GET /drone/status`

Requires: `mission:read`

    { "drone_id": str, "reputation_score": int, "tier": str,
      "on_chain_ready": bool, "network": str }

### `POST /mission/run`

Requires: `mission:run`. Rate limit: 10/min.

Runs a full mission through the pipeline: **simulated** telemetry
(`environment/sim.py::DroneEnvironment`, not a real drone), scoring,
PoPW record creation, sensor bundle, score-root commitment, and reward
calculation. Fires a `mission.completed` webhook on success.

Request body:

    {
      "origin": {"lat": float, "lon": float, "alt": float, "speed": float=5.0},
      "destination": {"lat": float, "lon": float, "alt": float, "speed": float=5.0},
      "waypoints": [{"lat": float, "lon": float, "alt": float, "speed": float}],
      "drone_id": str,
      "mission_type": "urban_delivery" | "survey" | "inspection" | "emergency" | "cargo"
    }

Response:

    {
      "mission_id": str, "drone_id": str, "score": int,
      "popw": {"trajectory_hash": str, "attestation_id": str,
               "tee_status": str, "on_chain_string": str},
      "bundle_hash": str, "score_root": str,
      "on_chain_ready": bool, "reward_knx": {...}
    }

> **Note:** there is no endpoint yet that runs a mission from a real
> connected drone (MAVLink/DJI/ROS2) instead of the simulator — see
> `dronesync/drone_connector.py::DroneConnector.record_mission()` for the
> adapter code that exists but is not wired into this API.

### `GET /popw/latest`

Requires: `mission:read`. Returns the most recent score-root commitment,
or `{"status": "no missions yet"}` if none exist yet.

### `GET /validator/scoreroot`

Requires: `validator:read` (granted to the `validator` and `admin` roles).

### Admin endpoints — client management

All require `admin:all`.

- `POST /admin/clients/create` — body `{"name": str, "role": str}` →
  returns the new client's `api_key` **once** (not retrievable again).
- `GET /admin/clients` — list all clients (no API keys included).
- `POST /admin/clients/{client_id}/revoke` — deactivate a client's key.
- `GET /admin/stats` — `{total_clients, active_clients, total_requests}`.

### `GET /me`

Requires: any valid key. Returns the calling client's own profile.

### Webhooks

- `POST /webhooks/register` — body `{"url": str, "secret": str}`. Secret
  is encrypted at rest (Fernet) and used to HMAC-sign outgoing webhook
  payloads (`X-DroneSync-Signature` header).
- `GET /webhooks` — list the caller's own webhooks (id + url only).
- `DELETE /webhooks/{webhook_id}` — deactivate; `404` if the id doesn't
  belong to the caller.

### `POST /delivery/prove`

Requires: `mission:run`. Creates a Proof-of-Delivery snapshot (destination
vs. actual landing coordinates + camera detections) and fires a
`delivery.proved` webhook.

    {
      "mission_id": str,
      "destination_lat": float, "destination_lon": float,
      "actual_lat": float, "actual_lon": float,
      "altitude": float=50.0,
      "camera_detections": [...]
    }

---

## Internal Synapse Handler (`dronesync/synapse.py`)

Used by miner/validator nodes internally (not over HTTP) — this is what
`main.py`'s demo and the dashboard drive directly.

### `DroneNavSynapseHandler`

    DroneNavSynapseHandler(drone_id: str = "DRONE_001", use_ai_planner: bool = False)
    handler.handle(synapse_task: dict) -> dict

Input fields: `task_id`, `mission_type`, `origin`, `destination`,
`waypoints`, `drone_count`, `payload_kg`.

Response fields: `mission_id`, `status` (`OK`/`BLOCKED`/`REJECTED`/`ERROR`),
`score`, `trajectory_hash`, `sensor_hash`, `tee_status`, `on_chain_ready`,
`proof_package`.

### `SwarmSynapseHandler`

    SwarmSynapseHandler(drone_ids: list[str])
    handler.handle_swarm_task(synapse_task: dict) -> dict

Response fields: `swarm_mission_id`, `avg_score`, `swarm_approved`,
`consensus`, `on_chain_ready`.

---

## Shared building blocks

### `MissionHistory`

Immutable hash-chained mission log.

    add(mission_id, score, duration_s, battery_used, weather, security) -> None
    verify_chain() -> bool
    stats() -> dict
    last(n: int = 3) -> list

### `ReplayGuard`

    check(mission_id: str, created_at: float) -> dict
    # Returns: {"allowed": bool, "reason": str}

### `DroneFirewall`

    filter(command: dict) -> dict
    # Returns: {"status": "ALLOWED" or "BLOCKED", "reason": str}

---

## Error Codes (Synapse handler)

  OK        Mission completed successfully
  BLOCKED   Firewall rejected command
  REJECTED  Replay attack detected
  ERROR     Unexpected pipeline error
