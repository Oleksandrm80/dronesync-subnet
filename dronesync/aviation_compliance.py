from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ComplianceRule:
    rule_id: str
    description: str
    max_altitude_m: float = 120.0
    min_distance_from_people_m: float = 30.0
    requires_license: bool = True
    daylight_only: bool = True


class AviationCompliance:
    def __init__(self):
        self.rules = [
            ComplianceRule("ICAO-001", "Max altitude 120m AGL", max_altitude_m=120.0),
            ComplianceRule("ICAO-002", "30m distance from people", min_distance_from_people_m=30.0),
            ComplianceRule("ICAO-003", "Operator license required", requires_license=True),
            ComplianceRule("ICAO-004", "Daylight operations only", daylight_only=True),
        ]

    def check_altitude(self, alt_m: float) -> Tuple[bool, str]:
        if alt_m > 120.0:
            return False, f"Altitude {alt_m}m exceeds 120m limit"
        return True, "OK"

    def check_flight(self, alt_m: float, is_licensed: bool, is_daylight: bool) -> List[str]:
        violations = []
        ok, msg = self.check_altitude(alt_m)
        if not ok:
            violations.append(msg)
        if not is_licensed:
            violations.append("Operator license required")
        if not is_daylight:
            violations.append("Night flights not permitted")
        return violations

    def is_compliant(self, alt_m: float, is_licensed: bool, is_daylight: bool) -> bool:
        return len(self.check_flight(alt_m, is_licensed, is_daylight)) == 0


compliance = AviationCompliance()
