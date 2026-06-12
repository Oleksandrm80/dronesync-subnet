"""Tests for DroneSync Economic Reward Model."""

import pytest
from dronesync.economics import RewardCalculator, EconomicSimulator, TIER_MULTIPLIERS


class TestRewardCalculator:
    def test_excellent_score_gives_high_reward(self):
        calc = RewardCalculator()
        r = calc.calculate("m1", total_score=0.95, grade="EXCELLENT")
        assert r.final_reward > 1.5

    def test_poor_score_gives_low_reward(self):
        calc = RewardCalculator()
        r = calc.calculate("m1", total_score=0.30, grade="POOR")
        assert r.final_reward < 1.0

    def test_elite_tier_doubles_reward(self):
        calc_active = RewardCalculator()
        calc_elite = RewardCalculator()
        r_a = calc_active.calculate("m1", 0.80, "GOOD", reputation_tier="ACTIVE")
        r_e = calc_elite.calculate("m1", 0.80, "GOOD", reputation_tier="ELITE")
        assert r_e.final_reward == pytest.approx(r_a.final_reward * 2.0, abs=0.05)

    def test_safety_violations_reduce_reward(self):
        calc = RewardCalculator()
        r_clean = calc.calculate("m1", 0.80, "GOOD", safety_violations=0)
        calc2 = RewardCalculator()
        r_viol = calc2.calculate("m1", 0.80, "GOOD", safety_violations=5)
        assert r_viol.final_reward < r_clean.final_reward

    def test_streak_builds_on_good_missions(self):
        calc = RewardCalculator()
        calc.calculate("m1", 0.90, "EXCELLENT")
        calc.calculate("m2", 0.88, "GOOD")
        assert calc.streak == 2

    def test_streak_resets_on_poor(self):
        calc = RewardCalculator()
        calc.calculate("m1", 0.90, "EXCELLENT")
        calc.calculate("m2", 0.40, "POOR")
        assert calc.streak == 0

    def test_streak_bonus_increases_reward(self):
        calc = RewardCalculator()
        for i in range(5):
            calc.calculate(f"m{i}", 0.90, "EXCELLENT")
        r_with_streak = calc.calculate("m5", 0.90, "EXCELLENT")
        calc2 = RewardCalculator()
        r_no_streak = calc2.calculate("m0", 0.90, "EXCELLENT")
        assert r_with_streak.final_reward > r_no_streak.final_reward

    def test_max_penalty_capped(self):
        calc = RewardCalculator()
        r = calc.calculate("m1", 0.80, "GOOD", safety_violations=100)
        assert r.penalty <= 0.5

    def test_final_reward_never_negative(self):
        calc = RewardCalculator()
        r = calc.calculate("m1", 0.0, "POOR", safety_violations=100)
        assert r.final_reward >= 0.0

    def test_summary_counts_missions(self):
        calc = RewardCalculator()
        for i in range(5):
            calc.calculate(f"m{i}", 0.80, "GOOD")
        s = calc.summary()
        assert s["mission_count"] == 5

    def test_total_earned_accumulates(self):
        calc = RewardCalculator()
        calc.calculate("m1", 0.80, "GOOD")
        calc.calculate("m2", 0.80, "GOOD")
        assert calc.total_earned > 0


class TestEconomicSimulator:
    def _missions(self, n=5, score=0.85, grade="GOOD"):
        return [
            {"mission_id": f"m{i}", "total_score": score, "grade": grade}
            for i in range(n)
        ]

    def test_simulation_returns_all_missions(self):
        sim = EconomicSimulator()
        result = sim.simulate(self._missions(5))
        assert len(result["missions"]) == 5

    def test_elite_earns_more_than_rookie(self):
        sim = EconomicSimulator()
        elite = sim.simulate(self._missions(10), reputation_tier="ELITE")
        rookie = sim.simulate(self._missions(10), reputation_tier="ROOKIE")
        assert elite["total_earned_knx"] > rookie["total_earned_knx"]

    def test_avg_reward_makes_sense(self):
        sim = EconomicSimulator()
        result = sim.simulate(self._missions(4, score=0.90, grade="EXCELLENT"))
        assert result["avg_reward_knx"] > 0
        assert result["avg_reward_knx"] == pytest.approx(
            result["total_earned_knx"] / 4, abs=0.001
        )
