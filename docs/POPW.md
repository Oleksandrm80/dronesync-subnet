# DroneSync — Proof of Physical Work (PoPW)

## One Line

PoPW is a cryptographic proof that an autonomous drone mission
was physically executed, validated, and approved by swarm consensus.

---

## Why PoPW?

Traditional blockchains use Proof of Work (computation) or
Proof of Stake (capital). DroneSync introduces Proof of Physical Work —
proof that real-world autonomous work was performed and verified.

---

## PoPW Chain

Mission
↓
Planner builds route
↓
Drone executes mission
↓
Execution Trace collected (trajectory, sensors, telemetry)
↓
Validator scores the trace
↓
TEE signs the result (hardware attestation)
↓
Swarm consensus approves (QUORUM 0.67)
↓
PoPW record stored immutably
↓
External Verification possible at any time

---

## PoPW Record Structure

mission_id        — unique mission identifier
trajectory_hash   — SHA256 of flight path
sensor_hash       — SHA256 of sensor bundle
score             — validator score (0-100)
attestation_id    — TEE attestation identifier
tee_status        — SIGNED / PENDING
popw_signature    — cryptographic signature
on_chain_ready    — True when ready for submission

---

## TEE Attestation

Every PoPW is signed by a Trusted Execution Environment (TEE):

- Hardware-grade proof of execution
- Tamper-proof: signature invalid if data modified
- attestation_id links PoPW to hardware session
- tee_version tracks which TEE version signed the record

---

## Immutable History

Every mission is stored with SHA256 chain linking:

mission_1_hash = SHA256(mission_1_data)
mission_2_hash = SHA256(mission_2_data + mission_1_hash)
mission_N_hash = SHA256(mission_N_data + mission_(N-1)_hash)

Modifying any past mission invalidates all subsequent hashes.

---

## External Verification

Any external system can verify a PoPW record:

1. Check trajectory_hash matches flight data
2. Check TEE signature is valid
3. Check consensus approved the mission
4. Check mission_id not in replay guard
5. Check chain hash integrity

---

## References

- [SECURITY.md](SECURITY.md) — Threat model
- [CONSENSUS.md](CONSENSUS.md) — Consensus model
- [API.md](API.md) — API reference
