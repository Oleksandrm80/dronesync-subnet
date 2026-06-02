# DroneSync Subnet — Roadmap

## Current State (Done)
- Mission planning with computation trace (planner_steps)
- Replay validation — VERIFIED / REJECTED
- Swarm collision avoidance (predictive, all time steps)
- TEE attestation + PoPW record (on-chain ready)
- GPS spoofing detection
- Signal jamming detection
- HMAC command signing + replay attack prevention
- Dynamic obstacles
- Weather impact analysis
- Energy optimizer
- City no-fly zones (Zurich, Berlin, Kyiv)
- Mission history + statistics
- KonnexNode (testnet ready, awaiting SDK)
- 32 tests passing

---

## Phase 1 — After Grant Approval (Month 1)

### Security
- **Drone Firewall** — filter all incoming commands, log blocked attempts in PoPW
- **Swarm Blacklist** — compromised drone voted out by the swarm automatically
- **Zero Trust Flight** — re-verify every command every 5 seconds, fully automatic
- **Post-Quantum Signatures** — quantum-resistant cryptography for 20+ year protection

### Reputation
- **Drone Reputation Score** — on-chain rating per drone, better score = better missions + more tokens

---

## Phase 2 — Unique Features (Month 2)

- **Drone Last Will** — on crash, drone sends final PoPW with coordinates + diagnostics automatically
- **Bio-inspired Routing** — routes strengthen like ant trails, bad paths disappear naturally
- **Drone Memory** — each drone accumulates flight experience stored on-chain, experience = asset value
- **Swarm Consensus** — swarm votes on route before executing, no central operator needed
- **Emergency Override Protocol** — city emergency signal redirects all drones in area instantly

---

## Phase 3 — Ecosystem (Month 3)

- **Mission Marketplace** — companies post jobs, drones take them, smart contract pays on PoPW confirm
- **Environmental Proof** — drone collects air quality / temperature data during flight, sold to cities
- **Swarm Insurance Pool** — all nodes contribute, automatic payout on mission failure
- **Proof of Airspace** — verified flight path data sold to insurance / logistics / cities
- **Drone Last Mile Consensus** — swarm confirms landing zone is clear before touchdown

---

## Phase 4 — Asset Layer (Month 4+)

- **Drone NFT Identity** — each drone is an NFT with full flight history and reputation
- **Carbon Credit** — electric missions generate verified carbon offset tokens
- **Proof of Silence** — idle drone gets reputation penalty, incentive to stay active

---

## Konnex Integration (After SDK)

- Replace KonnexNode stub with real SDK
- Real on-chain PoPW submission
- Testnet node running 24/7
- Mainnet launch
