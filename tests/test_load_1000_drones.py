import time
import random
from dronesync.drone_registry import DroneRegistry
from dronesync.geofencing import GeoFencer, GeoZone


def test_load_1000_drones():
    registry = DroneRegistry()
    geofencer = GeoFencer()
    geofencer.add_zone(GeoZone("restricted_1", "NoFlyZone", "no_fly", 50.0, 30.0, 500))

    start = time.time()
    for i in range(1000):
        drone_id = f"DRONE_{i:04d}"
        registry.register(drone_id)

    assert registry.count() == 1000

    violations = 0
    for i in range(1000):
        lat = 50.0 + random.uniform(-0.01, 0.01)
        lon = 30.0 + random.uniform(-0.01, 0.01)
        ok, zone = geofencer.check(lat, lon, 100)
        if not ok:
            violations += 1

    elapsed = time.time() - start
    print(f"1000 drones registered and checked in {elapsed:.2f}s, violations: {violations}")
    assert elapsed < 5.0


if __name__ == "__main__":
    test_load_1000_drones()
    print("PASS")
