"""
demo_depin.py

Demo: Full DePIN cycle
Mission → PoPW → Validator Network Consensus → Token Reward → Wallet

Run:
    python3 demo_depin.py
"""

import asyncio
import time
import threading

from dronesync.validator_node import ValidatorNode
from dronesync.validator_network import ValidatorNetwork
from dronesync.economics import RewardCalculator
from dronesync.wallet import MinerWallet


NODES = [
    {"id": "validator-kyiv",    "port": 9101},
    {"id": "validator-berlin",  "port": 9102},
    {"id": "validator-newyork", "port": 9103},
]
PEER_URIS = [f"ws://localhost:{n['port']}" for n in NODES]


def _start_node(node_id, port, peers):
    async def run():
        peers_for_node = [u for u in peers if str(port) not in u]
        node = ValidatorNode(node_id=node_id, host="localhost",
                             port=port, peers=peers_for_node)
        await node.start()
    asyncio.run(run())


async def main():
    print(f"\n{'='*60}")
    print("DroneSync — Full DePIN Cycle")
    print("Mission → PoPW → Consensus → Reward → Wallet")
    print(f"{'='*60}")

    # Start validator network
    print("\n[1] Starting validator network...")
    for n in NODES:
        t = threading.Thread(
            target=_start_node,
            args=(n["id"], n["port"], PEER_URIS),
            daemon=True,
        )
        t.start()
        print(f"    ✓ {n['id']} → ws://localhost:{n['port']}")
    await asyncio.sleep(1.0)

    network = ValidatorNetwork(node_uris=PEER_URIS)
    calculator = RewardCalculator()
    wallet = MinerWallet(
        wallet_id="miner-001",
        persist_path="/tmp/demo_depin_wallet.json",
    )

    print(f"\n[2] Initial wallet balance: {wallet.balance} KNX")

    # Run 3 missions
    missions = [
        {"mission_id": f"mission_{int(time.time())}_1", "score": 92.0,
         "grade": "EXCELLENT", "tier": "TRUSTED", "violations": 0},
        {"mission_id": f"mission_{int(time.time())}_2", "score": 75.0,
         "grade": "GOOD",      "tier": "TRUSTED", "violations": 0},
        {"mission_id": f"mission_{int(time.time())}_3", "score": 45.0,
         "grade": "POOR",      "tier": "TRUSTED", "violations": 2},
    ]

    print(f"\n[3] Running {len(missions)} missions...\n")

    for m in missions:
        print(f"    Mission: {m['mission_id']}")
        print(f"    Score:   {m['score']}")

        # Build PoPW
        popw = {
            "mission_id": m["mission_id"],
            "score": m["score"],
            "computation_hash": "a3f9c2e1b8d7f4a6" if m["score"] >= 60 else "",
            "constraints_satisfied": m["score"] >= 60,
            "trajectory_positions": [
                [50.45, 30.52, 50.0, time.time()],
                [50.46, 30.53, 55.0, time.time() + 5],
                [50.47, 30.54, 60.0, time.time() + 10],
            ] if m["score"] >= 60 else [[50.45, 30.52, 50.0, time.time()]],
        }

        # Submit to validator network
        result = await network.submit_popw(popw)
        consensus = result.consensus

        print(f"    Consensus: {'✅ YES' if consensus else '❌ NO'} "
              f"(quorum={result.quorum:.0%}, {result.duration_ms:.0f}ms)")

        if consensus:
            # Calculate reward
            breakdown = calculator.calculate(
                mission_id=m["mission_id"],
                total_score=m["score"] / 100.0,
                grade=m["grade"],
                reputation_tier=m["tier"],
                safety_violations=m["violations"],
            )
            # Credit wallet
            tx = wallet.credit(
                mission_id=m["mission_id"],
                amount_knx=breakdown.final_reward,
                reason=f"mission_reward_grade_{m['grade'].lower()}",
            )
            print(f"    Reward:    +{breakdown.final_reward:.4f} KNX "
                  f"(streak={calculator.streak})")
            print(f"    Balance:   {wallet.balance} KNX")
        else:
            print(f"    Reward:    0 KNX (not accepted)")

        print()

    # Final summary
    print(f"[4] Final Wallet Summary:")
    s = wallet.summary()
    print(f"    Balance:         {s['balance_knx']} KNX")
    print(f"    Total earned:    {s['total_earned_knx']} KNX")
    print(f"    Total penalties: {s['total_penalties_knx']} KNX")
    print(f"    Transactions:    {s['transaction_count']}")

    print(f"\n[5] Transaction History:")
    for tx in wallet.history():
        print(f"    {tx['tx_id']} | {tx['mission_id'][-6:]} "
              f"| {tx['amount_knx']:+.4f} KNX | {tx['reason']}")

    print(f"\n{'='*60}")
    print("✅ DePIN cycle complete — rewards on-chain ready")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
