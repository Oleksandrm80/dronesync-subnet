"""Tests for DroneStorage and SecureStorage — persistent drone state."""
import json
from dronesync.storage import DroneStorage, SecureStorage


def test_save_and_load_roundtrip(tmp_path):
    storage = DroneStorage("drone_A", storage_dir=str(tmp_path))
    storage.save({"battery": 80})
    loaded = storage.load()
    assert loaded["battery"] == 80
    assert loaded["drone_id"] == "drone_A"


def test_load_returns_empty_dict_when_no_file(tmp_path):
    storage = DroneStorage("drone_B", storage_dir=str(tmp_path))
    assert storage.load() == {}
    assert not storage.exists()


def test_tampered_file_detected(tmp_path):
    storage = DroneStorage("drone_C", storage_dir=str(tmp_path))
    storage.save({"battery": 80})
    with open(storage.path, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data["battery"] = 999
        f.seek(0)
        json.dump(data, f)
        f.truncate()
    loaded = storage.load()
    assert loaded.get("_tampered") is True


def test_corrupted_json_resets_and_backs_up(tmp_path):
    storage = DroneStorage("drone_D", storage_dir=str(tmp_path))
    storage.save({"battery": 80})
    with open(storage.path, "w", encoding="utf-8") as f:
        f.write("{not valid json")
    loaded = storage.load()
    assert loaded == {}
    assert (tmp_path / "drone_D.json.corrupted").exists()


def test_append_mission_keeps_history(tmp_path):
    storage = DroneStorage("drone_E", storage_dir=str(tmp_path))
    storage.append_mission({"mission_id": "M1", "score": 90})
    storage.append_mission({"mission_id": "M2", "score": 80})
    missions = storage.get_missions()
    assert [m["mission_id"] for m in missions] == ["M1", "M2"]


def test_append_mission_caps_history_at_1000(tmp_path):
    storage = DroneStorage("drone_F", storage_dir=str(tmp_path))
    for i in range(1005):
        storage.append_mission({"mission_id": f"M{i}"})
    missions = storage.get_missions()
    assert len(missions) == 1000
    assert missions[0]["mission_id"] == "M5"


def test_update_and_get_reputation(tmp_path):
    storage = DroneStorage("drone_G", storage_dir=str(tmp_path))
    storage.update_reputation(75, "TRUSTED")
    rep = storage.get_reputation()
    assert rep == {"score": 75, "tier": "TRUSTED"}


def test_get_reputation_defaults_when_unset(tmp_path):
    storage = DroneStorage("drone_H", storage_dir=str(tmp_path))
    assert storage.get_reputation() == {"score": 50, "tier": "ROOKIE"}


def test_clear_removes_file(tmp_path):
    storage = DroneStorage("drone_I", storage_dir=str(tmp_path))
    storage.save({"battery": 80})
    assert storage.exists()
    storage.clear()
    assert not storage.exists()


# --- SecureStorage ---

def test_secure_storage_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr("dronesync.storage.STORAGE_DIR", str(tmp_path))
    secure = SecureStorage("drone_J")
    secure.save("mission_1", {"waypoints": [1, 2, 3]})
    loaded = secure.load("mission_1")
    assert loaded == {"waypoints": [1, 2, 3]}


def test_secure_storage_verify_detects_tamper(tmp_path, monkeypatch):
    monkeypatch.setattr("dronesync.storage.STORAGE_DIR", str(tmp_path))
    secure = SecureStorage("drone_K")
    stored_hash = secure.save("mission_1", {"waypoints": [1, 2, 3]})
    assert secure.verify("mission_1", stored_hash)
    assert not secure.verify("mission_1", "0" * 64)


def test_secure_storage_get_status(tmp_path, monkeypatch):
    monkeypatch.setattr("dronesync.storage.STORAGE_DIR", str(tmp_path))
    secure = SecureStorage("drone_L")
    secure.save("mission_1", {"waypoints": [1, 2, 3]})
    status = secure.get_status()
    assert status["drone_id"] == "drone_L"
    assert status["total_records"] == 1
    assert status["encrypted"] is True
