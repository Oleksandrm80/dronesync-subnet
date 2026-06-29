"""
DroneSync - Swarm Consensus
Weighted voting by reputation tier.
ELITE=4, TRUSTED=3, ACTIVE=2, ROOKIE=1
"""
import hashlib
import time

TIER_WEIGHTS = {
    "ELITE":   4,
    "TRUSTED": 3,
    "ACTIVE":  2,
    "ROOKIE":  1,
}

QUORUM = 0.67


class SwarmConsensus:
    def __init__(self, drone_ids: list):
        self.drone_ids = drone_ids
        self.blacklist: list = []
        self.votes_log: list = []
        self._reputation: dict = {}

    def register_drone_reputation(self, drone_id: str, tier: str):
        if tier not in TIER_WEIGHTS:
            tier = "ROOKIE"
        self._reputation[drone_id] = tier

    def _weight(self, drone_id: str) -> int:
        return TIER_WEIGHTS.get(self._reputation.get(drone_id, "ROOKIE"), 1)

    def _total_weight(self, drone_list: list) -> int:
        return sum(self._weight(d) for d in drone_list)

    def vote_on_route(self, mission_id: str, route_safe_votes: list) -> dict:
        active_drones = [d for d in self.drone_ids if d not in self.blacklist]
        total_weight = self._total_weight(active_drones)

        if total_weight == 0:
            return {"status": "REJECTED", "reason": "no_active_drones"}

        approval_weight = sum(
            self._weight(drone_id)
            for drone_id, vote in route_safe_votes
            if vote and drone_id not in self.blacklist
        )
        approval_rate = approval_weight / total_weight

        tier_breakdown = {}
        for drone_id, vote in route_safe_votes:
            if drone_id in self.blacklist:
                continue
            tier = self._reputation.get(drone_id, "ROOKIE")
            if tier not in tier_breakdown:
                tier_breakdown[tier] = {"approve": 0, "reject": 0}
            if vote:
                tier_breakdown[tier]["approve"] += 1
            else:
                tier_breakdown[tier]["reject"] += 1

        result = {
            "mission_id": mission_id,
            "total_voters": len(active_drones),
            "total_weight": total_weight,
            "approval_weight": approval_weight,
            "approval_rate": round(approval_rate, 3),
            "status": "APPROVED" if approval_rate >= QUORUM else "REJECTED",
            "tier_breakdown": tier_breakdown,
            "timestamp": int(time.time())
        }
        self.votes_log.append(result)
        return result

    def vote_blacklist(self, suspect_drone_id: str, blacklist_votes: list) -> dict:
        active_drones = [
            d for d in self.drone_ids
            if d not in self.blacklist and d != suspect_drone_id
        ]
        total_weight = self._total_weight(active_drones)

        if total_weight == 0:
            return {"status": "REJECTED", "reason": "no_active_drones"}

        votes_weight = sum(
            self._weight(drone_id)
            for drone_id, vote in blacklist_votes
            if vote and drone_id not in self.blacklist
        )
        vote_rate = votes_weight / total_weight

        if vote_rate >= QUORUM:
            if suspect_drone_id not in self.blacklist:
                self.blacklist.append(suspect_drone_id)
            status = "BLACKLISTED"
        else:
            status = "CLEARED"

        result = {
            "suspect": suspect_drone_id,
            "suspect_tier": self._reputation.get(suspect_drone_id, "ROOKIE"),
            "total_voters": len(active_drones),
            "total_weight": total_weight,
            "votes_weight_for_blacklist": votes_weight,
            "vote_rate": round(vote_rate, 3),
            "status": status,
            "timestamp": int(time.time())
        }
        self.votes_log.append(result)
        return result

    def get_swarm_status(self) -> dict:
        active_drones = [d for d in self.drone_ids if d not in self.blacklist]
        tier_distribution: dict = {}
        for drone_id in active_drones:
            tier = self._reputation.get(drone_id, "ROOKIE")
            tier_distribution[tier] = tier_distribution.get(tier, 0) + 1
        log_hash = hashlib.sha256(str(self.votes_log).encode()).hexdigest()
        return {
            "total_drones": len(self.drone_ids),
            "active_drones": len(active_drones),
            "total_voting_weight": self._total_weight(active_drones),
            "blacklisted": self.blacklist,
            "tier_distribution": tier_distribution,
            "votes_cast": len(self.votes_log),
            "log_hash": log_hash,
            "on_chain_ready": True
        }


class ByzantineDetector:
    """
    Detects Byzantine behavior in drone swarm.
    Flags drones that consistently vote against the majority.
    Protects against coordinated attacks on consensus.
    """

    SUSPICION_THRESHOLD = 3   # votes against majority before flagged
    BYZANTINE_THRESHOLD = 5   # votes against majority before blacklisted

    def __init__(self, consensus: "SwarmConsensus"):
        self.consensus = consensus
        self._against_majority: dict = {}  # drone_id -> count

    def analyze(self, vote_result: dict, votes: list) -> dict:
        """
        Analyze voting round for Byzantine behavior.
        Flags drones that voted against the majority outcome.
        """
        majority_approve = vote_result["status"] == "APPROVED"
        flagged = []
        blacklisted = []

        for drone_id, vote in votes:
            if drone_id in self.consensus.blacklist:
                continue
            voted_against = (majority_approve and not vote) or \
                           (not majority_approve and vote)
            if voted_against:
                self._against_majority[drone_id] = \
                    self._against_majority.get(drone_id, 0) + 1
                count = self._against_majority[drone_id]

                if count >= self.BYZANTINE_THRESHOLD:
                    if drone_id not in self.consensus.blacklist:
                        self.consensus.blacklist.append(drone_id)
                    blacklisted.append(drone_id)
                elif count >= self.SUSPICION_THRESHOLD:
                    flagged.append(drone_id)

        return {
            "byzantine_flagged": flagged,
            "byzantine_blacklisted": blacklisted,
            "suspicion_counts": dict(self._against_majority),
            "swarm_safe": len(blacklisted) == 0
        }

    def get_status(self) -> dict:
        import hashlib
        return {
            "monitored_drones": len(self._against_majority),
            "suspicious_drones": [
                d for d, c in self._against_majority.items()
                if c >= self.SUSPICION_THRESHOLD
            ],
            "blacklisted": self.consensus.blacklist,
            "status_hash": hashlib.sha256(
                str(self._against_majority).encode()
            ).hexdigest()
        }


class ORCACollisionAvoider:
    """
    ORCA (Optimal Reciprocal Collision Avoidance) for drone swarms.
    Each drone independently computes a velocity that avoids collisions.
    """

    SAFE_DISTANCE = 10.0   # meters minimum between drones
    TIME_HORIZON  = 5.0    # seconds to look ahead

    def __init__(self, safe_distance: float = 10.0, time_horizon: float = 5.0):
        self.safe_distance = safe_distance
        self.time_horizon  = time_horizon

    def compute_avoidance(self, drone_id: str, positions: dict, velocities: dict) -> dict:
        """
        Compute safe velocity for drone_id given all drone positions and velocities.
        positions:  {drone_id: (x, y, z)}
        velocities: {drone_id: (vx, vy, vz)}
        Returns:    {drone_id: new_velocity, "collisions_avoided": [...], "safe": bool}
        """
        if drone_id not in positions or drone_id not in velocities:
            return {"drone_id": drone_id, "safe": True, "collisions_avoided": []}

        px, py, pz   = positions[drone_id]
        vx, vy, vz   = velocities[drone_id]
        avoided      = []
        new_vx, new_vy, new_vz = vx, vy, vz

        for other_id, (ox, oy, oz) in positions.items():
            if other_id == drone_id:
                continue
            dx = ox - px
            dy = oy - py
            dz = oz - pz
            dist = (dx**2 + dy**2 + dz**2) ** 0.5

            if dist < self.safe_distance:
                # Push velocity away from the other drone
                if dist > 0:
                    scale = (self.safe_distance - dist) / dist
                    new_vx -= dx * scale * 0.5
                    new_vy -= dy * scale * 0.5
                    new_vz -= dz * scale * 0.3
                avoided.append({
                    "other_drone": other_id,
                    "distance_m": round(dist, 2),
                    "action": "velocity_adjusted"
                })

        return {
            "drone_id":           drone_id,
            "original_velocity":  (vx, vy, vz),
            "safe_velocity":      (round(new_vx,3), round(new_vy,3), round(new_vz,3)),
            "collisions_avoided": avoided,
            "safe":               len(avoided) == 0,
            "timestamp":          int(time.time())
        }

    def check_swarm(self, positions: dict, velocities: dict) -> dict:
        """Check entire swarm for potential collisions."""
        results = {}
        total_avoided = 0
        for drone_id in positions:
            r = self.compute_avoidance(drone_id, positions, velocities)
            results[drone_id] = r
            total_avoided += len(r["collisions_avoided"])
        return {
            "swarm_safe":      total_avoided == 0,
            "total_avoided":   total_avoided,
            "drone_results":   results,
            "timestamp":       int(time.time())
        }
