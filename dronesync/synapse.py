# dronesync/synapse.py
"""
DroneSync ↔ Konnex DroneNavSynapse adapter.

DroneNavSynapse — протокол валидатора Konnex (NETUID 4).
Принимает задание от валидатора, запускает полный DroneSync
pipeline (planner → env → pipeline → PoPW) и возвращает
готовый артефакт для on-chain scoring.
"""

import time
import hashlib
import json
import hmac as _hmac
from typing import Dict

from miner.planner import DronePlanner, AIPlanner
from environment.sim import DroneEnvironment
from validator.scorer import DroneEvaluator
from dronesync.protocol import MissionInstruction, Waypoint as WP, MissionType
from dronesync.pipeline import MissionPipeline
from dronesync.reputation import DroneReputation
from dronesync.security import DroneSecuritySuite
from dronesync.firewall import DroneFirewall
from dronesync.memory import DroneMemory
from dronesync.storage import DroneStorage
from dronesync.swarm_consensus import SwarmConsensus
from miner.weather import WeatherService
from dronesync.identity import DRONE_ID
from dronesync.tx_queue import TxQueue


class MissionAdapter:
    """Конвертирует DroneNavSynapse task → MissionInstruction."""

    def from_synapse_task(self, task: Dict) -> MissionInstruction:
        if not isinstance(task, dict):
            task = {}
        origin_raw = task.get("origin", {})
        dest_raw = task.get("destination", {})
        if not isinstance(origin_raw, dict):
            origin_raw = {}
        if not isinstance(dest_raw, dict):
            dest_raw = {}

        def _clamp_lat(v):
            try:
                return max(-90.0, min(90.0, float(v)))
            except (TypeError, ValueError):
                raise ValueError(f"Invalid latitude: {v!r}")

        def _clamp_lon(v):
            try:
                return max(-180.0, min(180.0, float(v)))
            except (TypeError, ValueError):
                raise ValueError(f"Invalid longitude: {v!r}")

        def _clamp_alt(v):
            try:
                return max(0.0, min(500.0, float(v)))
            except (TypeError, ValueError):
                return 50.0

        if "lat" not in origin_raw or "lon" not in origin_raw:
            raise ValueError("origin must include 'lat' and 'lon'")
        if "lat" not in dest_raw or "lon" not in dest_raw:
            raise ValueError("destination must include 'lat' and 'lon'")

        origin = WP(
            lat=_clamp_lat(origin_raw["lat"]),
            lon=_clamp_lon(origin_raw["lon"]),
            alt=_clamp_alt(origin_raw.get("alt", 50)),
            speed=_clamp_alt(origin_raw.get("speed", 5)),
        )
        destination = WP(
            lat=_clamp_lat(dest_raw["lat"]),
            lon=_clamp_lon(dest_raw["lon"]),
            alt=_clamp_alt(dest_raw.get("alt", 50)),
            speed=_clamp_alt(dest_raw.get("speed", 5)),
        )
        waypoints = []
        for wp in task.get("waypoints", []):
            if not isinstance(wp, dict):
                continue
            if "lat" not in wp or "lon" not in wp:
                continue
            waypoints.append(WP(
                lat=_clamp_lat(wp["lat"]),
                lon=_clamp_lon(wp["lon"]),
                alt=_clamp_alt(wp.get("alt", 50)),
                speed=_clamp_alt(wp.get("speed", 5)),
            ))

        try:
            mission_type = MissionType(task.get("mission_type", "urban_delivery"))
        except ValueError:
            mission_type = MissionType.URBAN_DELIVERY

        return MissionInstruction(
            mission_id=task.get("task_id", "DSYNC_" + str(int(time.time()))),
            mission_type=mission_type,
            origin=origin,
            destination=destination,
            waypoints=waypoints,
            drone_count=task.get("drone_count", 1),
            payload_kg=task.get("payload_kg", 0.5),
        )


class DroneNavSynapseHandler:
    """
    Основной обработчик задания от валидатора Konnex.

    Использование:
        handler = DroneNavSynapseHandler(drone_id=DRONE_ID)
        response = handler.handle(synapse_task)
        # response содержит полный PoPW артефакт для on-chain scoring
    """

    def __init__(self, drone_id: str = DRONE_ID, use_ai_planner: bool = False):
        self.drone_id = drone_id
        self.adapter = MissionAdapter()
        self.planner = AIPlanner() if use_ai_planner else DronePlanner()
        self.env = DroneEnvironment()
        self.evaluator = DroneEvaluator()
        self.security = DroneSecuritySuite()
        self.firewall = DroneFirewall(drone_id=drone_id)
        self.memory = DroneMemory(drone_id=drone_id)
        self.storage = DroneStorage(drone_id=drone_id)
        self.reputation = DroneReputation(drone_id=drone_id)
        self.weather = WeatherService()
        self.pipeline = MissionPipeline(
            drone_ids=[drone_id],
            drone_reputations={drone_id: self.reputation},
        )
        from dronesync.replay_guard import ReplayGuard
        self.replay_guard = ReplayGuard()

    def handle(self, synapse_task: Dict) -> Dict:
        """
        Принимает задание от валидатора, выполняет полный DroneSync pipeline,
        возвращает PoPW артефакт.
        """
        if not isinstance(synapse_task, dict):
            return {"status": "REJECTED", "reason": "invalid_input_type", "on_chain_ready": False}
        if not synapse_task:
            return {"status": "REJECTED", "reason": "empty_task", "on_chain_ready": False}

        waypoints = synapse_task.get("waypoints", [])
        for wp in waypoints:
            if isinstance(wp, dict):
                lat, lon = float(wp.get("lat", 0)), float(wp.get("lon", 0))
                alt = float(wp.get("alt", 0.0))
            elif len(wp) >= 2:
                lat, lon = float(wp[0]), float(wp[1])
                alt = float(wp[2]) if len(wp) >= 3 else 0.0
            else:
                continue
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return {"status": "REJECTED", "reason": "invalid_gps_coordinates", "on_chain_ready": False}
            if not (0 <= alt <= 500):
                return {"status": "REJECTED", "reason": "invalid_altitude", "on_chain_ready": False}

        battery = synapse_task.get("battery")
        if battery is not None and not (0 <= float(battery) <= 100):
            return {"status": "REJECTED", "reason": "invalid_battery", "on_chain_ready": False}

        try:
            t_start = time.time()

            # 1. Firewall check
            cmd = {
                "action": "execute_task",
                "source": "konnex_validator",
                "timestamp": int(time.time()),
            }
            cmd["signature"] = _hmac.new(
                self.firewall._secret,
                json.dumps(cmd, sort_keys=True).encode(),
                hashlib.sha256
            ).hexdigest()
            fw_result = self.firewall.filter(cmd)
            if fw_result["status"] == "BLOCKED":
                return {
                    "mission_id": synapse_task.get("task_id", "unknown"),
                    "status": "BLOCKED",
                    "reason": fw_result["reason"],
                    "on_chain_ready": False,
                }

            # 2. Конвертируем задание в MissionInstruction
            mission = self.adapter.from_synapse_task(synapse_task)
            rg_check = self.replay_guard.check(
                mission.mission_id, float(synapse_task.get("created_at", time.time()))
            )
            if not rg_check["allowed"]:
                return {"status": "REJECTED", "reason": rg_check["reason"],
                        "mission_id": mission.mission_id}

            # 3. Планируем траекторию
            trajectory = self.planner.plan_trajectory(mission)

            # 4. Запускаем симуляцию среды
            sensor_data = self.env.run(trajectory)

            # 5. Оцениваем траекторию
            score = self.evaluator.score(trajectory, sensor_data)
            replay = self.evaluator.replay_validate(trajectory)

            # 6. Проверка безопасности
            security_result = self.security.full_security_check(trajectory, score)

            # 7. Запускаем канонический pipeline (PoPW + SensorBundle + ZK + ScoreRoot + reputation)
            pipeline_result = self.pipeline.run(
                mission, trajectory, sensor_data, score,
                executing_drone_id=self.drone_id,
            )

            # 8. Обновляем память о полёте (уникально для synapse)
            current_weather = self.weather.get_current()
            self.memory.record_flight(
                trajectory.positions,
                duration_s=round(time.time() - t_start, 2),
                wind_ms=current_weather.wind_speed,
            )

            # 9. Сохраняем в персистентное хранилище
            self.storage.append_mission({
                "mission_id": mission.mission_id,
                "score": score,
                "duration_s": round(time.time() - t_start, 2),
                "timestamp": int(time.time()),
            })

            if isinstance(self.planner, AIPlanner):
                self.planner.learn_from_score(score)

            duration = round(time.time() - t_start, 3)
            record = pipeline_result["popw_record"]
            checks = pipeline_result["checks"]
            mission_safe = security_result.get("mission_cleared", True)

            result = {
                "mission_id": mission.mission_id,
                "status": "OK",
                "score": score,
                "replay_status": replay["status"],
                "replay_steps": replay.get("steps_count", 0),
                "trajectory_hash": checks["trajectory_hash"],
                "sensor_hash": checks["sensor_bundle_hash"],
                "bundle_hash": checks["sensor_bundle_hash"],
                "tee_status": record["attestation"]["status"],
                "attestation_id": record["attestation"]["attestation_id"],
                "security": {
                    "overall_status": security_result["overall_status"],
                    "threat_level": checks["threat_level"],
                    "mission_safe": mission_safe,
                },
                "reputation": pipeline_result["reputation"] or self.reputation.get_status(),
                "popw": record,
                "on_chain_ready": pipeline_result["on_chain_ready"],
                "proof_package": {
                    "trajectory_hash": checks["trajectory_hash"],
                    "sensor_hash": checks["sensor_bundle_hash"],
                    "score": score,
                    "attestation_id": record["attestation"]["attestation_id"],
                    "chain_string": "PROOF|" + mission.mission_id + "|" +
                        checks["trajectory_hash"][:16] + "|" +
                        checks["sensor_bundle_hash"][:16] + "|" +
                        str(score),
                },
                "pipeline_hash": pipeline_result["pipeline_hash"],
                "zk_proof": pipeline_result.get("zk_proof"),
                "duration_s": duration,
            }

            TxQueue().enqueue(result)
            return result

        except Exception as e:
            return {
                "mission_id": synapse_task.get("task_id", "unknown"),
                "status": "ERROR",
                "reason": str(e),
                "on_chain_ready": False,
            }


class SwarmSynapseHandler:
    """
    Обработчик заданий для роя дронов.
    """

    def __init__(self, drone_ids: list):
        self.drone_ids = drone_ids
        self.handlers = {
            d: DroneNavSynapseHandler(drone_id=d, use_ai_planner=True)
            for d in drone_ids
        }
        self.consensus = SwarmConsensus(drone_ids=drone_ids)

    def handle_swarm_task(self, synapse_task: Dict) -> Dict:
        results = {}
        for drone_id, handler in self.handlers.items():
            drone_task = dict(synapse_task)
            drone_task["task_id"] = synapse_task.get("task_id", "TASK") + "_" + drone_id
            results[drone_id] = handler.handle(drone_task)

        votes = [
            (d, results[d]["score"] >= 80)
            for d in self.drone_ids
            if results[d].get("status") == "OK"
        ]
        mission_id = synapse_task.get("task_id", "DSYNC_swarm")
        consensus_result = self.consensus.vote_on_route(mission_id, votes)
        from dronesync.swarm_consensus import ByzantineDetector
        _bd = ByzantineDetector(self.consensus)
        _bd.analyze(consensus_result, votes)

        avg_score = round(
            sum(r["score"] for r in results.values() if r.get("status") == "OK")
            / max(len([r for r in results.values() if r.get("status") == "OK"]), 1),
            2,
        )

        return {
            "swarm_mission_id": mission_id,
            "drone_results": results,
            "consensus": consensus_result,
            "avg_score": avg_score,
            "swarm_approved": consensus_result["status"] == "APPROVED",
            "on_chain_ready": all(
                r.get("on_chain_ready", False) for r in results.values()
            ),
        }


def demo_synapse():
    """Демонстрация обработки задания от валидатора Konnex."""

    print("=" * 55)
    print("KONNEX DroneNavSynapse → DroneSync ADAPTER")
    print("=" * 55)

    validator_task = {
        "task_id": "KNX_TASK_" + str(int(time.time())),
        "mission_type": "urban_delivery",
        "origin": {"lat": 0.0, "lon": 0.0, "alt": 50, "speed": 5},
        "destination": {"lat": 0.05, "lon": 0.05, "alt": 50, "speed": 5},
        "waypoints": [
            {"lat": 0.025, "lon": 0.025, "alt": 50, "speed": 5},
        ],
        "drone_count": 1,
        "payload_kg": 0.5,
        "validator_signature": "konnex_testnet_v1_sig",
    }

    print("validator_task_id: " + validator_task["task_id"])
    print()

    handler = DroneNavSynapseHandler(drone_id=DRONE_ID, use_ai_planner=True)
    response = handler.handle(validator_task)

    print("SINGLE DRONE RESPONSE:")
    print("  mission_id:      " + response["mission_id"])
    print("  status:          " + response["status"])
    print("  score:           " + str(response["score"]))
    print("  replay_status:   " + response["replay_status"])
    print("  replay_steps:    " + str(response["replay_steps"]))
    print("  trajectory_hash: " + response["trajectory_hash"][:20] + "...")
    print("  sensor_hash:     " + response["sensor_hash"][:20] + "...")
    print("  bundle_hash:     " + response["bundle_hash"][:20] + "...")
    print("  tee_status:      " + response["tee_status"])
    print("  attestation_id:  " + response["attestation_id"])
    print("  security_status: " + response["security"]["overall_status"])
    print("  threat_level:    " + response["security"]["threat_level"])
    print("  on_chain_ready:  " + str(response["on_chain_ready"]))
    print("  duration_s:      " + str(response["duration_s"]))
    print()

    print("SWARM (3 DRONES) RESPONSE:")
    swarm = SwarmSynapseHandler(drone_ids=["drone_0", "drone_1", "drone_2"])

    swarm_task = dict(validator_task)
    swarm_task["task_id"] = "KNX_SWARM_" + str(int(time.time()))
    swarm_task["drone_count"] = 3

    swarm_response = swarm.handle_swarm_task(swarm_task)
    print("  swarm_mission_id: " + swarm_response["swarm_mission_id"])
    print("  avg_score:        " + str(swarm_response["avg_score"]))
    print("  swarm_approved:   " + str(swarm_response["swarm_approved"]))
    print("  on_chain_ready:   " + str(swarm_response["on_chain_ready"]))
    for d, r in swarm_response["drone_results"].items():
        print("    " + d + ": score=" + str(r.get("score", "N/A")) +
              " | tee=" + str(r.get("tee_status", "N/A")))
    print()
    print("DroneNavSynapse adapter READY for Konnex NETUID 4")


if __name__ == "__main__":
    demo_synapse()
