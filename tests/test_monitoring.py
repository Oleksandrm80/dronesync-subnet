"""
Monitoring & Alerting Test
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.monitoring import MetricsCollector, AlertManager


def test_metrics_empty():
    m = MetricsCollector()
    metrics = m.get_metrics()
    assert metrics["total_missions"] == 0
    assert metrics["avg_score"] == 0.0
    assert metrics["on_chain_ready"] is True


def test_metrics_record_mission():
    m = MetricsCollector()
    m.record_mission("m1", score=0.85, duration_ms=120.0, consensus=True)
    m.record_mission("m2", score=0.75, duration_ms=100.0, consensus=True)
    metrics = m.get_metrics()
    assert metrics["total_missions"] == 2
    assert metrics["avg_score"] == 0.8
    assert metrics["success_rate"] == 1.0


def test_metrics_failed_consensus():
    m = MetricsCollector()
    m.record_mission("m1", score=0.85, duration_ms=120.0, consensus=True)
    m.record_mission("m2", score=0.3, duration_ms=100.0, consensus=False)
    metrics = m.get_metrics()
    assert metrics["success_rate"] == 0.5


def test_metrics_validator_latency():
    m = MetricsCollector()
    m.record_validator_latency("VAL_001", 150.0)
    m.record_validator_latency("VAL_002", 250.0)
    metrics = m.get_metrics()
    assert metrics["avg_validator_latency_ms"] == 200.0


def test_metrics_error_recording():
    m = MetricsCollector()
    m.record_error("TIMEOUT", "Validator timeout")
    m.record_error("CRASH", "Node crashed")
    metrics = m.get_metrics()
    assert metrics["total_errors"] == 2


def test_alert_low_score():
    m = MetricsCollector()
    for i in range(10):
        m.record_mission(f"m{i}", score=0.3, duration_ms=100.0, consensus=False)
    alert_mgr = AlertManager(m)
    alerts = alert_mgr.check()
    types = [a["type"] for a in alerts]
    assert "LOW_SCORE" in types


def test_alert_low_success_rate():
    m = MetricsCollector()
    for i in range(10):
        m.record_mission(f"m{i}", score=0.7, duration_ms=100.0, consensus=False)
    alert_mgr = AlertManager(m)
    alerts = alert_mgr.check()
    types = [a["type"] for a in alerts]
    assert "LOW_SUCCESS_RATE" in types


def test_alert_high_latency():
    m = MetricsCollector()
    m.record_mission("m1", score=0.9, duration_ms=100.0, consensus=True)
    m.record_validator_latency("VAL_001", 3000.0)
    alert_mgr = AlertManager(m)
    alerts = alert_mgr.check()
    types = [a["type"] for a in alerts]
    assert "HIGH_LATENCY" in types


def test_no_alerts_healthy_system():
    m = MetricsCollector()
    for i in range(10):
        m.record_mission(f"m{i}", score=0.9, duration_ms=100.0, consensus=True)
    m.record_validator_latency("VAL_001", 100.0)
    alert_mgr = AlertManager(m)
    alerts = alert_mgr.check()
    assert len(alerts) == 0


def test_status_healthy():
    m = MetricsCollector()
    for i in range(5):
        m.record_mission(f"m{i}", score=0.9, duration_ms=100.0, consensus=True)
    alert_mgr = AlertManager(m)
    status = alert_mgr.get_status()
    assert status["healthy"] is True
    assert status["critical_count"] == 0
    assert status["on_chain_ready"] is True


def test_status_unhealthy():
    m = MetricsCollector()
    for i in range(10):
        m.record_mission(f"m{i}", score=0.3, duration_ms=100.0, consensus=False)
    alert_mgr = AlertManager(m)
    status = alert_mgr.get_status()
    assert status["healthy"] is False
    assert status["critical_count"] > 0
