"""
Тесты для новых модулей: webhook, proof_of_delivery, auth.
"""
import pytest
import time


class TestProofOfDelivery:

    def test_snapshot_creation(self):
        from dronesync.proof_of_delivery import ProofOfDelivery
        pod = ProofOfDelivery()
        snapshot = pod.create_snapshot(
            mission_id="TEST_001",
            destination_lat=50.0,
            destination_lon=30.0,
            actual_lat=50.0001,
            actual_lon=30.0001,
            altitude=50.0,
            camera_detections=[{"label": "package", "confidence": 0.95}],
        )
        assert snapshot.mission_id == "TEST_001"
        assert snapshot.camera_snapshot_hash != ""
        assert snapshot.gps_accuracy_m() < 50.0

    def test_delivery_proved_when_accurate(self):
        from dronesync.proof_of_delivery import ProofOfDelivery
        pod = ProofOfDelivery()
        snapshot = pod.create_snapshot(
            mission_id="TEST_002",
            destination_lat=50.0,
            destination_lon=30.0,
            actual_lat=50.0001,
            actual_lon=30.0001,
            altitude=50.0,
            camera_detections=[{"label": "package", "confidence": 0.9}],
        )
        proof = pod.prove(snapshot)
        assert proof.delivered is True
        assert proof.proof_hash != ""
        assert proof.on_chain_ready is True

    def test_delivery_failed_when_gps_too_far(self):
        from dronesync.proof_of_delivery import ProofOfDelivery
        pod = ProofOfDelivery()
        snapshot = pod.create_snapshot(
            mission_id="TEST_003",
            destination_lat=50.0,
            destination_lon=30.0,
            actual_lat=50.01,
            actual_lon=30.01,
            altitude=50.0,
            camera_detections=[{"label": "package", "confidence": 0.9}],
        )
        proof = pod.prove(snapshot)
        assert proof.delivered is False

    def test_delivery_failed_without_camera(self):
        from dronesync.proof_of_delivery import ProofOfDelivery
        pod = ProofOfDelivery()
        snapshot = pod.create_snapshot(
            mission_id="TEST_004",
            destination_lat=50.0,
            destination_lon=30.0,
            actual_lat=50.0001,
            actual_lon=30.0001,
            altitude=50.0,
            camera_detections=[],
        )
        proof = pod.prove(snapshot)
        assert proof.delivered is False

    def test_proof_to_dict(self):
        from dronesync.proof_of_delivery import ProofOfDelivery
        pod = ProofOfDelivery()
        snapshot = pod.create_snapshot(
            mission_id="TEST_005",
            destination_lat=50.0,
            destination_lon=30.0,
            actual_lat=50.0001,
            actual_lon=30.0001,
            altitude=50.0,
            camera_detections=[{"label": "package"}],
        )
        proof = pod.prove(snapshot)
        d = proof.to_dict()
        assert "mission_id" in d
        assert "delivered" in d
        assert "proof_hash" in d
        assert "on_chain_ready" in d


class TestWebhook:

    def test_register_and_get(self, tmp_path, monkeypatch):
        from dronesync import webhook
        monkeypatch.setattr(webhook, "DB_PATH", tmp_path / "webhooks.db")
        monkeypatch.setattr(webhook, "_db", None)
        db = webhook.get_webhook_db()
        db.register("client_001", "https://example.com/callback", "secret123")
        hooks = db.get_webhooks("client_001")
        assert len(hooks) == 1
        assert hooks[0]["url"] == "https://example.com/callback"

    def test_deactivate(self, tmp_path, monkeypatch):
        from dronesync import webhook
        monkeypatch.setattr(webhook, "DB_PATH", tmp_path / "webhooks.db")
        monkeypatch.setattr(webhook, "_db", None)
        db = webhook.get_webhook_db()
        db.register("client_002", "https://example.com/cb", "secret")
        hooks = db.get_webhooks("client_002")
        assert db.deactivate(hooks[0]["id"], "client_002") is True
        hooks_after = db.get_webhooks("client_002")
        assert len(hooks_after) == 0

    def test_deactivate_rejects_non_owner(self, tmp_path, monkeypatch):
        from dronesync import webhook
        monkeypatch.setattr(webhook, "DB_PATH", tmp_path / "webhooks.db")
        monkeypatch.setattr(webhook, "_db", None)
        db = webhook.get_webhook_db()
        db.register("client_003", "https://example.com/cb", "secret")
        hooks = db.get_webhooks("client_003")
        assert db.deactivate(hooks[0]["id"], "client_999") is False
        hooks_after = db.get_webhooks("client_003")
        assert len(hooks_after) == 1

    def test_sign_payload(self):
        from dronesync.webhook import _sign_payload
        sig = _sign_payload("mysecret", b"payload")
        assert len(sig) == 64
        assert sig == _sign_payload("mysecret", b"payload")
        assert sig != _sign_payload("othersecret", b"payload")


class TestAuth:

    def test_create_and_verify(self, tmp_path, monkeypatch):
        from dronesync import auth
        monkeypatch.setattr(auth, "DB_PATH", tmp_path / "auth.db")
        monkeypatch.setattr(auth, "_auth_db", None)
        db = auth.get_auth_db()
        result = db.create_client("TestClient", "operator")
        assert result["api_key"].startswith("ds_")
        client = db.verify_key(result["api_key"])
        assert client is not None
        assert client.name == "TestClient"
        assert client.role == "operator"

    def test_revoke(self, tmp_path, monkeypatch):
        from dronesync import auth
        monkeypatch.setattr(auth, "DB_PATH", tmp_path / "auth.db")
        monkeypatch.setattr(auth, "_auth_db", None)
        db = auth.get_auth_db()
        result = db.create_client("RevokeMe", "customer")
        db.revoke_client(result["client_id"])
        client = db.verify_key(result["api_key"])
        assert client is None

    def test_validator_read_permission_granted_to_validator_and_admin(self):
        """Regression: GET /validator/scoreroot requires validator:read --
        it must actually be reachable by the validator and admin roles."""
        from dronesync.auth import ROLE_PERMISSIONS
        assert "validator:read" in ROLE_PERMISSIONS["validator"]
        assert "validator:read" in ROLE_PERMISSIONS["admin"]

    def test_invalid_key(self, tmp_path, monkeypatch):
        from dronesync import auth
        monkeypatch.setattr(auth, "DB_PATH", tmp_path / "auth.db")
        monkeypatch.setattr(auth, "_auth_db", None)
        db = auth.get_auth_db()
        client = db.verify_key("ds_invalidkey")
        assert client is None
