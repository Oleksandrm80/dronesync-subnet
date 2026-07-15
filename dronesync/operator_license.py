from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime


@dataclass
class OperatorLicense:
    license_id: str
    operator_id: str
    operator_name: str
    issued_at: str
    expires_at: str
    license_type: str  # "commercial", "recreational", "research"
    max_drones: int = 10
    allowed_zones: list = field(default_factory=list)
    is_active: bool = True


class LicenseRegistry:
    def __init__(self):
        self._licenses: Dict[str, OperatorLicense] = {}

    def issue(self, license: OperatorLicense):
        self._licenses[license.license_id] = license

    def revoke(self, license_id: str):
        if license_id in self._licenses:
            self._licenses[license_id].is_active = False

    def verify(self, operator_id: str) -> Optional[OperatorLicense]:
        for lic in self._licenses.values():
            if lic.operator_id == operator_id and lic.is_active:
                return lic
        return None

    def is_licensed(self, operator_id: str) -> bool:
        return self.verify(operator_id) is not None


license_registry = LicenseRegistry()
