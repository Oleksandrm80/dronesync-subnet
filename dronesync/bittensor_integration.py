"""
DroneSync - Bittensor Integration
Connects DroneSync subnet to Bittensor network.
"""
import hashlib
import json
import time
import threading


class SubnetConfig:
    """DroneSync subnet configuration for Bittensor."""
    NETUID = 42  # subnet ID (placeholder until registered)
    NETWORK = "testnet"
    CHAIN_ENDPOINT = "wss://test.finney.opentensor.ai:443"
    MIN_STAKE = 1000  # TAO required to be validator
    TEMPO = 360  # blocks per epoch (~1 hour)


class MinerAxon:
    """
    Represents a DroneSync miner on Bittensor.
    Miners execute drone missions and submit PoPW proofs.
    """

    def __init__(self, wallet_address: str, hotkey: str):
        self.wallet_address = wallet_address
        self.hotkey = hotkey
        self.uid = None
        self.stake = 0.0
        self.trust = 0.0
        self.incentive = 0.0
        self._missions_completed = 0
        self._lock = threading.Lock()

    def submit_popw(self, popw: dict) -> dict:
        """Submit PoPW proof to the subnet."""
        proof_hash = hashlib.sha256(
            json.dumps(popw, sort_keys=True).encode()
        ).hexdigest()
        with self._lock:
            self._missions_completed += 1
        return {
            "status": "submitted",
            "proof_hash": proof_hash,
            "mission_id": popw.get("mission_id"),
            "miner": self.hotkey,
            "timestamp": time.time(),
        }

    def get_status(self) -> dict:
        with self._lock:
            return {
                "wallet": self.wallet_address,
                "hotkey": self.hotkey,
                "uid": self.uid,
                "stake_tao": self.stake,
                "trust": self.trust,
                "incentive": self.incentive,
                "missions_completed": self._missions_completed,
                "network": SubnetConfig.NETWORK,
                "netuid": SubnetConfig.NETUID,
            }


class ValidatorAxon:
    """
    Represents a DroneSync validator on Bittensor.
    Validators verify PoPW proofs and set weights for miners.
    """

    def __init__(self, wallet_address: str, hotkey: str):
        self.wallet_address = wallet_address
        self.hotkey = hotkey
        self.uid = None
        self.stake = 0.0
        self._weights = {}
        self._lock = threading.Lock()

    def verify_popw(self, popw: dict) -> dict:
        """Verify PoPW proof from a miner."""
        score = popw.get("score", 0)
        mission_id = popw.get("mission_id", "")
        proof_hash = popw.get("trajectory_hash", "")

        valid = (
            score >= 0.6 and
            len(mission_id) > 0 and
            len(proof_hash) > 0
        )

        return {
            "valid": valid,
            "score": score,
            "mission_id": mission_id,
            "validator": self.hotkey,
            "timestamp": time.time(),
        }

    def set_weights(self, miner_scores: dict) -> dict:
        """Set weights for miners based on their PoPW scores."""
        with self._lock:
            total = sum(miner_scores.values())
            if total == 0:
                return {"status": "no_scores"}
            self._weights = {
                uid: round(score / total, 6)
                for uid, score in miner_scores.items()
            }
        weights_hash = hashlib.sha256(
            json.dumps(self._weights, sort_keys=True).encode()
        ).hexdigest()
        return {
            "status": "weights_set",
            "miners_count": len(self._weights),
            "weights_hash": weights_hash,
            "validator": self.hotkey,
            "timestamp": time.time(),
        }

    def get_weights(self) -> dict:
        with self._lock:
            return dict(self._weights)

    def get_status(self) -> dict:
        with self._lock:
            return {
                "wallet": self.wallet_address,
                "hotkey": self.hotkey,
                "uid": self.uid,
                "stake_tao": self.stake,
                "miners_tracked": len(self._weights),
                "network": SubnetConfig.NETWORK,
                "netuid": SubnetConfig.NETUID,
            }


class SubnetMetagraph:
    """
    Simulates Bittensor metagraph — network state.
    Tracks all miners and validators in the subnet.
    """

    def __init__(self):
        self._miners = {}
        self._validators = {}
        self._lock = threading.Lock()
        self._block = 0

    def register_miner(self, miner: MinerAxon) -> int:
        with self._lock:
            uid = len(self._miners)
            miner.uid = uid
            self._miners[uid] = miner
        return uid

    def register_validator(self, validator: ValidatorAxon) -> int:
        with self._lock:
            uid = 1000 + len(self._validators)
            validator.uid = uid
            self._validators[uid] = validator
        return uid

    def update_block(self):
        with self._lock:
            self._block += 1

    def get_state(self) -> dict:
        with self._lock:
            return {
                "netuid": SubnetConfig.NETUID,
                "network": SubnetConfig.NETWORK,
                "block": self._block,
                "n_miners": len(self._miners),
                "n_validators": len(self._validators),
                "tempo": SubnetConfig.TEMPO,
                "min_stake": SubnetConfig.MIN_STAKE,
                "on_chain_ready": True,
            }
