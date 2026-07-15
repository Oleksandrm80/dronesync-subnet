"""Tests for aviation_compliance.py and operator_license.py (from backup/server merge)."""
from dronesync.aviation_compliance import AviationCompliance
from dronesync.operator_license import OperatorLicense, LicenseRegistry


def test_flight_within_limits_is_compliant():
    compliance = AviationCompliance()
    assert compliance.is_compliant(alt_m=100.0, is_licensed=True, is_daylight=True)


def test_altitude_violation_detected():
    compliance = AviationCompliance()
    violations = compliance.check_flight(alt_m=150.0, is_licensed=True, is_daylight=True)
    assert any("120m" in v for v in violations)
    assert not compliance.is_compliant(alt_m=150.0, is_licensed=True, is_daylight=True)


def test_unlicensed_night_flight_has_two_violations():
    compliance = AviationCompliance()
    violations = compliance.check_flight(alt_m=50.0, is_licensed=False, is_daylight=False)
    assert len(violations) == 2


def test_license_issue_and_verify():
    registry = LicenseRegistry()
    lic = OperatorLicense(
        license_id="LIC-001", operator_id="OP-001", operator_name="Test Operator",
        issued_at="2026-01-01", expires_at="2027-01-01", license_type="commercial",
    )
    registry.issue(lic)
    assert registry.is_licensed("OP-001")
    assert registry.verify("OP-001").license_id == "LIC-001"


def test_license_revoke_disables_it():
    registry = LicenseRegistry()
    lic = OperatorLicense(
        license_id="LIC-002", operator_id="OP-002", operator_name="Test Operator 2",
        issued_at="2026-01-01", expires_at="2027-01-01", license_type="recreational",
    )
    registry.issue(lic)
    registry.revoke("LIC-002")
    assert not registry.is_licensed("OP-002")


def test_unknown_operator_is_not_licensed():
    registry = LicenseRegistry()
    assert registry.verify("NOBODY") is None
    assert not registry.is_licensed("NOBODY")
