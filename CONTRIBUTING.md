# Contributing to DroneSync

## Welcome

DroneSync is an open subnet built on Konnex for urban drone coordination.
We welcome contributions from developers, researchers, and drone enthusiasts.

## How to Contribute

### 1. Fork and Clone
git clone https://github.com/Oleksandrm80/dronesync-subnet.git
cd dronesync-subnet
pip install -r requirements.txt

### 2. Areas We Need Help

| Area | Skills Needed | Priority |
|------|--------------|----------|
| Konnex SDK integration | Python, Blockchain | High |
| Isaac Sim integration | Python, Robotics | High |
| WebSocket API | Python, FastAPI | Medium |
| Web dashboard | React, JavaScript | Medium |
| Real GPS data | Python, OpenStreetMap | Medium |
| Hardware support | Python, DJI SDK | Low |

### 3. Code Standards
- Python 3.10+
- All modules must have docstrings
- All new features must be tested in main.py
- Follow existing code structure

### 4. Subnet Architecture
Miners implement: plan_trajectory()
Validators implement: score()
PoPW artifacts must include: instruction_hash, trajectory_root, score

### 5. Contact
Twitter: @OleksandrM80
Konnex Discord: subnets.testnet.konnex.world