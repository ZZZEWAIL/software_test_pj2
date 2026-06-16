"""
path_power_schedule.py 单元测试

覆盖 PathPowerSchedule 的能量分配逻辑：energy = 1 / path_frequency
"""
import unittest
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from schedule.path_power_schedule import PathPowerSchedule
from utils.seed import Seed
from utils.coverage import Location


class TestPathPowerSchedule(unittest.TestCase):
    """测试 PathPowerSchedule — 基于路径频率的能量分配"""

    def setUp(self):
        self.schedule = PathPowerSchedule()

    # ========== 基础功能测试 ==========

    def test_assign_energy_single_seed(self):
        """单个 seed，路径未出现过时 energy = 1.0"""
        seed = Seed("data", {("func", 1), ("func", 2)})
        self.schedule.assign_energy([seed])
        self.assertEqual(seed.energy, 1.0)

    def test_assign_energy_two_seeds_same_path(self):
        """两个 seed 同路径：第一个 energy=1.0，第二个 energy=0.5"""
        s1 = Seed("d1", {("f", 1)})
        s2 = Seed("d2", {("f", 1)})

        # 模拟 fuzzer 先注册路径再分配能量
        path_id = frozenset({("f", 1)})
        self.schedule.path_frequency[path_id] = 2  # 该路径已出现2次

        self.schedule.assign_energy([s1, s2])
        self.assertEqual(s1.energy, 0.5)
        self.assertEqual(s2.energy, 0.5)

    def test_assign_energy_different_paths(self):
        """不同路径的 seed 获得不同能量"""
        s1 = Seed("d1", {("f", 1)})
        s2 = Seed("d2", {("f", 2)})

        path1 = frozenset({("f", 1)})
        path2 = frozenset({("f", 2)})
        self.schedule.path_frequency[path1] = 1
        self.schedule.path_frequency[path2] = 5

        self.schedule.assign_energy([s1, s2])
        self.assertEqual(s1.energy, 1.0)
        self.assertEqual(s2.energy, 0.2)

    def test_assign_energy_empty_population(self):
        """空种群不报错"""
        self.schedule.assign_energy([])

    def test_assign_energy_unseen_path_defaults_one(self):
        """未在 path_frequency 中出现的路径，freq 默认为 1"""
        seed = Seed("new_data", {("func", 99)})
        self.assertNotIn(frozenset({("func", 99)}), self.schedule.path_frequency)
        self.schedule.assign_energy([seed])
        self.assertEqual(seed.energy, 1.0)

    # ========== 边界条件测试 ==========

    def test_energy_decreases_with_repeated_path(self):
        """同一路径出现越多，能量越低"""
        path_id = frozenset({("f", 1)})
        energies = []
        for freq in range(1, 6):
            seed = Seed(f"d{freq}", {("f", 1)})
            self.schedule.path_frequency[path_id] = freq
            self.schedule.assign_energy([seed])
            energies.append(round(seed.energy, 4))

        self.assertEqual(energies, [1.0, 0.5, 0.3333, 0.25, 0.2])

    def test_path_id_is_frozenset(self):
        """验证路径标识计算正确（assign_energy 使用 frozenset(coverage) 作为 key）"""
        seed = Seed("d", {("a", 1), ("b", 2)})
        # 手动设置 path_frequency 来模拟 fuzzer 的行为
        path_id = frozenset(seed.coverage)
        self.schedule.path_frequency[path_id] = 3
        self.schedule.assign_energy([seed])
        self.assertIsInstance(path_id, frozenset)
        # energy = 1/3
        self.assertAlmostEqual(seed.energy, 1.0 / 3)

    def test_high_path_frequency_gives_very_low_energy(self):
        """高频路径获得极低能量"""
        path_id = frozenset({("f", 1)})
        self.schedule.path_frequency[path_id] = 10000
        seed = Seed("boring", {("f", 1)})
        self.schedule.assign_energy([seed])
        self.assertAlmostEqual(seed.energy, 0.0001)
        self.assertGreater(seed.energy, 0)

    # ========== choose 集成测试 ==========

    def test_choose_respects_energy_distribution(self):
        """统计验证：低频率路径的 seed 被选中概率更高"""
        random.seed(42)

        s_rare = Seed("rare", {("f", 1)})
        s_common = Seed("common", {("f", 2)})

        path_rare = frozenset({("f", 1)})
        path_common = frozenset({("f", 2)})
        self.schedule.path_frequency[path_rare] = 1
        self.schedule.path_frequency[path_common] = 10

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
        self.assertGreater(ratio, 5.0,
                           f"rare应该远多于common，实际ratio={ratio:.2f}")

    def test_choose_returns_seed_instance(self):
        """choose() 返回 Seed 实例"""
        seed = Seed("test", {("f", 1)})
        self.schedule.assign_energy([seed])
        chosen = self.schedule.choose([seed])
        self.assertIsInstance(chosen, Seed)
        self.assertEqual(chosen.data, "test")


if __name__ == '__main__':
    unittest.main(verbosity=2)
