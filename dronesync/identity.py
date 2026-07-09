"""
DroneSync - Node Identity
Reads real Konnex hotkey from bittensor wallet.
"""
import json
import os

HOTKEY_PATH = os.path.expanduser("~/.bittensor/wallets/miner/hotkeys/defaultpub.txt")

def get_drone_id() -> str:
    try:
        with open(HOTKEY_PATH) as f:
            data = json.load(f)
        return data["ss58Address"]
    except Exception:
        return os.environ.get("DRONE_ID", "DRONE_UNREGISTERED")

def get_public_key() -> str:
    try:
        with open(HOTKEY_PATH) as f:
            data = json.load(f)
        return data["publicKey"]
    except Exception:
        return ""

DRONE_ID = get_drone_id()
PUBLIC_KEY = get_public_key()

def get_validator_id() -> str:
    try:
        validator_path = os.environ.get("VALIDATOR_HOTKEY_PATH", HOTKEY_PATH)
        resolved = os.path.realpath(os.path.expanduser(validator_path))
        allowed_base = os.path.realpath(os.path.expanduser("~/.bittensor/"))
        if not resolved.startswith(allowed_base):
            raise ValueError(f"Path outside allowed directory: {validator_path}")
        with open(resolved) as f:
            data = json.load(f)
        return data["ss58Address"]
    except Exception:
        return os.environ.get("VALIDATOR_ID", "VALIDATOR_UNREGISTERED")

VALIDATOR_ID = get_validator_id()
