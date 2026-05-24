# DroneSync Architecture

## Overview

DroneSync implements a three-layer architecture on top of Konnex L1:

### Layer 1: Mission Registry (On-chain)
- Mission instructions hashed and stored on Konnex L1
- Each instruction_hash is unique and immutable
- Reward (KNX) locked in escrow until mission scored

### Layer 2: Miner Network (Off-chain compute)
- Miners receive mission instructions from chain
- Run urban path planning algorithms locally
- Submit trajectory + sensor fusion data as PoPW candidates

### Layer 3: Validator Network (Off-chain scoring)
- Validators score independently
- 4 criteria: Safety 40%, Task Match 30%, Efficiency 20%, Sensor 10%
- Consensus score triggers PoPW artifact on-chain

## PoPW Artifact

{
  "mission_id": "dsync_001",
  "instruction_hash": "sha256:abc...",
  "trajectory_root": "sha256:def...",
  "sensor_data_root": "sha256:ghi...",
  "final_score": 0.87
}

## DroneSync vs drone-navigation

Feature          | drone-navigation | DroneSync
Focus            | Single drone     | Multi-drone swarm
Environment      | Open areas       | Dense urban
Mission types    | Basic nav        | 5 urban types
Safety model     | Basic            | Full no-fly+wind+battery
Use case         | Research         | Real urban delivery