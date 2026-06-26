"""
Validator TLS Auth Test
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dronesync.validator_auth import ValidatorAuth


def test_sign_and_verify():
    auth = ValidatorAuth(secret="test_secret")
    msg = {"type": "submit_popw", "mission_id": "m1"}
    signed = auth.sign_message(msg)
    assert auth.verify_message(signed)


def test_wrong_secret_rejected():
    auth1 = ValidatorAuth(secret="secret_A")
    auth2 = ValidatorAuth(secret="secret_B")
    msg = {"type": "submit_popw", "mission_id": "m1"}
    signed = auth1.sign_message(msg)
    assert not auth2.verify_message(signed)


def test_tampered_message_rejected():
    auth = ValidatorAuth(secret="test_secret")
    msg = {"type": "submit_popw", "mission_id": "m1"}
    signed = auth.sign_message(msg)
    signed["mission_id"] = "hacked"
    assert not auth.verify_message(signed)


def test_missing_signature_rejected():
    auth = ValidatorAuth(secret="test_secret")
    msg = {"type": "submit_popw", "mission_id": "m1"}
    assert not auth.verify_message(msg)


def test_token_generate_and_verify():
    auth = ValidatorAuth(secret="test_secret")
    token = auth.generate_token("VALIDATOR_001")
    assert auth.verify_token(token)


def test_token_wrong_secret_rejected():
    auth1 = ValidatorAuth(secret="secret_A")
    auth2 = ValidatorAuth(secret="secret_B")
    token = auth1.generate_token("VALIDATOR_001")
    assert not auth2.verify_token(token)


def test_expired_token_rejected():
    auth = ValidatorAuth(secret="test_secret")
    token = auth.generate_token("VALIDATOR_001")
    token["_ts"] = time.time() - 60
    assert not auth.verify_token(token)


def test_wss_uri():
    auth = ValidatorAuth()
    uri = auth.get_wss_uri("1.2.3.4", 9001)
    assert uri == "wss://1.2.3.4:9001"
