"""
DroneSync -- Economic Reward Model
Calculates KNX token rewards for miners based on mission performance.
"""

from dataclasses import dataclass
from typing import List


TIER_MULTIPLIERS = {
    "ELITE":   2.0,
    "TRUSTED": 1.5,
    "ACTIVE":  1.0,
    "ROOKIE":  0.5,
}

BASE_REWARD_KNX = 1.0
PENALTY_PER_VIOLATION = 0.05
MAX_PENALTY = 0.5
STREAK_BONUS_PER_MISSION = 0.02
MAX_STREAK_BONUS = 0.20


@dataclass
class RewardBreakdown:
    mission_id: str
    base_reward: float
    score_multiplier: float
    tier_multiplier: float
    streak_bonus: float
    penalty: float
    final_reward: float
    grade: str

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "base_reward_knx": round(self.base_reward, 4),
            "score_multiplier": round(self.score_multiplier, 3),
            "tier_multiplier": round(self.tier_multiplier, 3),
            "streak_bonus": round(self.streak_bonus, 4),
            "penalty": round(self.penalty, 4),
            "final_reward_knx": round(self.final_reward, 4),
            "grade": self.grade,
        }


class RewardCalculator:
    """
    Calculates miner KNX rewards for completed missions.
    final = (base * score_mult * tier_mult + streak_bonus) - penalty
    """

    def __init__(self):
        self._streak: int = 0
        self._total_earned: float = 0.0
        self._mission_count: int = 0

    @property
    def streak(self) -> int:
        return self._streak

    @property
    def total_earned(self) -> float:
        return round(self._total_earned, 4)

    @property
    def mission_count(self) -> int:
        return self._mission_count

    def calculate(
        self,
        mission_id: str,
        total_score: float,
        grade: str,
        reputation_tier: str = "ACTIVE",
        safety_violations: int = 0,
        base_reward: float = BASE_REWARD_KNX,
    ) -> RewardBreakdown:

        score_mult = self._score_multiplier(total_score)
        tier_mult = TIER_MULTIPLIERS.get(reputation_tier.upper(), 1.0)
        penalty = min(MAX_PENALTY, max(0, safety_violations) * PENALTY_PER_VIOLATION)

        # Вычисляем grade из реального счёта — не доверяем внешнему параметру
        if total_score >= 0.85:
            derived_grade = "EXCELLENT"
        elif total_score >= 0.70:
            derived_grade = "GOOD"
        else:
            derived_grade = "POOR"

        if derived_grade in ("EXCELLENT", "GOOD"):
            self._streak += 1
        else:
            self._streak = 0

        streak_bonus = min(MAX_STREAK_BONUS, self._streak * STREAK_BONUS_PER_MISSION)
        final = max(0.0, base_reward * score_mult * tier_mult + streak_bonus - penalty)

        self._total_earned += final
        self._mission_count += 1

        return RewardBreakdown(
            mission_id=mission_id,
            base_reward=base_reward,
            score_multiplier=score_mult,
            tier_multiplier=tier_mult,
            streak_bonus=streak_bonus,
            penalty=penalty,
            final_reward=final,
            grade=grade,
        )

    def summary(self) -> dict:
        return {
            "mission_count": self._mission_count,
            "current_streak": self._streak,
            "total_earned_knx": self.total_earned,
            "avg_reward_knx": round(self.total_earned / max(1, self._mission_count), 4),
        }

    def _score_multiplier(self, score: float) -> float:
        clamped = max(0.0, min(1.0, score))
        return round(0.5 + clamped * 1.5, 3)


class EconomicSimulator:
    """Simulates cumulative earnings over a batch of missions."""

    def simulate(
        self,
        missions: List[dict],
        reputation_tier: str = "ACTIVE",
    ) -> dict:
        calc = RewardCalculator()
        results = []
        for m in missions:
            breakdown = calc.calculate(
                mission_id=m["mission_id"],
                total_score=m["total_score"],
                grade=m["grade"],
                reputation_tier=reputation_tier,
                safety_violations=m.get("safety_violations", 0),
            )
            results.append(breakdown.to_dict())

        summary = calc.summary()
        summary["tier"] = reputation_tier
        summary["missions"] = results
        return summary
