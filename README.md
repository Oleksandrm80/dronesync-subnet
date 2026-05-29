# 🚁 DroneSync — Urban Drone Swarm Subnet on Konnex

> Konnex subnet for coordinating autonomous drone swarms in urban environments using Proof-of-Physical-Work (PoPW) consensus, real-time sensor fusion, and on-chain mission validation.

![Konnex](https://img.shields.io/badge/Konnex-Testnet-orange)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Prototype-yellow)

## What is DroneSync?

DroneSync is a Konnex subnet (NETUID: TBA) that enables decentralized coordination of drone swarms in complex urban environments:

- Multi-drone collision avoidance in dense urban airspace
- Last-mile delivery route optimization with dynamic obstacle handling
- On-chain mission validation via PoPW
- Sensor fusion scoring by validators

## Architecture

- Miners: receive missions, run urban path planner, submit trajectory + sensor data
- Validators: score submissions on Safety(40%), Task Match(30%), Efficiency(20%), Sensor Quality(10%)
- Chain: stores instruction hash, trajectory root, sensor root, PoPW artifact

## Mission Types

- URBAN_DELIVERY — last-mile package delivery
- SWARM_SURVEY — multi-drone area mapping
- OBSTACLE_RACE — dynamic obstacle avoidance
- FORMATION_FLY — coordinated swarm formation
- EMERGENCY_ROUTE — priority routing around incidents

## Quick Start

git clone https://github.com/Oleksandrm80/dronesync-subnet.git
cd dronesync-subnet
pip install -e .

## Run Miner

python -m miner.planner --wallet YOUR_WALLET --netuid 4 --network testnet

## Run Validator

python -m validator.scorer --wallet YOUR_WALLET --netuid 4 --network testnet

## Links
## Demo Output

$ python main.py

DroneSync MVP starting...

==================================================
SINGLE DRONE MISSION
==================================================
trajectory created
environment simulation done
score computed: 97

==================================================
SWARM MISSION - 3 DRONES
==================================================
3 trajectories planned
drone_0: status=CLEAR, collision_risks=0
drone_1: status=CLEAR, collision_risks=0
drone_2: status=CLEAR, collision_risks=0

==================================================
AI PLANNER - LEARNING MODE
==================================================
mission 1: score=97 | safety=0.4 efficiency=0.37
mission 2: score=97 | safety=0.4 efficiency=0.39
mission 3: score=97 | safety=0.4 efficiency=0.41
AI planner trained on 3 missions

==================================================
CITY MAP - ZURICH URBAN AIRSPACE
==================================================
city: zurich
no-fly zones: 3
zone types: ['hospital', 'government', 'airport']
city center: NO-FLY: government | safe_alt=140m
near airport: NO-FLY: airport | safe_alt=140m
near hospital: NO-FLY: government | safe_alt=140m

==================================================
TEE ATTESTATION - PoPW RECORD
==================================================
mission_id: DSYNC_1780031201
score: 97
trajectory_hash: 30e3e7f3e85c71e1...
attestation: ATT_000001
tee_status: VERIFIED
on_chain_ready: True
on-chain string: POPW|DSYNC_...|30e3e7f3e85c71e1|97|4a5d96d7ae6d8bea

==================================================
SECURITY SUITE - THREAT DETECTION
==================================================
overall_status: SECURE
gps_spoofing: CLEAN
hijacking: NONE
mission_cleared: True
command_verified: True

==================================================
WEATHER MODULE - ZURICH CONDITIONS
==================================================
flyable: True
severity: CLEAR
wind: 3.3 m/s
recommendation: FLY_NORMAL - conditions optimal

==================================================
ENERGY OPTIMIZER
==================================================
total_distance_km: 0.425
battery_used_pct: 7.0%
battery_remaining_pct: 93.0%
efficiency_rating: EXCELLENT
mission_feasible: True
recommendation: GO - sufficient battery for mission
optimal_speed_ms: 10.0

DroneSync pipeline completed successfully
PoPW artifact ready for on-chain submission