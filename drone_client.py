"""
DroneSync - Drone Client
Connects a real or emulated drone to the DroneSync dashboard.
Usage: python3 drone_client.py --drone-id DRONE_001 --server http://localhost:8080
"""
import time
import json
import argparse
import urllib.request
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dronesync.mavlink_emulator import MAVLinkEmulator


def post(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def run(drone_id, server, interval=1.0):
    print(f"[DroneClient] Connecting {drone_id} to {server}")
    result = post(f"{server}/api/register", {"drone_id": drone_id, "source": "mavlink"})
    if not result:
        print("[ERROR] Could not register drone")
        return
    print(f"[DroneClient] Registered: {result}")

    emulator = MAVLinkEmulator()
    print(f"[DroneClient] Sending telemetry every {interval}s. Press Ctrl+C to stop.")
    try:
        while True:
            telemetry = emulator.tick()
            telemetry["drone_id"] = drone_id
            post(f"{server}/api/telemetry", telemetry)
            post(f"{server}/api/heartbeat", {"drone_id": drone_id})
            print(f"[{drone_id}] lat={telemetry['lat']} lon={telemetry['lon']} alt={telemetry['alt']}m bat={telemetry['battery_pct']}%")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[DroneClient] Disconnected")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--drone-id", default="DRONE_001")
    parser.add_argument("--server", default="http://localhost:8080")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    run(args.drone_id, args.server, args.interval)
