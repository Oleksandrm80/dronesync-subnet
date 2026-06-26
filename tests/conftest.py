import os
import pytest
import glob


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    db_files = [
        "/tmp/test_recovery_guard.db",
        "/tmp/test_recovery_wallet.db",
        "/tmp/test_recovery_wallet_reload.db",
        "/tmp/concurrency_wallet.db",
        "/tmp/concurrency_guard.db",
        "/tmp/concurrency_guard2.db",
        "/tmp/million_guard.db",
        "/tmp/endurance_guard.db",
        "/tmp/endurance_wallet.db",
        "/tmp/fuzz_guard.db",
        "/tmp/fuzz_guard2.db",
        "/tmp/fuzz_wallet.db",
        "/tmp/chaos_guard.db",
        "/tmp/adv_guard.db",
        "/tmp/anticheat_guard.db",
    ]
    for path in db_files:
        if os.path.exists(path):
            os.remove(path)
    yield
    for path in db_files:
        if os.path.exists(path):
            os.remove(path)
