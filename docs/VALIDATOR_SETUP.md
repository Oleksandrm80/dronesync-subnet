# DroneSync — Validator Node Setup

A validator verifies PoPW proofs from miners and sets weights on Konnex chain.

## Requirements

- Python 3.10+
- Konnex wallet with sufficient KNX stake
- Server with stable internet connection

## 1. Clone and install

    git clone https://github.com/oleksandrm80/dronesync-subnet.git
    cd dronesync-subnet
    pip install -r requirements.txt

## 2. Create validator wallet

    pip install bittensor
    btcli wallet new_coldkey --wallet.name validator
    btcli wallet new_hotkey --wallet.name validator --wallet.hotkey default

## 3. Run validator

    python3 -c "
    from dronesync.konnex_integration import ValidatorNode, SubnetConfig
    from dronesync.identity import VALIDATOR_ID
    v = ValidatorNode(wallet_address='your_wallet', hotkey=VALIDATOR_ID)
    print('Validator running on NETUID', SubnetConfig.NETUID)
    print('Validator ID:', VALIDATOR_ID)
    "

## 4. Run with Docker

    docker compose up -d validator

## 5. How scoring works

Validators receive PoPW proofs from miners and score them:

- Score >= 85 → EXCELLENT
- Score >= 70 → GOOD  
- Score >= 50 → ACCEPTABLE
- Score < 50  → POOR (not submitted on-chain)

Weights are set proportionally to scores. Miners with higher scores
earn more KNX tokens per epoch.

## 6. Verify a PoPW proof manually

    python3 verify_popw.py --mission-id DSYNC_xxxxx
