# DroneSync — Consensus Model

## One Line

DroneSync uses Byzantine-aware swarm consensus with QUORUM 0.67 —
a mission is approved only when at least 2/3 of drones agree.

---

## How It Works

Swarm votes on mission route
Each drone: True (approve) or False (reject)
approval_rate = approved_votes / total_votes
if approval_rate >= 0.67 then APPROVED else REJECTED

---

## Why QUORUM = 0.67?

| QUORUM | Risk |
|--------|------|
| 0.51 | 3 malicious drones out of 5 can approve any mission |
| 0.67 | Malicious nodes must exceed 33% of swarm to manipulate |
| 1.00 | One offline drone blocks all missions |

**0.67 is the optimal balance between security and availability.**

---

## Byzantine Fault Tolerance

The system remains secure while malicious participants stay below 33%.

| Scenario | Honest | Malicious | Result |
|----------|--------|-----------|--------|
| 4/5 honest | 80% | 20% | APPROVED |
| 3/5 honest | 60% | 40% | REJECTED |
| 7/10 honest | 70% | 30% | APPROVED |
| 5/10 honest | 50% | 50% | REJECTED |
| 17/50 honest | 34% | 66% | REJECTED |

---

## Network Partition

If part of the swarm goes offline, QUORUM still applies:

| Online | Vote | Result |
|--------|------|--------|
| 5/10 online, all approve | 50% | REJECTED — no quorum |
| 7/10 online, all approve | 70% | APPROVED |

This prevents split-brain: missions cannot be approved during network outages.

---

## Blacklist Voting

Drones can vote to blacklist a malicious peer:
if approval_rate >= 0.67 then drone_X blacklisted
Blacklisted drone excluded from future votes

---

## References

- [SECURITY.md](SECURITY.md) — Full threat model
- [POPW.md](POPW.md) — Proof of Physical Work specification
- [API.md](API.md) — API reference
