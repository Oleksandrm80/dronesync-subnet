"""
DroneSync - Swarm Consensus
The swarm votes on route approval and dangerous drone exclusion.
No central operator — the swarm decides collectively.
"""
import hashlib
import time


class SwarmConsensus:
    """
    Decentralized decision-making for drone swarms.
    Majority vote required before mission execution.
    Compromised drones voted out automatically.
    """

    QUORUM = 0.51  # 51% majority required

    def __init__(self, drone_ids: list):
        self.drone_ids = drone_ids
        self.blacklist = []
        self.votes_log = []

    def vote_on_route(self, mission_id: str,
                      route_safe_votes: list) -> dict:
        """
        Swarm votes on whether route is safe to execute.
        route_safe_votes: list of (drone_id, True/False) tuples.
        """
        active_drones = [d for d in self.drone_ids if d not in self.blacklist]
        total = len(active_drones)
        if total == 0:
            return {"status": "REJECTED", "reason": "no_active_drones"}

        approvals = sum(1 for _, vote in route_safe_votes if vote)
        approval_rate = approvals / total

        result = {
            "mission_id": mission_id,
            "total_voters": total,
            "approvals": approvals,
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
        total = len(active_drones)
        if total == 0:
            return {"status": "REJECTED", "reason": "no_active_drones"}

        votes_for = sum(1 for _, vote in blacklist_votes if vote)
        vote_rate = votes_for / total

        if vote_rate >= self.QUORUM:
            if suspect_drone_id not in self.blacklist:
                self.blacklist.append(suspect_drone_id)
            status = "BLACKLISTED"
        else:
            status = "CLEARED"

        return {
            "suspect": suspect_drone_id,
            "total_voters": total,
            "votes_for_blacklist": votes_for,
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
