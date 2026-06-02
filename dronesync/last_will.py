"""
DroneSync - Drone Last Will
On critical failure, drone sends final PoPW with coordinates and diagnostics.
Automatic — no human required.
"""
import hashlib
import time


class DroneLastWill:
    """
    Emergency PoPW record triggered on drone failure.
    Captures last known position, failure cause, and full diagnostics.
    Submitted to chain automatically before shutdown.
    """

    def __init__(self, drone_id: str):
        self.drone_id = drone_id

    def trigger(self, last_position: list, failure_cause: str,
                battery_pct: float, mission_id: str) -> dict:
        """
        Generate Last Will PoPW on critical failure.
        Called automatically when drone detects fatal condition.
        """
        timestamp = int(time.time())

        payload = {
            "drone_id": self.drone_id,
            "mission_id": mission_id,
            "last_position": {
                "lat": last_position[0],
                "lon": last_position[1],
                "alt": last_position[2]
            },
            "failure_cause": failure_cause,
            "battery_pct": battery_pct,
            "timestamp": timestamp
        }

        will_hash = hashlib.sha256(str(payload).encode()).hexdigest()

        return {
            "type": "LAST_WILL",
            "drone_id": self.drone_id,
            "mission_id": mission_id,
            "last_position": payload["last_position"],
            "failure_cause": failure_cause,
            "battery_pct": battery_pct,
            "timestamp": timestamp,
            "will_hash": will_hash,
            "on_chain_ready": True,
            "insurance_claim_ready": True
        }

    def simulate_crash(self, trajectory_positions: list,
                       mission_id: str) -> dict:
        """Simulate crash at last known position for testing."""
        last = trajectory_positions[-1]
        return self.trigger(
            last_position=last[:3],
            failure_cause="CRITICAL_BATTERY_FAILURE",
            battery_pct=2.1,
            mission_id=mission_id
        )
