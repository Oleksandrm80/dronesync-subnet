"""
demo_validator_network.py

Demo: 3 validator nodes reach consensus on a PoPW mission.

Run:
    python3 demo_validator_network.py
"""

import asyncio
import time
import threading
import logging

from dronesync.validator_node import ValidatorNode
from dronesync.validator_network import ValidatorNetwork

logging.basicConfig(level=logging.WARNING)


NODES = [
    {"id": "validator-kyiv",    "port": 9001},
    {"id": "validator-berlin",  "port": 9002},
    {"id": "validator-newyork", "port": 9003},
]

PEER_URIS = [f"ws://localhost:{n['port']}" for n in NODES]


def _start_node(node_id: str, port: int, peers: list):
    async def run():
        peers_for_node = [uri for uri in peers if str(port) not in uri]
        node = ValidatorNode(node_id=node_id, host="localhost",
                             port=port, peers=peers_for_node)
        await node.start()
    asyncio.run(run())


async def main():
    print(f"\n{'='*60}")
    print("DroneSync — Decentralized Validator Network")
    print(f"{'='*60}")

    # Start 3 validator nodes in background threads
    print("\n[1] Starting validator nodes...")
    threads = []
    for n in NODES:
        t = threading.Thread(
            target=_start_node,
            args=(n["id"], n["port"], PEER_URIS),
            daemon=True,
        )
        t.start()
        threads.append(t)
        print(f"    ✓ {n['id']} → ws://localhost:{n['port']}")

    # Wait for nodes to start
    await asyncio.sleep(1.0)

    # Check network status
    network = ValidatorNetwork(node_uris=PEER_URIS)
    status = await network.get_network_status()
    online = sum(1 for v in status.values() if v)
    print(f"\n[2] Network status: {online}/{len(NODES)} nodes online")
    for uri, ok in status.items():
        print(f"    {'✓' if ok else '✗'} {uri}")

    # Submit a PoPW to the network
    print(f"\n[3] Submitting PoPW to network...")

    popw = {
        "mission_id": f"mission_{int(time.time())}",
        "score": 87.5,
        "computation_hash": "a3f9c2e1b8d7f4a6c0e3b1d9f2a5c8e0",
        "constraints_satisfied": True,
        "trajectory_positions": [
            [50.4501, 30.5234, 50.0, time.time()],
            [50.4510, 30.5240, 55.0, time.time() + 5],
            [50.4520, 30.5250, 60.0, time.time() + 10],
        ],
        "energy_estimate": 12.4,
        "simulation_steps": 150,
    }

    print(f"    Mission ID: {popw['mission_id']}")
    print(f"    Score:      {popw['score']}")

    result = await network.submit_popw(popw)

    print(f"\n[4] Consensus Result:")
    print(f"    Votes received:  {result.to_dict()['votes_total']}/{len(NODES)}")
    print(f"    Votes accepted:  {result.to_dict()['votes_accepted']}")
    print(f"    Quorum:          {result.quorum:.0%}")
    print(f"    Avg score:       {result.avg_score:.1f}")
    print(f"    Duration:        {result.duration_ms:.0f}ms")

    if result.consensus:
        print(f"\n✅ CONSENSUS REACHED — Mission accepted by network")
    else:
        print(f"\n❌ NO CONSENSUS — Mission rejected")

    # Test with bad PoPW
    print(f"\n[5] Testing with low-score PoPW...")
    bad_popw = {
        "mission_id": f"bad_mission_{int(time.time())}",
        "score": 30.0,
        "computation_hash": "abc123",
        "constraints_satisfied": False,
        "trajectory_positions": [[50.0, 30.0, 10.0, time.time()]],
        "energy_estimate": 0,
        "simulation_steps": 0,
    }

    bad_result = await network.submit_popw(bad_popw)
    if not bad_result.consensus:
        print(f"    ✅ Bad PoPW correctly rejected (quorum={bad_result.quorum:.0%})")
    else:
        print(f"    ❌ Bad PoPW incorrectly accepted")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
