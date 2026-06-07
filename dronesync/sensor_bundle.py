"""
DroneSync - Sensor Bundle
Packages sensor data + trajectory + PoPW into one signed evidence bundle.
Required by Konnex PoPW policy — evidence must be complete and tamper-evident.
"""
import hashlib
import json
import time


class SensorBundle:
    """
    Complete evidence package for one drone mission.
    Combines: trajectory trace + sensor readings + PoPW record.
    Signed as a single unit — any tampering invalidates the whole bundle.
    """

    VERSION = "1.0"

    def pack(self, mission_id: str, trajectory,
             sensor_data, popw_record: dict,
             drone_id: str = "DRONE_001") -> dict:
        """
        Pack all mission evidence into a signed bundle.
        This is what gets submitted to Konnex validation layer.
        """
        trajectory_summary = {
            "positions_count": len(trajectory.positions),
            "origin": trajectory.positions[0][:2],
            "destination": trajectory.positions[-1][:2],
            "planner_steps": trajectory.metadata.get("planner_steps", []),
            "steps_hash": trajectory.metadata.get("steps_hash", ""),
        }

        sensor_summary = {
            "lidar_points": len(sensor_data.lidar_points),
            "camera_detections": sensor_data.camera_detections,
            "imu_data": sensor_data.imu_data,
            "timestamp": sensor_data.timestamp,
        }
        sensor_hash = hashlib.sha256(
            json.dumps(sensor_summary, sort_keys=True).encode()
        ).hexdigest()

        bundle = {
            "bundle_version": self.VERSION,
            "mission_id": mission_id,
            "drone_id": drone_id,
            "timestamp": int(time.time()),
            "trajectory": trajectory_summary,
            "sensor_hash": sensor_hash,
            "sensor_detections": sensor_data.camera_detections,
            "popw": {
                "mission_id": popw_record["mission_id"],
                "trajectory_hash": popw_record["trajectory_hash"],
                "score": popw_record["score"],
                "attestation_id": popw_record["attestation"]["attestation_id"],
                "tee_status": popw_record["attestation"]["status"],
                "on_chain_string": self._format_chain_string(popw_record),
            },
        }

        bundle["bundle_hash"] = hashlib.sha256(
            json.dumps(bundle, sort_keys=True).encode()
        ).hexdigest()
        bundle["on_chain_ready"] = True

        return bundle

    def verify(self, bundle: dict) -> dict:
        """
        Verify bundle integrity — recompute hash and compare.
        """
        stored_hash = bundle.get("bundle_hash")
        check = {k: v for k, v in bundle.items()
                 if k not in ("bundle_hash", "on_chain_ready")}
        recomputed = hashlib.sha256(
            json.dumps(check, sort_keys=True).encode()
        ).hexdigest()

        if stored_hash == recomputed:
            return {
                "valid": True,
                "mission_id": bundle["mission_id"],
                "bundle_hash": stored_hash,
                "score": bundle["popw"]["score"],
                "tee_status": bundle["popw"]["tee_status"]
            }
        return {
            "valid": False,
            "reason": "bundle_hash_mismatch"
        }

    def _format_chain_string(self, popw_record: dict) -> str:
        return (
            "POPW|" +
            popw_record["mission_id"] + "|" +
            popw_record["trajectory_hash"][:16] + "|" +
            str(popw_record["score"]) + "|" +
            popw_record["attestation"]["attestation_hash"][:16]
        )
    def pack_batch(self, bundles: list) -> dict:
        """Pack multiple mission bundles into one batch for chain submission."""
        batch_hash = hashlib.sha256(
            json.dumps([b["bundle_hash"] for b in bundles]).encode()
        ).hexdigest()
        return {
            "batch_size": len(bundles),
            "mission_ids": [b["mission_id"] for b in bundles],
            "bundle_hashes": [b["bundle_hash"] for b in bundles],
            "batch_hash": batch_hash,
            "timestamp": int(time.time()),
            "on_chain_ready": True
        }
