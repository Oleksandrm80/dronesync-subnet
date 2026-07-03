# DroneSync — Miner Node Setup

A miner is a drone operator who connects to DroneSync subnet on Konnex NETUID 4.

## Requirements

- Python 3.10+
- Node.js 18+
- Bittensor wallet (for Konnex hotkey identity)
- Optional: real drone with MAVLink support

## 1. Clone and install

    git clone https://github.com/oleksandrm80/dronesync-subnet.git
    cd dronesync-subnet
    pip install -r requirements.txt

## 2. Create Konnex wallet

    pip install bittensor
    btcli wallet new_coldkey --wallet.name miner
    btcli wallet new_hotkey --wallet.name miner --wallet.hotkey default

Your hotkey address becomes your DRONE_ID on the network.

## 3. Configure environment

    cp .env.example .env
    # Add your OpenWeatherMap API key to .env

## 4. Run miner

    # Simulation mode (no drone)
    python3 main.py

    # With real drone via USB
    python3 demo_mavlink.py /dev/ttyUSB0

    # With real drone via WiFi
    python3 demo_mavlink.py udp:192.168.1.10:14550

    # Emulator mode
    python3 demo_mavlink.py --emulator

## 5. Run with Docker

    docker compose up -d miner

## 6. Verify PoPW

    python3 verify_popw.py

## Transaction Queue

PoPW proofs are automatically queued for on-chain submission.
Check queue status:

    python3 -c "from dronesync.tx_queue import TxQueue; print(TxQueue().get_stats())"
