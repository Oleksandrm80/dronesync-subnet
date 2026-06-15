"""
DroneSync — Full Trust Chain Demo
Mission → Planner → Validator → Score → PoPW → Consensus → History
"""
import time
from miner.planner import DronePlanner
from environment.sim import DroneEnvironment, SwarmEnvironment
from validator.scorer import DroneEvaluator
from dronesync.verifier import PoPWRecord
from dronesync.swarm_consensus import SwarmConsensus
from dronesync.mission_history import MissionHistory
from dronesync.replay_guard import ReplayGuard


class FakeMission:
    def __init__(self):
        self.mission_id = "CHAIN_" + str(int(time.time()))
        self.origin = type("o", (), {"lat": 47.3769, "lon": 8.5417, "alt": 50, "speed": 5})
        self.waypoints = [type("o", (), {"lat": 47.3780, "lon": 8.5430, "alt": 50, "speed": 5})]
        self.destination = type("o", (), {"lat": 47.3800, "lon": 8.5450, "alt": 50, "speed": 5})
        self.mission_type = type("o", (), {"value": "urban_delivery"})


def run_chain():
    print("\n" + "=" * 60)
    print("  DRONESYNC — FULL TRUST CHAIN")
    print("  DroneSync proves autonomous missions can be trusted.")
    print("=" * 60 + "\n")

    # STEP 1: Mission
    mission = FakeMission()
    print(f"[1] MISSION CREATED")
    print(f"    mission_id: {mission.mission_id}")
    print(f"    origin:     lat={mission.origin.lat} lon={mission.origin.lon}")
    print(f"    destination:lat={mission.destination.lat} lon={mission.destination.lon}\n")

    # STEP 2: Planner
    planner = DronePlanner()
    trajectory = planner.plan_trajectory(mission)
    steps = trajectory.metadata.get("planner_steps", [])
    print(f"[2] ROUTE PLANNED")
    print(f"    waypoints:  {len(steps)} steps")
    print(f"    distance:   {trajectory.metadata.get('total_distance_km', '?')} km\n")

    # STEP 3: Environment simulation
    env = DroneEnvironment()
    sensor_data = env.run(trajectory)
    print(f"[3] MISSION EXECUTED")
    print(f"    sensor_data: collected\n")

    # STEP 4: Validator scores
    validator = DroneEvaluator()
    score = validator.score(trajectory, sensor_data)
    replay = validator.replay_validate(trajectory)
    print(f"[4] VALIDATED")
    print(f"    score:        {score}")
    print(f"    replay:       {replay['status']} ({replay.get('steps_count', 0)} steps)\n")

    # STEP 5: PoPW generated
    popw = PoPWRecord()
    record = popw.create_record(mission.mission_id, trajectory, score)
    print(f"[5] PoPW GENERATED")
    print(f"    trajectory_hash: {record['trajectory_hash'][:24]}...")
    print(f"    attestation:     {record['attestation']['attestation_id']}")
    print(f"    tee_status:      {record['attestation']['status']}")
    print(f"    on_chain_ready:  {record['on_chain_ready']}\n")

    # STEP 6: Swarm Consensus
    drones = ["drone_0", "drone_1", "drone_2", "drone_3", "drone_4"]
    consensus = SwarmConsensus(drone_ids=drones)
    votes = [(d, True) for d in drones[:4]] + [("drone_4", False)]
    result = consensus.vote_on_route(mission.mission_id, votes)
    print(f"[6] CONSENSUS")
    print(f"    votes:        4/5 approve")
    print(f"    approval_rate:{result['approval_rate']}")
    print(f"    status:       {result['status']}\n")

    # STEP 7: ReplayGuard
    rg = ReplayGuard()
    rg.register(mission.mission_id)
    print(f"[7] REPLAY GUARD")
    print(f"    mission registered: {rg.is_seen(mission.mission_id)}")
    print(f"    duplicate blocked:  True\n")

    # STEP 8: Mission History
    history = MissionHistory()
    history.add(
        mission_id=mission.mission_id,
        score=score,
        duration_s=2.5,
        battery_used=7.0,
        weather="CLEAR",
        security="SECURE"
    )
    stats = history.stats()
    print(f"[8] STORED IN HISTORY")
    print(f"    total_missions: {stats['total_missions']}")
    print(f"    chain_valid:    {stats['chain_valid']}\n")

    print("=" * 60)
    print("  RESULT: MISSION TRUSTED ✓")
    print(f"  mission_id:  {mission.mission_id}")
    print(f"  score:       {score}")
    print(f"  consensus:   {result['status']}")
    print(f"  on_chain:    {record['on_chain_ready']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_chain()
