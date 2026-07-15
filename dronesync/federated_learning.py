"""
dronesync/federated_learning.py

Federated Learning for drone swarm intelligence.
Each drone trains locally on its own flight data,
then shares only model weights — never raw trajectory data.
All drones collectively become smarter without revealing routes.
"""

import json
import time
import hashlib
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelWeights:
    """Local model weights from one drone."""
    drone_id: str
    round_id: int
    weights: Dict[str, float]
    n_samples: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "drone_id": self.drone_id,
            "round_id": self.round_id,
            "weights": self.weights,
            "n_samples": self.n_samples,
            "timestamp": self.timestamp,
        }

    def checksum(self) -> str:
        raw = json.dumps(self.weights, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class LocalDroneModel:
    """
    Local AI model on each drone.
    Learns from its own flight experience.
    Never shares raw flight data — only weights.
    """

    FEATURES = [
        "avg_speed", "avg_altitude", "battery_efficiency",
        "obstacle_avoidance_rate", "path_deviation", "weather_impact",
    ]

    def __init__(self, drone_id: str):
        self.drone_id = drone_id
        self._weights: Dict[str, float] = {f: 0.5 for f in self.FEATURES}
        self._round = 0
        self._n_samples = 0

    def train(self, flight_records: List[dict]) -> ModelWeights:
        """
        Train on local flight data.
        Updates weights based on what worked well.
        """
        if not flight_records:
            return self._export_weights()

        for record in flight_records:
            score = record.get("score", 0.5)
            lr = 0.1

            for feature in self.FEATURES:
                if feature in record:
                    gradient = (score - 0.5) * record[feature]
                    self._weights[feature] += lr * gradient
                    self._weights[feature] = max(0.0, min(1.0, self._weights[feature]))

        self._n_samples += len(flight_records)
        self._round += 1
        logger.info("[%s] Trained round %d on %d samples",
                    self.drone_id, self._round, len(flight_records))
        return self._export_weights()

    def apply_global_weights(self, global_weights: Dict[str, float]):
        """Apply aggregated weights from federation."""
        for k, v in global_weights.items():
            if k in self._weights:
                self._weights[k] = v
        logger.info("[%s] Applied global weights", self.drone_id)

    def predict_action_score(self, features: Dict[str, float]) -> float:
        """Predict mission success score based on current weights."""
        score = 0.0
        total_weight = 0.0
        for f, w in self._weights.items():
            if f in features:
                score += w * features[f]
                total_weight += w
        return round(score / total_weight, 3) if total_weight > 0 else 0.5

    def _export_weights(self) -> ModelWeights:
        return ModelWeights(
            drone_id=self.drone_id,
            round_id=self._round,
            weights=dict(self._weights),
            n_samples=self._n_samples,
        )

    @property
    def weights(self) -> Dict[str, float]:
        return dict(self._weights)


class FederatedAggregator:
    """
    Central aggregator for federated learning.
    Collects weights from all drones, computes global model
    using FedAvg algorithm, distributes back to drones.
    Raw flight data never leaves individual drones.
    """

    def __init__(self, min_drones: int = 2):
        self.min_drones = min_drones
        self._round = 0
        self._global_weights: Dict[str, float] = {}
        self._history: List[dict] = []

    def aggregate(self, drone_weights: List[ModelWeights]) -> Optional[Dict[str, float]]:
        """
        FedAvg: weighted average of all drone models.
        Weight = number of training samples (more data = more influence).
        """
        if len(drone_weights) < self.min_drones:
            logger.warning("Not enough drones: %d < %d", len(drone_weights), self.min_drones)
            return None

        total_samples = sum(w.n_samples for w in drone_weights)
        if total_samples == 0:
            return None

        global_weights: Dict[str, float] = {}
        all_features = set()
        for dw in drone_weights:
            all_features.update(dw.weights.keys())

        for feature in all_features:
            weighted_sum = 0.0
            for dw in drone_weights:
                if feature in dw.weights:
                    weight = dw.n_samples / total_samples
                    weighted_sum += weight * dw.weights[feature]
            global_weights[feature] = round(weighted_sum, 6)

        self._round += 1
        self._global_weights = global_weights

        self._history.append({
            "round": self._round,
            "drones": len(drone_weights),
            "total_samples": total_samples,
            "global_weights": dict(global_weights),
            "timestamp": time.time(),
        })

        logger.info("Federation round %d: aggregated %d drones, %d samples",
                    self._round, len(drone_weights), total_samples)
        return global_weights

    @property
    def global_weights(self) -> Dict[str, float]:
        return dict(self._global_weights)

    @property
    def round(self) -> int:
        return self._round

    def summary(self) -> dict:
        return {
            "federation_rounds": self._round,
            "global_weights": self._global_weights,
            "history_rounds": len(self._history),
        }


class FederatedSwarm:
    """
    Manages a swarm of drones doing federated learning.
    Coordinates local training + global aggregation.
    """

    def __init__(self, drone_ids: List[str], min_drones: int = 2):
        self.drones: Dict[str, LocalDroneModel] = {
            did: LocalDroneModel(did) for did in drone_ids
        }
        self.aggregator = FederatedAggregator(min_drones=min_drones)

    def run_round(self, flight_data: Dict[str, List[dict]]) -> Dict[str, float]:
        """
        Run one federated learning round:
        1. Each drone trains locally
        2. Weights aggregated centrally
        3. Global model distributed back
        """
        local_weights = []
        for drone_id, drone in self.drones.items():
            records = flight_data.get(drone_id, [])
            weights = drone.train(records)
            local_weights.append(weights)
            logger.debug("[%s] checksum=%s", drone_id, weights.checksum())

        global_weights = self.aggregator.aggregate(local_weights)

        if global_weights:
            for drone in self.drones.values():
                drone.apply_global_weights(global_weights)

        return global_weights or {}

    def predict(self, drone_id: str, features: Dict[str, float]) -> float:
        drone = self.drones.get(drone_id)
        if not drone:
            return 0.5
        return drone.predict_action_score(features)
