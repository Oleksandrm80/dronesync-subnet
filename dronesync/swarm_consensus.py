"""
DroneSync - Swarm Consensus
The swarm votes on route approval and dangerous drone exclusion.
No central operator — the swarm decides collectively.
"""
import hashlib
import time


TIER_WEIGHTS = {
    "ELITE":   2.0,
    "TRUSTED": 1.5,
    "ACTIVE":  1.0,
    "ROOKIE":  0.5,
}


class SwarmConsensus:
    """
    Decentralized decision-making for drone swarms.
    Weighted majority vote required before mission execution.
    ELITE/TRUSTED votes count more than ROOKIE votes.
    Compromised drones voted out automatically.
    """

    QUORUM = 0.51  # 51% of total weight required

    def __init__(self, drone_ids: list):
        self.drone_ids = drone_ids
        self.blacklist = []
        self.votes_log = []
        self.reputations = {}  # drone_id -> {"score": float, "tier": str}

    def update_reputation(self, drone_id: str, score: float,
                          tier: str = "ACTIVE"):
        self.reputations[drone_id] = {"score": score, "tier": tier}

    def _get_weight(self, drone_id: str) -> float:
        rep = self.reputations.get(drone_id, {})
        tier = rep.get("tier", "ACTIVE")
        return TIER_WEIGHTS.get(tier, 1.0)

    def vote_on_route(self, mission_id: str,
                      route_safe_votes: list) -> dict:
        """
        Swarm votes on whether route is safe to execute.
        route_safe_votes: list of (drone_id, True/False) tuples.
        Each vote is weighted by drone tier reputation.
        """
        active_drones = [d for d in self.drone_ids if d not in self.blacklist]
        if not active_drones:
            return {"status": "REJECTED", "reason": "no_active_drones"}

        total_weight = sum(self._get_weight(d) for d in active_drones)
        approval_weight = sum(
            self._get_weight(drone_id)
            for drone_id, vote in route_safe_votes
            if vote and drone_id in active_drones
        )
        approval_rate = approval_weight / total_weight if total_weight > 0 else 0.0

        result = {
            "mission_id": mission_id,
            "total_voters": len(active_drones),
            "total_weight": round(total_weight, 2),
            "approval_weight": round(approval_weight, 2),
            "approval_rate": round(approval_rate, 2),
            "status": "APPROVED" if approval_rate >= self.QUORUM else "REJECTED",
            "timestamp": int(time.time())
        }
        self.votes_log.append(result)
        return result

    def vote_blacklist(self, suspect_drone_id: str,
                       blacklist_votes: list) -> dict:
        """
        Swarm votes to blacklist a compromised drone.
        blacklist_votes: list of (drone_id, True/False) tuples.
        """
        active_drones = [d for d in self.drone_ids
                         if d not in self.blacklist and d != suspect_drone_id]
        if not active_drones:
            return {"status": "REJECTED", "reason": "no_active_drones"}

        total_weight = sum(self._get_weight(d) for d in active_drones)
        weight_for = sum(
            self._get_weight(drone_id)
            for drone_id, vote in blacklist_votes
            if vote and drone_id in active_drones
        )
        vote_rate = weight_for / total_weight if total_weight > 0 else 0.0

        if vote_rate >= self.QUORUM:
            if suspect_drone_id not in self.blacklist:
                self.blacklist.append(suspect_drone_id)
            status = "BLACKLISTED"
        else:
            status = "CLEARED"

        return {
            "suspect": suspect_drone_id,
            "total_voters": len(active_drones),
            "total_weight": round(total_weight, 2),
            "weight_for_blacklist": round(weight_for, 2),
            "vote_rate": round(vote_rate, 2),
            "status": status,
            "timestamp": int(time.time())
        }

    def get_swarm_status(self) -> dict:
        log_hash = hashlib.sha256(str(self.votes_log).encode()).hexdigest()
        return {
            "total_drones": len(self.drone_ids),
            "active_drones": len(self.drone_ids) - len(self.blacklist),
            "blacklisted": self.blacklist,
            "votes_cast": len(self.votes_log),
            "log_hash": log_hash,
            "on_chain_ready": True
        }
