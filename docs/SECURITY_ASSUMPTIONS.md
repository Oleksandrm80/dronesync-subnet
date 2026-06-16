# DroneSync — Security Assumptions

## One Line

DroneSync is secure under the following assumptions.
If any assumption is violated, the security guarantees no longer hold.

---

## Assumptions

### 1. Honest Nodes > 67%
At least 2/3 of swarm nodes are honest at any given time.
If malicious nodes exceed 33%, consensus can be manipulated.

### 2. GPS Valid After Validation
Coordinates passing lat/lon/altitude validation are considered trustworthy.
DroneSync does not protect against hardware-level GPS spoofing.

### 3. ReplayGuard Persistence
ReplayGuard append-only log survives restart.
If the log file is deleted, replay attacks become possible.

### 4. Storage Integrity
SHA256 integrity hash is verified on every storage load.
If storage is tampered, system returns _tampered=True and halts.

### 5. Deterministic Scoring
Same mission input always produces same score.
Validator logic must not contain random or time-dependent elements.

### 6. TEE Simulation
Current TEE is simulated (SGX_SIM_001).
In production, real TEE hardware is required for hardware-grade guarantees.

### 7. Timestamp Trust Window
Missions with timestamp older than MAX_AGE_SECONDS are rejected.
Missions with timestamp more than 300 seconds in the future are rejected.

### 8. Rate Limiting
DroneFirewall limits to 20 commands per minute per drone.
Does not protect against distributed rate abuse from multiple sources.

---

## What Breaks If Assumptions Fail

| Assumption Violated | Consequence |
|---------------------|-------------|
| Honest nodes < 67% | Malicious consensus possible |
| GPS spoofed at hardware level | Invalid trajectory accepted |
| ReplayGuard log deleted | Same mission processed twice |
| Storage tampered | Data integrity lost |
| TEE compromised | PoPW signatures untrustworthy |
| Rate limit bypassed | Drone flooded with commands |

---

## References

- [SECURITY.md](SECURITY.md) — Threat model
- [CONSENSUS.md](CONSENSUS.md) — Consensus model
- [POPW.md](POPW.md) — PoPW specification
