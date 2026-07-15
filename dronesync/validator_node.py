"""
dronesync/validator_node.py

Decentralized validator node.
Each node runs a WebSocket server, receives PoPW from drones,
validates independently, and broadcasts its vote to peers.
"""

import asyncio
import json
import logging
import time
import hashlib
from typing import Dict, List

import websockets

from dronesync.reputation import DroneReputation

logger = logging.getLogger(__name__)


class ValidatorVote:

    def __init__(self, validator_id: str, mission_id: str,
                 accepted: bool, score: float, reason: str = ""):
        self.validator_id = validator_id
        self.mission_id = mission_id
        self.accepted = accepted
        self.score = score
        self.reason = reason
        self.timestamp = time.time()
        self.signature = self._sign()

    def _sign(self) -> str:
        data = f"{self.validator_id}:{self.mission_id}:{self.accepted}:{self.score:.4f}:{self.timestamp:.3f}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "validator_id": self.validator_id,
            "mission_id": self.mission_id,
            "accepted": self.accepted,
            "score": self.score,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }


class ValidatorNode:
    """
    Single validator node in the decentralized network.
    Runs WebSocket server on given port.
    Connects to peer validators to broadcast votes.
    """

    def __init__(self, node_id: str, host: str = "localhost", port: int = 9001,
                 peers: List[str] = None, min_score: float = 60.0):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers = peers or []
        self.min_score = min_score
        self._votes: Dict[str, List[ValidatorVote]] = {}
        self._results: Dict[str, dict] = {}
        self._reputation = DroneReputation(drone_id=node_id)
        self._seen_missions: set = set()

    def _validate_popw(self, popw: dict) -> ValidatorVote:
        mission_id = popw.get("mission_id", "unknown")
        score = float(popw.get("score", 0))
        computation_hash = popw.get("computation_hash", "")
        constraints_ok = popw.get("constraints_satisfied", False)

        if not computation_hash:
            return ValidatorVote(self.node_id, mission_id, False, score, "missing_hash")

        if not constraints_ok:
            return ValidatorVote(self.node_id, mission_id, False, score, "constraints_failed")

        if score < self.min_score:
            return ValidatorVote(self.node_id, mission_id, False, score, f"score_too_low:{score:.1f}")

        positions = popw.get("trajectory_positions", [])
        if len(positions) < 2:
            return ValidatorVote(self.node_id, mission_id, False, score, "trajectory_too_short")

        return ValidatorVote(self.node_id, mission_id, True, score, "accepted")

    async def _broadcast_vote(self, vote: ValidatorVote):
        for peer_uri in self.peers:
            try:
                async with websockets.connect(peer_uri, open_timeout=3) as ws:
                    await ws.send(json.dumps({
                        "type": "vote",
                        "vote": vote.to_dict(),
                    }))
                    logger.debug("Vote sent to %s", peer_uri)
            except Exception as e:
                logger.warning("Could not reach peer %s: %s", peer_uri, e)

    async def _handle_client(self, websocket):
        try:
            async for raw in websocket:
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "submit_popw":
                    popw = msg.get("popw", {})
                    mission_id = popw.get("mission_id", "unknown")
                    logger.info("[%s] Received PoPW for mission %s", self.node_id, mission_id)
                    if mission_id in self._seen_missions:
                        await websocket.send(json.dumps({
                            "type": "vote_ack",
                            "vote": {"accepted": False, "reason": "duplicate_mission", "mission_id": mission_id},
                        }))
                        continue
                    self._seen_missions.add(mission_id)

                    vote = self._validate_popw(popw)
                    logger.info("[%s] Vote: accepted=%s score=%.1f reason=%s",
                                self.node_id, vote.accepted, vote.score, vote.reason)

                    if mission_id not in self._votes:
                        self._votes[mission_id] = []
                    self._votes[mission_id].append(vote)

                    await websocket.send(json.dumps({
                        "type": "vote_ack",
                        "vote": vote.to_dict(),
                    }))

                    await self._broadcast_vote(vote)

                elif msg_type == "vote":
                    vote_data = msg.get("vote", {})
                    mission_id = vote_data.get("mission_id", "unknown")
                    vote = ValidatorVote(
                        validator_id=vote_data["validator_id"],
                        mission_id=mission_id,
                        accepted=vote_data["accepted"],
                        score=vote_data["score"],
                        reason=vote_data.get("reason", ""),
                    )
                    if mission_id not in self._votes:
                        self._votes[mission_id] = []
                    self._votes[mission_id].append(vote)
                    logger.info("[%s] Received peer vote from %s: accepted=%s",
                                self.node_id, vote_data["validator_id"], vote.accepted)

                elif msg_type == "get_result":
                    mission_id = msg.get("mission_id", "")
                    result = self._compute_result(mission_id)
                    await websocket.send(json.dumps({
                        "type": "result",
                        "result": result,
                    }))

        except websockets.exceptions.ConnectionClosedOK:
            pass
        except Exception as e:
            logger.error("[%s] Handler error: %s", self.node_id, e)

    def _compute_result(self, mission_id: str) -> dict:
        votes = self._votes.get(mission_id, [])
        if not votes:
            return {"mission_id": mission_id, "consensus": False, "reason": "no_votes"}

        total = len(votes)
        accepted = sum(1 for v in votes if v.accepted)
        avg_score = sum(v.score for v in votes) / total
        quorum = accepted / total

        consensus = quorum >= 0.67

        return {
            "mission_id": mission_id,
            "consensus": consensus,
            "quorum": round(quorum, 3),
            "votes_total": total,
            "votes_accepted": accepted,
            "avg_score": round(avg_score, 2),
            "reason": "quorum_reached" if consensus else "quorum_failed",
        }

    async def start(self):
        logger.info("[%s] Starting validator on ws://%s:%d", self.node_id, self.host, self.port)
        async with websockets.serve(self._handle_client, self.host, self.port):
            await asyncio.Future()

    def get_result(self, mission_id: str) -> dict:
        return self._compute_result(mission_id)
