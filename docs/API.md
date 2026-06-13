# DroneSync API Reference

## DroneNavSynapseHandler

Main handler for Konnex validator tasks (NETUID 4).

### Constructor

    DroneNavSynapseHandler(drone_id: str = "DRONE_001", use_ai_planner: bool = False)

### handle(synapse_task: dict) -> dict

Executes full DroneSync pipeline and returns PoPW artifact.

Input fields:
  task_id       str    Unique mission identifier
  mission_type  str    e.g. urban_delivery
  origin        dict   {lat, lon, alt, speed}
  destination   dict   {lat, lon, alt, speed}
  waypoints     list   List of {lat, lon, alt, speed}
  drone_count   int    Number of drones
  payload_kg    float  Payload weight

Response fields:
  mission_id       str   Mission identifier
  status           str   OK, BLOCKED, REJECTED, ERROR
  score            int   Mission score 0-100
  trajectory_hash  str   SHA256 of trajectory
  sensor_hash      str   SHA256 of sensor bundle
  tee_status       str   TEE attestation status
  on_chain_ready   bool  Ready for blockchain submission
  proof_package    dict  chain_string for on-chain scoring

---

## SwarmSynapseHandler

Handles multi-drone swarm tasks with consensus voting.

### Constructor

    SwarmSynapseHandler(drone_ids: list[str])

### handle_swarm_task(synapse_task: dict) -> dict

Response fields:
  swarm_mission_id  str    Mission identifier
  avg_score         float  Average score across drones
  swarm_approved    bool   Consensus approval result
  consensus         dict   Voting details
  on_chain_ready    bool   All drones ready

---

## MissionHistory

Immutable blockchain-style mission log.

  add(mission_id, score, duration_s, battery_used, weather, security) -> None
  verify_chain() -> bool
  stats() -> dict
  last(n: int = 3) -> list

---

## ReplayGuard

Prevents replay attacks on mission submissions.

  check(mission_id: str, created_at: float) -> dict
  Returns: {"allowed": bool, "reason": str}

---

## DroneFirewall

HMAC-signed command filtering with rate limiting.

  filter(command: dict) -> dict
  Returns: {"status": "ALLOWED" or "BLOCKED", "reason": str}

---

## Error Codes

  OK        Mission completed successfully
  BLOCKED   Firewall rejected command
  REJECTED  Replay attack detected
  ERROR     Unexpected pipeline error
