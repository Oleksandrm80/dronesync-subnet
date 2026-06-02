"""Tests for security, threat defense, and command signing."""
import time
import pytest
from dronesync.security import (
    GPSSpoofingDetector, CommandSigner, AnomalyDetector, DroneSecuritySuite
)
from dronesync.threat_defense import ThreatDefense


def make_clean_positions():
    base_time = int(time.time())
    return [
        [47.3769 + i * 0.0001, 8.5417 + i * 0.0001, 50.0, base_time + i * 5]
        for i in range(5)
    ]


def make_spoofed_positions():
    base_time = int(time.time())
    positions = make_clean_positions()
    positions[2] = [48.0, 9.0, 50.0, base_time + 10]  # teleport
    return positions


# --- GPSSpoofingDetector ---

def test_clean_trajectory_not_flagged():
    detector = GPSSpoofingDetector()
    result = detector.analyze_trajectory(make_clean_positions())
    assert result["status"] == "CLEAN"
    assert not result["spoofing_detected"]


def test_spoofed_trajectory_flagged():
    detector = GPSSpoofingDetector()
    result = detector.analyze_trajectory(make_spoofed_positions())
    assert result["spoofing_detected"]
    assert result["status"] == "COMPROMISED"


# --- CommandSigner ---

def test_command_sign_and_verify():
    signer = CommandSigner()
    cmd = {"action": "fly", "destination": "47.38,8.54"}
    signed = signer.sign_command(cmd)
    assert signer.verify_command(signed)


def test_replay_attack_rejected():
    signer = CommandSigner()
    cmd = {"action": "fly", "destination": "47.38,8.54"}
    signed = signer.sign_command(cmd)
    assert signer.verify_command(signed)
    assert not signer.verify_command(signed)  # replay rejected


def test_tampered_command_rejected():
    signer = CommandSigner()
    cmd = {"action": "fly", "destination": "47.38,8.54"}
    signed = signer.sign_command(cmd)
    signed["command"]["destination"] = "99.99,99.99"
    assert not signer.verify_command(signed)


# --- ThreatDefense ---

def test_full_assessment_clean():
    defense = ThreatDefense()
    positions = make_clean_positions()
    result = defense.full_threat_assessment(positions, signal_strength=0.9)
    assert result["mission_safe"]
    assert result["overall_threat_level"] == "NONE"
    assert result["gps_status"] == "CLEAN"
    assert result["jamming_status"] == "CLEAR"


def test_jamming_detected_on_weak_signal():
    defense = ThreatDefense()
    positions = make_clean_positions()
    result = defense.full_threat_assessment(positions, signal_strength=0.1)
    assert result["jamming_status"] == "DETECTED"
    assert not result["mission_safe"]


def test_firmware_verification():
    defense = ThreatDefense()
    import hashlib
    data = b"valid_firmware_v1"
    h = hashlib.sha256(data).hexdigest()
    result = defense.verify_firmware(data, h)
    assert result["firmware_valid"]
    assert result["action"] == "APPLY_UPDATE"


def test_firmware_injection_detected():
    defense = ThreatDefense()
    import hashlib
    data = b"valid_firmware_v1"
    h = hashlib.sha256(data).hexdigest()
    tampered = b"malicious_firmware"
    result = defense.verify_firmware(tampered, h)
    assert not result["firmware_valid"]
    assert result["threat"] == "FIRMWARE_INJECTION"
    assert result["action"] == "REJECT_UPDATE"


# --- DroneSecuritySuite ---

def test_security_suite_secure():
    from dronesync.protocol import Trajectory
    import time as t
    base = int(t.time())
    traj = Trajectory(
        positions=[[47.3769 + i * 0.0001, 8.5417 + i * 0.0001, 50.0, base + i * 5]
                   for i in range(5)],
        velocities=[5.0] * 5,
        timestamps=[base + i * 5 for i in range(5)],
    )
    suite = DroneSecuritySuite()
    result = suite.full_security_check(traj, 95)
    assert result["overall_status"] == "SECURE"
    assert result["mission_cleared"]
