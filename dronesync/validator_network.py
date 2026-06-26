"""
dronesync/validator_network.py

Coordinator for decentralized validator network.
Submits PoPW to all validator nodes and collects consensus.
"""

import asyncio
import json
import logging
import time
from typing import List, Dict, Optional

import websockets

logger = logging.getLogger(__name__)


class NetworkResult:

    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self.votes: List[dict] = []
        self.consensus: bool = False
        self.quorum: float = 0.0
        self.avg_score: float = 0.0
        self.duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "consensus": self.consensus,
            "quorum": self.quorum,
            "avg_score": self.avg_score,
            "votes_total": len(self.votes),
            "votes_accepted": sum(1 for v in self.votes if v.get("accepted")),
            "duration_ms": round(self.duration_ms, 2),
        }


class ValidatorNetwork:
    """
    Submits PoPW to all validator nodes in the network,
    collects their votes, and computes final consensus.

    node_uris: list of WebSocket URIs
        e.g. ["ws://localhost:9001", "ws://localhost:9002", "ws://localhost:9003"]
    """

    def __init__(self, node_uris: List[str], timeout: float = 5.0):
        self.node_uris = node_uris
        self.timeout = timeout

    async def _submit_to_node(self, uri: str, popw: dict) -> Optional[dict]:
        try:
            async with websockets.connect(uri, open_timeout=self.timeout) as ws:
                await ws.send(json.dumps({
                    "type": "submit_popw",
                    "popw": popw,
                }))
                raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                msg = json.loads(raw)
                if msg.get("type") == "vote_ack":
                    return msg.get("vote")
        except asyncio.TimeoutError:
            logger.warning("Timeout from validator %s — node may be down", uri)
        except websockets.exceptions.ConnectionRefusedError:
            logger.warning("Node down: %s — skipping", uri)
        except websockets.exceptions.WebSocketException as e:
            logger.warning("WebSocket error from %s: %s", uri, e)
        except Exception as e:
            logger.warning("Error from validator %s: %s", uri, e)
        return None

    async def _get_result_from_node(self, uri: str, mission_id: str) -> Optional[dict]:
        try:
            async with websockets.connect(uri, open_timeout=self.timeout) as ws:
                await ws.send(json.dumps({
                    "type": "get_result",
                    "mission_id": mission_id,
                }))
                raw = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                msg = json.loads(raw)
                if msg.get("type") == "result":
                    return msg.get("result")
        except Exception as e:
            logger.warning("Could not get result from %s: %s", uri, e)
        return None

    async def submit_popw(self, popw: dict) -> NetworkResult:
        mission_id = popw.get("mission_id", "unknown")
        result = NetworkResult(mission_id)
        start = time.time()

        tasks = [self._submit_to_node(uri, popw) for uri in self.node_uris]
        responses = await asyncio.gather(*tasks)

        for vote in responses:
            if vote:
                result.votes.append(vote)

        reachable = sum(1 for v in responses if v is not None)
        logger.info("Validator network: %d/%d nodes responded", reachable, len(self.node_uris))
        total = len(result.votes)
        if total == 0:
            result.consensus = False
            result.quorum = 0.0
            result.avg_score = 0.0
        else:
            accepted = sum(1 for v in result.votes if v.get("accepted"))
            result.quorum = accepted / total
            result.avg_score = sum(v.get("score", 0) for v in result.votes) / total
            result.consensus = result.quorum >= 0.67

        result.duration_ms = (time.time() - start) * 1000
        return result

    def submit_popw_sync(self, popw: dict) -> NetworkResult:
        return asyncio.run(self.submit_popw(popw))

    async def get_network_status(self) -> Dict[str, bool]:
        status = {}
        for uri in self.node_uris:
            try:
                async with websockets.connect(uri, open_timeout=2.0):
                    status[uri] = True
            except Exception:
                status[uri] = False
        return status
