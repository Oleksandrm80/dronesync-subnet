"""Tests for MinerWallet."""

import os
import pytest
from dronesync.wallet import MinerWallet, Transaction


WALLET_PATH = "/tmp/test_dronesync_wallet.json"


@pytest.fixture(autouse=True)
def cleanup():
    for _p in [WALLET_PATH, WALLET_PATH.replace(".json", ".db")]:
        if os.path.exists(_p):
            os.remove(_p)
    yield
    for _p in [WALLET_PATH, WALLET_PATH.replace(".json", ".db")]:
        if os.path.exists(_p):
            os.remove(_p)


def _wallet() -> MinerWallet:
    return MinerWallet(wallet_id="test-miner", persist_path=WALLET_PATH)


def test_initial_balance():
    w = _wallet()
    assert w.balance == 0.0


def test_credit():
    w = _wallet()
    tx = w.credit("mission-1", 1.5, reason="mission_reward")
    assert w.balance == 1.5
    assert tx.amount_knx == 1.5
    assert tx.mission_id == "mission-1"
    assert tx.balance_after == 1.5


def test_multiple_credits():
    w = _wallet()
    w.credit("m1", 1.0)
    w.credit("m2", 2.0)
    w.credit("m3", 0.5)
    assert w.balance == 3.5


def test_debit():
    w = _wallet()
    w.credit("m1", 2.0)
    tx = w.debit("m1", 0.5, reason="penalty")
    assert w.balance == 1.5
    assert tx.amount_knx == -0.5


def test_debit_no_negative_balance():
    w = _wallet()
    w.credit("m1", 1.0)
    w.debit("m1", 5.0)
    assert w.balance == 0.0


def test_transaction_count():
    w = _wallet()
    w.credit("m1", 1.0)
    w.credit("m2", 2.0)
    assert w.transaction_count == 2


def test_history():
    w = _wallet()
    w.credit("m1", 1.0)
    w.credit("m2", 2.0)
    h = w.history(limit=10)
    assert len(h) == 2
    assert h[0]["mission_id"] == "m1"
    assert h[1]["mission_id"] == "m2"


def test_history_limit():
    w = _wallet()
    for i in range(5):
        w.credit(f"m{i}", 1.0)
    h = w.history(limit=3)
    assert len(h) == 3


def test_summary():
    w = _wallet()
    w.credit("m1", 2.0)
    w.credit("m2", 1.0)
    w.debit("m3", 0.5)
    s = w.summary()
    assert s["balance_knx"] == 2.5
    assert s["total_earned_knx"] == 3.0
    assert s["total_penalties_knx"] == 0.5
    assert s["transaction_count"] == 3


def test_tx_id_unique():
    w = _wallet()
    tx1 = w.credit("m1", 1.0)
    tx2 = w.credit("m2", 1.0)
    assert tx1.tx_id != tx2.tx_id


def test_persist_and_reload():
    w = _wallet()
    w.credit("m1", 3.5)
    w.credit("m2", 1.0)
    w2 = MinerWallet(wallet_id="test-miner", persist_path=WALLET_PATH)
    assert w2.balance == 4.5
    assert w2.transaction_count == 2


def test_credit_negative_raises():
    w = _wallet()
    with pytest.raises(ValueError):
        w.credit("m1", -1.0)
