"""Tests for Federated Learning — no network required."""

import pytest
from dronesync.federated_learning import (
    LocalDroneModel, ModelWeights, FederatedAggregator, FederatedSwarm
)


def _flight_records(score: float = 0.8, n: int = 5) -> list:
    return [
        {
            "score": score,
            "avg_speed": 0.7,
            "avg_altitude": 0.6,
            "battery_efficiency": 0.8,
            "obstacle_avoidance_rate": 0.9,
            "path_deviation": 0.3,
            "weather_impact": 0.5,
        }
        for _ in range(n)
    ]


def test_local_model_train():
    model = LocalDroneModel("drone-1")
    weights = model.train(_flight_records(score=0.9, n=10))
    assert weights.drone_id == "drone-1"
    assert weights.round_id == 1
    assert weights.n_samples == 10
    assert len(weights.weights) == 6


def test_local_model_weights_bounded():
    model = LocalDroneModel("drone-1")
    for _ in range(20):
        model.train(_flight_records(score=1.0, n=5))
    for v in model.weights.values():
        assert 0.0 <= v <= 1.0


def test_local_model_predict():
    model = LocalDroneModel("drone-1")
    model.train(_flight_records(score=0.9, n=10))
    features = {
        "avg_speed": 0.8,
        "avg_altitude": 0.7,
        "battery_efficiency": 0.9,
    }
    score = model.predict_action_score(features)
    assert 0.0 <= score <= 1.0


def test_weights_checksum():
    w1 = ModelWeights("d1", 1, {"a": 0.5, "b": 0.3}, 10)
    w2 = ModelWeights("d1", 1, {"a": 0.5, "b": 0.3}, 10)
    w3 = ModelWeights("d1", 1, {"a": 0.9, "b": 0.1}, 10)
    assert w1.checksum() == w2.checksum()
    assert w1.checksum() != w3.checksum()


def test_aggregator_fedavg():
    agg = FederatedAggregator(min_drones=2)
    weights = [
        ModelWeights("d1", 1, {"speed": 0.8, "alt": 0.6}, n_samples=10),
        ModelWeights("d2", 1, {"speed": 0.4, "alt": 0.8}, n_samples=10),
    ]
    global_w = agg.aggregate(weights)
    assert global_w is not None
    assert abs(global_w["speed"] - 0.6) < 0.01
    assert abs(global_w["alt"] - 0.7) < 0.01


def test_aggregator_weighted():
    agg = FederatedAggregator(min_drones=2)
    weights = [
        ModelWeights("d1", 1, {"speed": 1.0}, n_samples=90),
        ModelWeights("d2", 1, {"speed": 0.0}, n_samples=10),
    ]
    global_w = agg.aggregate(weights)
    assert global_w["speed"] > 0.8


def test_aggregator_not_enough_drones():
    agg = FederatedAggregator(min_drones=3)
    weights = [
        ModelWeights("d1", 1, {"speed": 0.8}, n_samples=10),
        ModelWeights("d2", 1, {"speed": 0.6}, n_samples=10),
    ]
    result = agg.aggregate(weights)
    assert result is None


def test_aggregator_summary():
    agg = FederatedAggregator(min_drones=2)
    weights = [
        ModelWeights("d1", 1, {"speed": 0.8}, n_samples=10),
        ModelWeights("d2", 1, {"speed": 0.6}, n_samples=10),
    ]
    agg.aggregate(weights)
    s = agg.summary()
    assert s["federation_rounds"] == 1
    assert "global_weights" in s


def test_swarm_run_round():
    swarm = FederatedSwarm(["drone-1", "drone-2", "drone-3"], min_drones=2)
    flight_data = {
        "drone-1": _flight_records(score=0.9, n=10),
        "drone-2": _flight_records(score=0.7, n=8),
        "drone-3": _flight_records(score=0.85, n=12),
    }
    global_w = swarm.run_round(flight_data)
    assert len(global_w) > 0


def test_swarm_multiple_rounds():
    swarm = FederatedSwarm(["d1", "d2"], min_drones=2)
    for i in range(3):
        flight_data = {
            "d1": _flight_records(score=0.8, n=5),
            "d2": _flight_records(score=0.9, n=5),
        }
        swarm.run_round(flight_data)
    assert swarm.aggregator.round == 3


def test_swarm_predict():
    swarm = FederatedSwarm(["d1", "d2"], min_drones=2)
    flight_data = {
        "d1": _flight_records(score=0.9, n=10),
        "d2": _flight_records(score=0.8, n=10),
    }
    swarm.run_round(flight_data)
    score = swarm.predict("d1", {"avg_speed": 0.8, "avg_altitude": 0.7})
    assert 0.0 <= score <= 1.0


def test_apply_global_weights():
    model = LocalDroneModel("d1")
    model.apply_global_weights({"avg_speed": 0.99, "avg_altitude": 0.01})
    assert abs(model.weights["avg_speed"] - 0.99) < 0.001
