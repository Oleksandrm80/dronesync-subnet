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
    def generate_recovery_plan(self, last_position: list, 
                                battery_pct: float) -> dict:
        """Generate recovery instructions for ground crew."""
        if battery_pct < 5.0:
            action = "IMMEDIATE_RETRIEVAL"
        elif battery_pct < 15.0:
            action = "PRIORITY_RETRIEVAL"
        else:
            action = "SCHEDULED_RETRIEVAL"

        return {
            "drone_id": self.drone_id,
            "recovery_action": action,
            "location": {
                "lat": last_position[0],
                "lon": last_position[1],
                "alt": last_position[2]
            },
            "battery_pct": battery_pct,
            "timestamp": int(time.time()),
            "estimated_retrieval_window_hours": 1 if battery_pct < 5.0 else 4
        }

    def full_diagnostics(self, last_position: list, failure_cause: str,
                          battery_pct: float, mission_id: str,
                          sensor_data: dict = None) -> dict:
        """Full diagnostics report combining last will and recovery plan."""
        will = self.trigger(last_position, failure_cause, 
                           battery_pct, mission_id)
        recovery = self.generate_recovery_plan(last_position, battery_pct)
        return {
            "last_will": will,
            "recovery_plan": recovery,
            "sensor_snapshot": sensor_data or {},
            "diagnostic_hash": hashlib.sha256(
                str(will).encode()
            ).hexdigest()[:16]
        }
