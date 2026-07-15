"""Tests for identity.py (hotkey resolution) and logger.py (centralized logging)."""
import logging

from dronesync.logger import get_logger
import dronesync.identity as identity


def test_get_logger_returns_configured_logger():
    logger = get_logger("test_logger_a")
    assert isinstance(logger, logging.Logger)
    assert logger.handlers


def test_get_logger_does_not_duplicate_handlers_on_repeat_calls():
    logger1 = get_logger("test_logger_b")
    handler_count = len(logger1.handlers)
    logger2 = get_logger("test_logger_b")
    assert logger1 is logger2
    assert len(logger2.handlers) == handler_count


def test_get_drone_id_falls_back_to_env_when_no_wallet(monkeypatch):
    monkeypatch.setattr(identity, "HOTKEY_PATH", "/nonexistent/path.txt")
    monkeypatch.setenv("DRONE_ID", "DRONE_TEST_123")
    assert identity.get_drone_id() == "DRONE_TEST_123"


def test_get_public_key_returns_empty_when_no_wallet(monkeypatch):
    monkeypatch.setattr(identity, "HOTKEY_PATH", "/nonexistent/path.txt")
    assert identity.get_public_key() == ""


def test_get_validator_id_rejects_path_outside_bittensor_dir(monkeypatch):
    monkeypatch.setenv("VALIDATOR_HOTKEY_PATH", "/etc/passwd")
    monkeypatch.setenv("VALIDATOR_ID", "VALIDATOR_TEST_123")
    assert identity.get_validator_id() == "VALIDATOR_TEST_123"
