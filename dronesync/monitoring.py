"""
DroneSync - Monitoring & Alerting
Tracks system health, performance metrics, and sends alerts.
"""
import time
import threading
from collections import deque


class MetricsCollector:
    """Collects and stores system metrics."""

    def __init__(self, window_size: int = 1000):
        self._lock = threading.Lock()
        self._missions = deque(maxlen=window_size)
        self._errors = deque(maxlen=window_size)
        self._validator_latencies = deque(maxlen=window_size)
        self._start_time = time.time()

    def record_mission(self, mission_id: str, score: float, duration_ms: float, consensus: bool):
        with self._lock:
            self._missions.append({
                "mission_id": mission_id,
                "score": score,
                "duration_ms": duration_ms,
                "consensus": consensus,
                "timestamp": time.time(),
            })

    def record_error(self, error_type: str, message: str):
        with self._lock:
            self._errors.append({
                "type": error_type,
                "message": message,
                "timestamp": time.time(),
            })

    def record_validator_latency(self, validator_id: str, latency_ms: float):
        with self._lock:
            self._validator_latencies.append({
                "validator_id": validator_id,
                "latency_ms": latency_ms,
                "timestamp": time.time(),
            })

    def get_metrics(self) -> dict:
        with self._lock:
            missions = list(self._missions)
            errors = list(self._errors)
            latencies = list(self._validator_latencies)

        uptime = time.time() - self._start_time
        total = len(missions)

        if total == 0:
            avg_score = 0.0
            success_rate = 0.0
            avg_duration = 0.0
            missions_per_sec = 0.0
        else:
            avg_score = sum(m["score"] for m in missions) / total
            success_rate = sum(1 for m in missions if m["consensus"]) / total
            avg_duration = sum(m["duration_ms"] for m in missions) / total
            missions_per_sec = total / uptime if uptime > 0 else 0.0

        avg_latency = 0.0
        if latencies:
            avg_latency = sum(l["latency_ms"] for l in latencies) / len(latencies)

        return {
            "uptime_seconds": round(uptime, 1),
            "total_missions": total,
            "avg_score": round(avg_score, 4),
            "success_rate": round(success_rate, 4),
            "avg_duration_ms": round(avg_duration, 2),
            "missions_per_sec": round(missions_per_sec, 2),
            "total_errors": len(errors),
            "avg_validator_latency_ms": round(avg_latency, 2),
            "on_chain_ready": True,
        }


class AlertManager:
    """Generates alerts when metrics cross thresholds."""

    THRESHOLDS = {
        "min_score": 0.5,
        "min_success_rate": 0.8,
        "max_error_rate": 0.1,
        "max_latency_ms": 2000.0,
        "max_duration_ms": 5000.0,
    }

    def __init__(self, collector: MetricsCollector):
        self._collector = collector
        self._alerts = []
        self._lock = threading.Lock()

    def check(self) -> list:
        metrics = self._collector.get_metrics()
        alerts = []

        if metrics["total_missions"] == 0:
            return []

        if metrics["avg_score"] < self.THRESHOLDS["min_score"]:
            alerts.append({
                "level": "WARNING",
                "type": "LOW_SCORE",
                "message": f"Average score {metrics['avg_score']:.2f} below threshold {self.THRESHOLDS['min_score']}",
                "timestamp": time.time(),
            })

        if metrics["success_rate"] < self.THRESHOLDS["min_success_rate"]:
            alerts.append({
                "level": "CRITICAL",
                "type": "LOW_SUCCESS_RATE",
                "message": f"Success rate {metrics['success_rate']:.1%} below {self.THRESHOLDS['min_success_rate']:.1%}",
                "timestamp": time.time(),
            })

        if metrics["avg_validator_latency_ms"] > self.THRESHOLDS["max_latency_ms"]:
            alerts.append({
                "level": "WARNING",
                "type": "HIGH_LATENCY",
                "message": f"Validator latency {metrics['avg_validator_latency_ms']:.0f}ms exceeds {self.THRESHOLDS['max_latency_ms']}ms",
                "timestamp": time.time(),
            })

        if metrics["avg_duration_ms"] > self.THRESHOLDS["max_duration_ms"]:
            alerts.append({
                "level": "WARNING",
                "type": "SLOW_PROCESSING",
                "message": f"Mission processing {metrics['avg_duration_ms']:.0f}ms exceeds {self.THRESHOLDS['max_duration_ms']}ms",
                "timestamp": time.time(),
            })

        with self._lock:
            self._alerts.extend(alerts)

        return alerts

    def get_all_alerts(self) -> list:
        with self._lock:
            return list(self._alerts)

    def get_status(self) -> dict:
        alerts = self.check()
        critical = [a for a in alerts if a["level"] == "CRITICAL"]
        warnings = [a for a in alerts if a["level"] == "WARNING"]
        return {
            "healthy": len(critical) == 0,
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "alerts": alerts,
            "on_chain_ready": True,
        }
