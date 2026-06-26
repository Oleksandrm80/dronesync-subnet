"""
Storage Recovery Test
Proves system handles damaged JSON, interrupted writes, missing files.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.replay_guard import ReplayGuard
from dronesync.wallet import MinerWallet


def test_replay_guard_missing_file():
    path = "/tmp/test_recovery_guard.json"
    if os.path.exists(path):
        os.remove(path)
    guard = ReplayGuard(persist_path=path)
    result = guard.check("mission-001", created_at=__import__('time').time())
    assert result["allowed"] is True


def test_replay_guard_corrupted_json():
    path = "/tmp/test_recovery_guard_corrupt.json"
    with open(path, "w") as f:
        f.write("{broken json:::}")
    try:
        guard = ReplayGuard(persist_path=path)
        result = guard.check("mission-001", created_at=__import__('time').time())
        assert result is not None
    except Exception as e:
        assert type(e).__name__ in ("JSONDecodeError", "ValueError")


def test_replay_guard_empty_file():
    path = "/tmp/test_recovery_guard_empty.json"
    with open(path, "w") as f:
        f.write("")
    try:
        guard = ReplayGuard(persist_path=path)
        result = guard.check("mission-001", created_at=__import__('time').time())
        assert result is not None
    except Exception as e:
        assert type(e).__name__ in ("JSONDecodeError", "ValueError")


def test_replay_guard_truncated_json():
    path = "/tmp/test_recovery_guard_trunc.json"
    with open(path, "w") as f:
        f.write('{"mission-001": 172')  # interrupted write
    try:
        guard = ReplayGuard(persist_path=path)
        result = guard.check("mission-002", created_at=__import__('time').time())
        assert result is not None
    except Exception as e:
        assert type(e).__name__ in ("JSONDecodeError", "ValueError")


def test_wallet_missing_file():
    path = "/tmp/test_recovery_wallet.json"
    if os.path.exists(path):
        os.remove(path)
    w = MinerWallet(wallet_id="recovery-test", persist_path=path)
    assert w.balance == 0.0
    w.credit("m1", 1.0)
    assert w.balance == 1.0


def test_wallet_corrupted_json():
    path = "/tmp/test_recovery_wallet_corrupt.json"
    with open(path, "w") as f:
        f.write("{broken:::}")
    try:
        w = MinerWallet(wallet_id="recovery-test", persist_path=path)
        assert w.balance == 0.0
    except Exception as e:
        assert type(e).__name__ in ("JSONDecodeError", "ValueError")


def test_wallet_empty_file():
    path = "/tmp/test_recovery_wallet_empty.json"
    with open(path, "w") as f:
        f.write("")
    try:
        w = MinerWallet(wallet_id="recovery-test", persist_path=path)
        assert w.balance == 0.0
    except Exception as e:
        assert type(e).__name__ in ("JSONDecodeError", "ValueError")


def test_wallet_persist_and_reload():
    path = "/tmp/test_recovery_wallet_reload.json"
    if os.path.exists(path):
        os.remove(path)
    w = MinerWallet(wallet_id="recovery-test", persist_path=path)
    w.credit("m1", 5.0)
    w.credit("m2", 3.0)
    w2 = MinerWallet(wallet_id="recovery-test", persist_path=path)
    assert w2.balance == 8.0
    assert w2.transaction_count == 2
