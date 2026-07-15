# DroneSync — Proof of Physical Work for Autonomous Drone Networks

> An open framework for cryptographic verification of real-world drone missions.
> Every flight produces a tamper-evident PoPW record — signed, validated by
> decentralized consensus, and ready for on-chain settlement.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-Apache%202.0-green)
![Tests](https://img.shields.io/badge/Tests-583%20passing-brightgreen)
![Status](https://img.shields.io/badge/Status-Working%20Demo-brightgreen)
![ZK](https://img.shields.io/badge/ZK-Groth16-purple)

---

## What is DroneSync?

DroneSync is a protocol for verifying physical work performed by autonomous drones.

Traditional blockchains verify **computation**.
Traditional AI networks verify **inference**.
DroneSync verifies **physical work**.

Every mission produces a cryptographic Proof of Physical Work (PoPW) --
signed with Ed25519, protected by Groth16 zero-knowledge proofs,
and approved by reputation-weighted Byzantine-tolerant consensus.

    Mission -> Planner -> Telemetry -> Ed25519 Sign -> ZK Proof -> Validator Consensus -> On-Chain

---

## Key Features

- **PoPW Protocol** -- cryptographic proof that a drone completed a real mission
- **Zero-Knowledge Proofs** -- Groth16 (circom + snarkjs) proves mission validity without revealing waypoints
- **Reputation-Weighted Consensus** -- ELITE 4x / TRUSTED 3x / ACTIVE 2x / ROOKIE 1x
- **Byzantine Fault Detection** -- automatic blacklist of malicious validators
- **ReplayGuard** -- 1-hour deduplication window prevents replay attacks
- **Validator Auth** -- HMAC-SHA256 inter-validator authentication
- **AI Planner** -- learns from validator feedback, optimizes safety/efficiency/energy
- **Federated Learning** -- drones improve together without sharing raw flight data
- **MAVLink Adapter** -- bridge for real drone hardware integration
- **Live Dashboard** -- Neural Cosmos visualization, real-time telemetry

---

## Architecture

    +--------------------------------------------------------------+
    |                      DroneSync Node                          |
    |                                                              |
    |  Mission Planner -> PoPW Verifier -> Swarm Consensus        |
    |  Sensor Bundle  -> ReplayGuard   -> ZK Prover (Groth16)     |
    |  Reward Engine  -> Validator Auth -> On-Chain Submission     |
    +--------------------------------------------------------------+

---

## Modules

| Module | Path | Description |
|--------|------|-------------|
| PoPW Verifier | dronesync/verifier.py | Record creation, Ed25519 signing |
| Swarm Consensus | dronesync/swarm_consensus.py | Weighted voting, Byzantine detection |
| ReplayGuard | dronesync/replay_guard.py | 1-hour dedup, replay prevention |
| ZK Prover | dronesync/zk_prover.py | Groth16 proof generation + verification |
| Validator Auth | dronesync/validator_auth.py | HMAC-SHA256 inter-validator auth |
| Mission Planner | miner/planner.py | Basic + AI trajectory planning |
| Reward Engine | dronesync/economics.py | Reward calculation, tier multipliers |
| Federated Learning | dronesync/federated_learning.py | Privacy-preserving model aggregation |
| MAVLink Adapter | dronesync/mavlink_adapter.py | Physical drone protocol bridge |
| Validator Network | dronesync/validator_network.py | WebSocket validator mesh |
| Wallet | dronesync/wallet.py | Transaction history, balance tracking |
| Dashboard | dashboard/app.py | Web monitoring interface |

---

## Demo Scripts

    python demo_depin.py              # Full DePIN cycle -- missions, rewards, wallet
    python demo_federated.py          # Federated learning across drone fleet
    python demo_validator_network.py  # Validator consensus network
    python demo_zk_proof.py           # Zero-knowledge proof generation + verification
    python demo_mavlink.py            # MAVLink telemetry bridge (requires drone)

---

## Testing

    # Run all 583 tests
    python -m pytest tests/ -v

    # Run by category
    python -m pytest tests/test_security.py -v
    python -m pytest tests/test_chaos.py -v
    python -m pytest tests/test_zk_setup.py -v
    python -m pytest tests/test_integration.py -v

583 tests passing across 45 test files -- unit, integration, security,
chaos, concurrency, mutation, property-based, and ZK proof tests.

---

## Security

| Threat | Mitigation |
|--------|-----------|
| GPS spoofing | Multi-waypoint consistency + IMU cross-validation |
| Telemetry fabrication | Ed25519 hardware signature + consensus |
| Replay attacks | ReplayGuard 1-hour dedup window |
| Route exposure | Groth16 ZK proofs -- waypoints never revealed |
| Unauthorized validators | HMAC-SHA256 auth, 30s TTL + nonce |
| Byzantine validators | Reputation detector, auto-blacklist |

---

## Roadmap

- [x] PoPW engine -- Ed25519 signing, SHA256 hashing
- [x] Reputation-weighted consensus
- [x] ReplayGuard -- replay attack prevention
- [x] ZK proof system -- Groth16 (circom + snarkjs)
- [x] Validator auth -- HMAC-SHA256
- [x] AI trajectory planner
- [x] Federated learning
- [x] MAVLink adapter
- [x] Live dashboard -- Neural Cosmos visualization
- [x] 583 passing tests
- [ ] Real drone hardware integration wired into the REST API (adapter code exists — MAVLink/DJI/ROS2 — but `/mission/run` still uses simulated telemetry)
- [ ] Live Konnex chain connection (currently simulated locally end-to-end pending the Konnex SDK)
- [ ] Decentralized network deployment (validator mesh protocol exists, not yet tested across multiple real machines)
- [ ] Security audit
- [ ] Domain + HTTPS

---

## License

Apache 2.0 -- Copyright 2024 Oleksandr Malchev

Contributions welcome via pull requests.

## Konnex Network — NETUID 4

DroneSync is built as a subnet on Konnex — a decentralized network for physical-world AI.

- **NETUID**: 4
- **Network**: konnex-testnet
- **Category**: Drone navigation & swarm coordination + Sensor fusion & PoPW validation
- **Token**: KNX (earned by drone operators for completing verified missions)

### How it works

1. Drone operator runs DroneSync miner node
2. Drone executes mission → generates PoPW proof
3. Validator verifies proof → sets weights on-chain
4. Operator earns KNX tokens proportional to mission quality

> **Current status:** the Konnex chain itself is not live yet -- the full
> pipeline above runs end-to-end today with real signing, real ZK proofs,
> and a locally simulated chain layer (`KonnexNode`, `TxQueue`) standing in
> for the on-chain submission until the Konnex SDK is released. See Roadmap.

---

## Quick Start

### Option 1 — Docker (recommended)

    git clone https://github.com/oleksandrm80/dronesync-subnet.git
    cd dronesync-subnet
    cp .env.example .env
    docker compose up -d

Services: Miner on port 8080, Dashboard on port 8888.

### Option 2 — Local

    git clone https://github.com/oleksandrm80/dronesync-subnet.git
    cd dronesync-subnet
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    python3 main.py

### Connect a real drone (MAVLink)

    python3 demo_mavlink.py /dev/ttyUSB0          # USB
    python3 demo_mavlink.py udp:192.168.1.10:14550 # WiFi/4G
    python3 demo_mavlink.py --emulator             # No drone needed
