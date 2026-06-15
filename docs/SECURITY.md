# DroneSync — Security Model

## One Line

DroneSync protects autonomous drone missions against physical and cyber threats
using cryptographic proofs, rate limiting, and Byzantine-aware consensus.

---

## Threat Model

| Threat | Attack | Protection |
|--------|--------|------------|
| GPS Spoofing | Fake coordinates sent to drone | Coordinate range validation + trajectory anomaly detection |
| Replay Attack | Reuse old mission_id | ReplayGuard — persists seen IDs to disk |
| Command Injection | Unsigned commands | HMAC-SHA256 signature on every command |
| Byzantine Drones | Malicious swarm members | Consensus QUORUM 0.67 — 2/3 majority required |
| Storage Tampering | Modify saved mission data | SHA256 integrity hash on every storage write |
| Rate Abuse | Flood drone with commands | DroneFirewall — 20 commands/minute limit |

---

## Security Assumptions

- System is secure while malicious participants remain below 33% of swarm
- If malicious nodes exceed QUORUM threshold, consensus can be manipulated
- ReplayGuard persists to disk — survives restart
- Storage integrity is verified on every load

---

## What is Protected

- GPS coordinates validated: lat [-90, 90], lon [-180, 180]
- Mission IDs: unique, tracked, replay blocked
- Commands: HMAC-SHA256 signed, timestamp verified
- Storage: SHA256 integrity hash, corruption recovery
- Swarm: Byzantine fault tolerant up to 33% malicious nodes

---

## What is NOT Protected

- Network-level DDoS attacks
- Physical drone hardware tampering
- Compromised TEE hardware
- Validator collusion above QUORUM threshold

---

## Security Audit Results

See latest results by running:

```bash
pytest -q
ruff check .
mypy .
bandit -r dronesync/
pip-audit

---

## References

- [CONSENSUS.md](CONSENSUS.md) — Byzantine fault tolerance details
- [POPW.md](POPW.md) — Proof of Physical Work specification
- [API.md](API.md) — API reference
