# dronesync/synapse.py
"""
DroneSync ↔ Konnex DroneNavSynapse adapter.

DroneNavSynapse — протокол валидатора Konnex (NETUID 4).
Этот модуль принимает задание от валидатора, запускает полный
DroneSync pipeline (planner → env → TEE → PoPW) и возвращает
готовый артефакт для on-chain scoring.
"""

import time
import hashlib
import json
from typing import Optional, Dict, Any

from miner.planner import DronePlanner, AIPlanner
from environment.sim import DroneEnvironment
from validator.scorer import DroneEvaluator
from dronesync.verifier import PoPWRecord
from dronesync.sensor_bundle import SensorBundle
from dronesync.reputation import DroneReputation
from dronesync.security import DroneSecuritySuite
from dronesync.threat_defense import ThreatDefense
from dronesync.firewall import DroneFirewall
from dronesync.memory import DroneMemory
from dronesync.storage import DroneStorage
from dronesync.swarm_consensus import SwarmConsensus
from miner.weather import WeatherService


class MissionAdapter:
    """Конвертирует DroneNavSynapse task → внутренний формат DroneSync."""

    def from_synapse_task(self, task: Dict) -> object:
        origin_raw = task.get("origin", {})
        dest_raw = task.get("destination", {})

        origin = type("Waypoint", (), {
            "lat": float(origin_raw.get("lat", 47.3769)),
            "lon": float(origin_raw.get("lon", 8.5417)),
            "alt": float(origin_raw.get("alt", 50)),
            "speed": float(origin_raw.get("speed", 5)),
        })

        destination = type("Waypoint", (), {
            "lat": float(dest_raw.get("lat", 47.3800)),
            "lon": float(dest_raw.get("lon", 8.5450)),
            "alt": float(dest_raw.get("alt", 50)),
            "speed": float(dest_raw.get("speed", 5)),
        })

        waypoints = []
        for wp in task.get("waypoints", []):
            waypoints.append(type("Waypoint", (), {
                "lat": float(wp.get("lat", 47.3780)),
                "lon": float(wp.get("lon", 8.5430)),
                "alt": float(wp.get("alt", 50)),
                "speed": float(wp.get("speed", 5)),
            }))

        mission = type("Mission", (), {
            "mission_id": task.get("task_id", "DSYNC_" + str(int(time.time()))),
            "mission_type": type("MType", (), {
                "value": task.get("mission_type", "urban_delivery")
            }),
            "origin": origin,
            "destination": destination,
            "waypoints": waypoints,
            "drone_count": task.get("drone_count", 1),
            "payload_kg": task.get("payload_kg", 0.5),
        })
        return mission


class DroneNavSynapseHandler:
    """
    Основной обработчик задания от валидатора Konnex.

    Использование:
        handler = DroneNavSynapseHandler(drone_id="DRONE_001")
        response = handler.handle(synapse_task)
        # response содержит полный PoPW артефакт для on-chain scoring
    """

    def __init__(self, drone_id: str = "DRONE_001", use_ai_planner: bool = False):
        self.drone_id = drone_id
        self.adapter = MissionAdapter()
        self.planner = AIPlanner() if use_ai_planner else DronePlanner()
        self.env = DroneEnvironment()
        self.evaluator = DroneEvaluator()
        self.security = DroneSecuritySuite()
        self.defense = ThreatDefense()
        self.firewall = DroneFirewall(drone_id=drone_id)
        self.memory = DroneMemory(drone_id=drone_id)
        self.storage = DroneStorage(drone_id=drone_id)
        self.reputation = DroneReputation(drone_id=drone_id)
        self.weather = WeatherService()

    def handle(self, synapse_task: Dict) -> Dict:
        """
        Принимает задание от валидатора, выполняет полный DroneSync pipeline,
        возвращает PoPW артефакт.

        Args:
            synapse_task: словарь с полями task_id, origin, destination, ...

        Returns:
            dict с полями: mission_id, score, trajectory_hash, sensor_hash,
                           bundle_hash, tee_status, popw, on_chain_ready
        """
        t_start = time.time()

        # 1. Firewall check — проверяем что команда легитимна
        cmd = {
            "action": "execute_task",
            "source": "konnex_validator",
            "timestamp": int(time.time()),
            "signature": synapse_task.get("validator_signature", "konnex_v1"),
        }
        fw_result = self.firewall.filter(cmd)
        if fw_result["status"] == "BLOCKED":
            return {
                "mission_id": synapse_task.get("task_id", "unknown"),
                "status": "BLOCKED",
                "reason": fw_result["reason"],
                "on_chain_ready": False,
            }

        # 2. Конвертируем задание
        mission = self.adapter.from_synapse_task(synapse_task)

        # 3. Планируем траекторию
        trajectory = self.planner.plan_trajectory(mission)

        # 4. Запускаем симуляцию среды (сенсоры, препятствия, погода)
        sensor_data = self.env.run(trajectory)

        # 5. Оцениваем траекторию
        score = self.evaluator.score(trajectory, sensor_data)
        replay = self.evaluator.replay_validate(trajectory)

        # 6. Проверка безопасности (GPS spoofing, hijacking, threat level)
        security_result = self.security.full_security_check(trajectory, score)
        threat_result = self.defense.full_threat_assessment(
            trajectory.positions,
            signal_strength=0.92
        )

        # 7. Создаём PoPW запись (TEE attestation)
        popw = PoPWRecord()
        record = popw.create_record(
            mission_id=mission.mission_id,
            trajectory=trajectory,
            score=score,
        )

        # 8. Упаковываем сенсорный бандл (evidence package)
        bundle = SensorBundle().pack(
            mission_id=mission.mission_id,
            trajectory=trajectory,
            sensor_data=sensor_data,
            popw_record=record,
        )

        # 9. Обновляем память и репутацию дрона
        mission_safe = security_result.get("mission_cleared", True)
        current_weather = self.weather.get_current()
        self.memory.record_flight(
            trajectory.positions,
            duration_s=round(time.time() - t_start, 2),
            wind_ms=current_weather.wind_speed,
        )
        self.reputation.record_mission(
            mission.mission_id, score, mission_safe, battery_used_pct=7.5
        )

        # 10. Сохраняем в персистентное хранилище
        self.storage.append_mission({
            "mission_id": mission.mission_id,
            "score": score,
            "duration_s": round(time.time() - t_start, 2),
            "timestamp": int(time.time()),
        })

        if isinstance(self.planner, AIPlanner):
            self.planner.learn_from_score(score)

        duration = round(time.time() - t_start, 3)

        return {
            "mission_id": mission.mission_id,
            "status": "OK",
            "score": score,
            "replay_status": replay["status"],
            "replay_steps": replay.get("steps_count", 0),
            "trajectory_hash": record["trajectory_hash"],
            "sensor_hash": bundle["sensor_hash"],
            "bundle_hash": bundle["bundle_hash"],
            "tee_status": bundle["popw"]["tee_status"],
            "attestation_id": record["attestation"]["attestation_id"],
            "security": {
                "overall_status": security_result["overall_status"],
                "threat_level": threat_result["overall_threat_level"],
                "mission_safe": mission_safe,
            },
            "reputation": self.reputation.get_status(),
            "popw": record,
            "on_chain_ready": record["on_chain_ready"] and bundle["on_chain_ready"],
            "duration_s": duration,
        }


class SwarmSynapseHandler:
    """
    Обработчик заданий для роя дронов (несколько экземпляров DroneNavSynapse).
    Добавляет децентрализованное голосование SwarmConsensus.
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
            results[drone_id] = handler.handle(synapse_task)

        # Голосование по маршруту — одобряют дроны с score >= 80
        votes = [
            (d, results[d]["score"] >= 80)
            for d in self.drone_ids
            if results[d].get("status") == "OK"
        ]
        mission_id = synapse_task.get("task_id", "DSYNC_swarm")
        consensus_result = self.consensus.vote_on_route(mission_id, votes)

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

    # Имитируем задание от валидатора Konnex
    validator_task = {
        "task_id": "KNX_TASK_" + str(int(time.time())),
        "mission_type": "urban_delivery",
        "origin": {"lat": 47.3769, "lon": 8.5417, "alt": 50, "speed": 5},
        "destination": {"lat": 47.3820, "lon": 8.5460, "alt": 50, "speed": 5},
        "waypoints": [
            {"lat": 47.3790, "lon": 8.5435, "alt": 50, "speed": 5},
        ],
        "drone_count": 1,
        "payload_kg": 0.5,
        "validator_signature": "konnex_testnet_v1_sig",
    }

    print("validator_task_id: " + validator_task["task_id"])
    print()

    # Одиночный дрон
    handler = DroneNavSynapseHandler(drone_id="DRONE_001", use_ai_planner=True)
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
    print("  reputation_tier: " + response["reputation"]["tier"])
    print("  on_chain_ready:  " + str(response["on_chain_ready"]))
    print("  duration_s:      " + str(response["duration_s"]))
    print()

    # Рой из 3 дронов
    print("SWARM (3 DRONES) RESPONSE:")
    swarm = SwarmSynapseHandler(drone_ids=["drone_0", "drone_1", "drone_2"])

    swarm_task = dict(validator_task)
    swarm_task["task_id"] = "KNX_SWARM_" + str(int(time.time()))
    swarm_task["drone_count"] = 3

    swarm_response = swarm.handle_swarm_task(swarm_task)
    print("  swarm_mission_id: " + swarm_response["swarm_mission_id"])
    print("  avg_score:        " + str(swarm_response["avg_score"]))
    print("  swarm_approved:   " + str(swarm_response["swarm_approved"]))
    print("  consensus_votes:  " + str(swarm_response["consensus"]["approval_weight"]) +
          "/" + str(swarm_response["consensus"]["total_voters"]))
    print("  on_chain_ready:   " + str(swarm_response["on_chain_ready"]))
    for d, r in swarm_response["drone_results"].items():
        print("    " + d + ": score=" + str(r.get("score", "N/A")) +
              " | tee=" + str(r.get("tee_status", "N/A")))
    print()
    print("DroneNavSynapse adapter READY for Konnex NETUID 4")


if __name__ == "__main__":
    demo_synapse()
