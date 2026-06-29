"""
demo_mavlink.py

Demo: Real telemetry from PX4 SITL → DroneSync PoPW

HOW TO USE:
1. Install PX4 SITL:
   git clone https://github.com/PX4/PX4-Autopilot.git
   cd PX4-Autopilot && make px4_sitl gazebo

2. Start SITL:
   cd PX4-Autopilot && make px4_sitl_default none_iris

3. Run this demo:
   python3 demo_mavlink.py

Or replay from a saved .tlog file:
   python3 demo_mavlink.py --replay path/to/flight.tlog
"""

import sys
import time
import hashlib
import json

from dronesync.mavlink_adapter import MAVLinkAdapter, SITLReplay
from dronesync.pipeline import MissionPipeline
from dronesync.protocol import MissionInstruction, MissionType, Waypoint


def run_live(connection: str = "udp:127.0.0.1:14550", duration: int = 30):
    print(f"\n{'='*60}")
    print("DroneSync — Real MAVLink Telemetry → PoPW")
    print(f"{'='*60}")
    print(f"Connecting to: {connection}")

    adapter = MAVLinkAdapter(connection)
    if not adapter.connect():
        print("ERROR: Could not connect. Is PX4 SITL running?")
        sys.exit(1)

    print(f"Connected! Recording {duration}s of telemetry...")
    trajectory, sensor_data = adapter.record_mission(duration_seconds=duration)
    adapter.disconnect()

    _generate_popw(trajectory, sensor_data, source="live_mavlink")


def run_replay(log_path: str):
    print(f"\n{'='*60}")
    print("DroneSync — MAVLink Log Replay → PoPW")
    print(f"{'='*60}")
    print(f"Replaying: {log_path}")

    replay = SITLReplay(log_path)
    trajectory, sensor_data = replay.to_trajectory_and_sensor()

    _generate_popw(trajectory, sensor_data, source=f"replay:{log_path}")


def _generate_popw(trajectory, sensor_data, source: str):
    print(f"\n--- Telemetry Summary ---")
    print(f"  Frames:       {trajectory.metadata.get('frame_count', len(trajectory.positions))}")
    print(f"  Duration:     {trajectory.metadata.get('duration_s', 0):.1f}s")
    print(f"  Max altitude: {trajectory.metadata.get('max_altitude', 0):.1f}m")
    print(f"  Max speed:    {trajectory.metadata.get('max_speed', 0):.2f}m/s")
    print(f"  Avg battery:  {trajectory.metadata.get('avg_battery', 0):.0f}%")

    if not trajectory.positions:
        print("\nERROR: No GPS positions recorded.")
        return

    first = trajectory.positions[0]
    last = trajectory.positions[-1]

    mission = MissionInstruction(
        mission_id=f"mavlink_{int(time.time())}",
        mission_type=MissionType.URBAN_DELIVERY,
        origin=Waypoint(lat=first[0], lon=first[1], alt=first[2]),
        destination=Waypoint(lat=last[0], lon=last[1], alt=last[2]),
        payload_kg=0.5,
    )

    print(f"\n--- Mission ---")
    print(f"  ID:     {mission.mission_id}")
    print(f"  Origin: {first[0]:.6f}, {first[1]:.6f} @ {first[2]:.1f}m")
    print(f"  Dest:   {last[0]:.6f}, {last[1]:.6f} @ {last[2]:.1f}m")

    # Calculate score from real MAVLink telemetry
    frames = len(trajectory.positions)
    max_alt = max(p[2] for p in trajectory.positions) if trajectory.positions else 0
    max_speed = trajectory.max_speed if hasattr(trajectory, "max_speed") else 0
    duration = trajectory.duration if hasattr(trajectory, "duration") else 0
    score = 0.0
    if frames >= 50: score += 30
    if max_alt >= 10: score += 30
    if max_speed >= 1.0: score += 20
    if duration >= 20: score += 20
    pipeline = MissionPipeline()
    result = pipeline.run(mission, trajectory=trajectory, sensor_data=sensor_data, score=score)
    score = max(score, result.get("score", 0))
    popw = result.get("popw", {})

    print(f"\n--- PoPW Result ---")
    print(f"  Score:            {score:.1f}/100")
    print(f"  Computation hash: {popw.get('computation_hash', 'N/A')[:32]}...")
    print(f"  Simulation steps: {popw.get('simulation_steps', 'N/A')}")
    print(f"  Energy estimate:  {popw.get('energy_estimate', 'N/A')}")
    print(f"  Constraints OK:   {popw.get('constraints_satisfied', 'N/A')}")
    print(f"  Source:           {source}")

    traj_bytes = json.dumps(trajectory.positions, sort_keys=True).encode()
    traj_hash = hashlib.sha256(traj_bytes).hexdigest()
    print(f"  Trajectory hash:  {traj_hash[:32]}...")

    if score >= 60:
        print(f"\n✅ MISSION TRUSTED — Real PoPW ready for on-chain submission")
    else:
        print(f"\n⚠️  Score too low ({score:.1f}) — mission not trusted")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    if "--replay" in sys.argv:
        idx = sys.argv.index("--replay")
        if idx + 1 < len(sys.argv):
            run_replay(sys.argv[idx + 1])
        else:
            print("Usage: python3 demo_mavlink.py --replay path/to/flight.tlog")
    else:
        connection = sys.argv[1] if len(sys.argv) > 1 else "udp:127.0.0.1:14550"
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        run_live(connection, duration)
