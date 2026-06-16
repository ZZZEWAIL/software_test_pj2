"""
rare_line_power_schedule.py 单元测试

覆盖 RareLinePowerSchedule 的能量分配逻辑：
energy = sum(1 / line_freq) for all covered lines
"""
import unittest
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from schedule.rare_line_power_schedule import RareLinePowerSchedule
from utils.seed import Seed
from utils.coverage import Location


class TestRareLinePowerSchedule(unittest.TestCase):
    """测试 RareLinePowerSchedule — 基于罕见代码行的能量分配"""

    def setUp(self):
        self.schedule = RareLinePowerSchedule()

    # ========== update_line_frequency 测试 ==========

    def test_update_line_frequency_new_line(self):
        """首次出现的行，频率为 1"""
        loc: Location = ("func", 10)
        self.schedule.update_line_frequency({loc})
        self.assertEqual(self.schedule.line_frequency[loc], 1)

    def test_update_line_frequency_repeated_line(self):
        """同一行多次出现，频率递增"""
        loc: Location = ("func", 10)
        self.schedule.update_line_frequency({loc})
        self.schedule.update_line_frequency({loc})
        self.schedule.update_line_frequency({loc})
        self.assertEqual(self.schedule.line_frequency[loc], 3)

    def test_update_line_frequency_empty_coverage(self):
        """空覆盖集不报错"""
        self.schedule.update_line_frequency(set())
        self.assertEqual(len(self.schedule.line_frequency), 0)

    def test_update_line_frequency_multiple_lines(self):
        """一次更新多行"""
        locs = {("f", 1), ("f", 2), ("f", 3)}
        self.schedule.update_line_frequency(locs)
        self.schedule.update_line_frequency(locs)
        for loc in locs:
            self.assertEqual(self.schedule.line_frequency[loc], 2)

    # ========== assign_energy 基础测试 ==========

    def test_assign_energy_single_seed_one_line(self):
        """种子覆盖 1 行，频率=1 → energy=1.0"""
        loc: Location = ("func", 1)
        self.schedule.line_frequency[loc] = 1
        seed = Seed("d", {loc})
        self.schedule.assign_energy([seed])
        self.assertEqual(seed.energy, 1.0)

    def test_assign_energy_multiple_lines(self):
        """种子覆盖 3 行，频率分别为 1, 2, 4 → energy = 1/1+1/2+1/4 = 1.75"""
        locs = {("f", 1), ("f", 2), ("f", 3)}
        # 预设频率
        self.schedule.line_frequency[("f", 1)] = 1
        self.schedule.line_frequency[("f", 2)] = 2
        self.schedule.line_frequency[("f", 3)] = 4

        seed = Seed("d", locs)
        self.schedule.assign_energy([seed])
        expected = 1.0 / 1 + 1.0 / 2 + 1.0 / 4  # = 1.75
        self.assertAlmostEqual(seed.energy, expected)

    def test_assign_energy_with_unseen_line(self):
        """未在 line_frequency 中的行，默认 freq=1"""
        loc: Location = ("f", 99)
        self.assertNotIn(loc, self.schedule.line_frequency)

        seed = Seed("d", {loc})
        self.schedule.assign_energy([seed])
        self.assertEqual(seed.energy, 1.0)

    def test_assign_energy_empty_population(self):
        """空种群不报错"""
        self.schedule.assign_energy([])

    # ========== 边界条件测试 ==========

    def test_energy_minimum_clamp(self):
        """零覆盖行时，能量不低于 1e-6（避免除零）"""
        seed = Seed("empty", set())
        self.schedule.assign_energy([seed])
        self.assertAlmostEqual(seed.energy, 1e-6)
        self.assertGreater(seed.energy, 0)

    def test_rare_line_gives_higher_contribution(self):
        """罕见行（频率低）比常见行（频率高）贡献更多能量"""
        loc_rare: Location = ("f", 1)
        loc_common: Location = ("f", 2)

        # 罕见行只出现1次，常见行出现100次
        self.schedule.line_frequency[loc_rare] = 1
        self.schedule.line_frequency[loc_common] = 100

        s_rare = Seed("rare", {loc_rare})
        s_common = Seed("common", {loc_common})

        self.schedule.assign_energy([s_rare, s_common])
        self.assertGreater(s_rare.energy, s_common.energy)
        self.assertAlmostEqual(s_rare.energy, 1.0)
        self.assertAlmostEqual(s_common.energy, 0.01)

    def test_mixed_rare_and_common_lines(self):
        """种子同时覆盖罕见行和常见行，能量为两者贡献之和"""
        loc_rare: Location = ("f", 1)
        loc_mid: Location = ("f", 2)
        loc_common: Location = ("f", 3)

        self.schedule.line_frequency[loc_rare] = 1
        self.schedule.line_frequency[loc_mid] = 5
        self.schedule.line_frequency[loc_common] = 20

        seed = Seed("mixed", {loc_rare, loc_mid, loc_common})
        self.schedule.assign_energy([seed])

        expected = 1.0 / 1 + 1.0 / 5 + 1.0 / 20  # = 1.25
        self.assertAlmostEqual(seed.energy, expected)

    def test_all_lines_same_frequency(self):
        """所有行频率相同时，能量 = 行数 × (1/freq)"""
        locs = {("f", 1), ("f", 2), ("f", 3)}
        for loc in locs:
            self.schedule.line_frequency[loc] = 10

        seed = Seed("common", locs)
        self.schedule.assign_energy([seed])
        expected = 3 * (1.0 / 10)  # = 0.3
        self.assertAlmostEqual(seed.energy, expected)

    # ========== choose 集成测试 ==========

    def test_choose_respects_energy_distribution(self):
        """统计验证：覆盖罕见行的 seed 被选中概率更高"""
        random.seed(42)

        loc_rare: Location = ("f", 1)
        loc_common: Location = ("f", 2)

        self.schedule.line_frequency[loc_rare] = 1    # energy ≈ 1.0
        self.schedule.line_frequency[loc_common] = 100  # energy ≈ 0.01

        s_rare = Seed("rare", {loc_rare})
        s_common = Seed("common", {loc_common})

        population = [s_rare, s_common]

        count = {"rare": 0, "common": 0}
        total = 10000
        for _ in range(total):
            chosen = self.schedule.choose(population)
            if chosen.data == "rare":
                count["rare"] += 1
            else:
                count["common"] += 1

        ratio = count["rare"] / max(count["common"], 1)
        self.assertGreater(ratio, 10.0,
                           f"rare应该远多于common，实际ratio={ratio:.2f}")

    def test_choose_returns_seed_with_multiple_lines(self):
        """choose 返回覆盖多行的 Seed"""
        locs = {("f", 1), ("f", 2)}
        for loc in locs:
            self.schedule.line_frequency[loc] = 1

        seed = Seed("multi", locs)
        self.schedule.assign_energy([seed])
        chosen = self.schedule.choose([seed])
        self.assertEqual(chosen.data, "multi")


if __name__ == '__main__':
    unittest.main(verbosity=2)
