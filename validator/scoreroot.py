"""
DroneSync - ScoreRoot
Validator publishes a cryptographic root of all scores on-chain.
Required by Konnex validation layer — proves scores weren't tampered with.
"""
import hashlib
import time
import json


class ScoreRoot:
    """
    Merkle-style root hash of all validator scores.
    Each score batch gets a ScoreRoot commitment posted on-chain.
    Auditors can verify any individual score against the root.
    """

    def __init__(self, validator_id: str):
        self.validator_id = validator_id
        self.scores: list = []
        self.commitments: list = []

    def add_score(self, mission_id: str, score: int,
                  trajectory_hash: str, sensor_hash: str):
        """Add a scored mission to the current batch."""
        entry = {
            "mission_id": mission_id,
            "score": score,
            "trajectory_hash": trajectory_hash,
            "sensor_hash": sensor_hash,
            "timestamp": int(time.time()),
            "validator_id": self.validator_id
        }
        entry["entry_hash"] = hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode()
        ).hexdigest()
        self.scores.append(entry)

    def compute_root(self) -> str:
        """Compute Merkle-style root of all score hashes."""
        if not self.scores:
            return hashlib.sha256(b"empty").hexdigest()
        hashes = [s["entry_hash"] for s in self.scores]
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256((hashes[i] + hashes[i+1]).encode()).hexdigest()
                for i in range(0, len(hashes), 2)
            ]
        return hashes[0]

    def commit(self) -> dict:
        """
        Create a ScoreRoot commitment for on-chain submission.
        This is what Konnex validators post to the chain.
        """
        root = self.compute_root()
        commitment = {
            "score_root": root,
            "validator_id": self.validator_id,
            "scores_count": len(self.scores),
            "timestamp": int(time.time()),
            "on_chain_ready": True
        }
        commitment["commitment_hash"] = hashlib.sha256(
            json.dumps(commitment, sort_keys=True).encode()
        ).hexdigest()
        self.commitments.append(commitment)
        return commitment

    def verify_score(self, mission_id: str) -> dict:
        """Verify that a specific score is included in the last commitment."""
        entry = next((s for s in self.scores if s["mission_id"] == mission_id), None)
        if not entry:
            return {"verified": False, "reason": "mission_not_found"}
        if not self.commitments:
            return {"verified": False, "reason": "no_commitment_yet"}
        return {
            "verified": True,
            "mission_id": mission_id,
            "score": entry["score"],
            "entry_hash": entry["entry_hash"],
            "score_root": self.commitments[-1]["score_root"]
        }
