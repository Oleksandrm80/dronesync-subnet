"""
Key Leakage Test
Proves secret keys never appear in logs, tracebacks, or API responses.
"""
import json
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.firewall import DroneFirewall
from dronesync.wallet import Wallet, MinerWallet


def test_firewall_secret_not_in_report():
    fw = DroneFirewall("DRONE_001")
    secret = fw._secret.decode()
    report = fw.get_report()
    report_str = json.dumps(report)
    assert secret not in report_str, "Secret key must not appear in report"


def test_firewall_secret_not_in_block_reason():
    fw = DroneFirewall("DRONE_001")
    secret = fw._secret.decode()
    result = fw.filter({"action": "fly", "source": "op",
                        "timestamp": 0, "signature": "fake"})
    result_str = json.dumps(result)
    assert secret not in result_str, "Secret key must not appear in filter result"


def test_wallet_password_not_in_error():
    w = Wallet(path="/tmp/test_key_leak_wallet.enc")
    w.save("my_secret_key_abc123", "my_password_xyz")
    secret_leaked = False
    try:
        w.load("wrong_password")
    except Exception as e:
        tb = traceback.format_exc()
        assert "my_password_xyz" not in tb, "Password must not appear in traceback"
        assert "my_secret_key_abc123" not in tb, "Secret key must not appear in traceback"


def test_miner_wallet_no_keys_in_history():
    path = "/tmp/test_key_leak_miner.json"
    if os.path.exists(path):
        os.remove(path)
    w = MinerWallet(wallet_id="test-miner", persist_path=path)
    w.credit("m1", 1.0)
    history = w.get_history()
    history_str = json.dumps(history)
    assert "password" not in history_str.lower()
    assert "secret" not in history_str.lower()
    assert "private" not in history_str.lower()


def test_firewall_admin_token_not_in_report():
    fw = DroneFirewall("DRONE_001")
    admin_token = fw._admin_token
    report = fw.get_report()
    report_str = json.dumps(report)
    assert admin_token not in report_str, "Admin token must not appear in report"


def test_firewall_secret_not_in_allowed_log():
    fw = DroneFirewall("DRONE_001")
    secret = fw._secret.decode()
    fw.trusted_sources.add("trusted_op")
    fw.filter({"action": "fly", "source": "trusted_op", "timestamp": 0})
    log_str = json.dumps(fw.allowed_log)
    assert secret not in log_str, "Secret must not appear in allowed log"
