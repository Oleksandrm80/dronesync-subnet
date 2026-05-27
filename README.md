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
🚀 DroneSync MVP starting...
✅ trajectory created
✅ environment simulation done
✅ score computed: 96
🎯 DroneSync run completed

Pipeline: mission → trajectory → simulation → scoring → PoPW artifact
Status: fully operational on local testnet environment

- Konnex Testnet: https://subnets.testnet.konnex.world
- Twitter: @OleksandrM80