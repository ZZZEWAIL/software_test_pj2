"""
size_power_schedule.py 单元测试

覆盖 SizeBasedPowerSchedule 的能量分配逻辑：
energy = 1 / len(seed.data)，输入越短能量越高
"""
import unittest
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from schedule.size_power_schedule import SizeBasedPowerSchedule
from utils.seed import Seed


class TestSizeBasedPowerSchedule(unittest.TestCase):
    """测试 SizeBasedPowerSchedule — 基于输入长度的能量分配"""

    def setUp(self):
        self.schedule = SizeBasedPowerSchedule()

    # ========== 基础功能测试 ==========

    def test_assign_energy_single_seed(self):
        """长度为 5 的种子，energy = 1/5 = 0.2"""
        seed = Seed("hello", {("f", 1)})
        self.schedule.assign_energy([seed])
        self.assertEqual(seed.energy, 0.2)

    def test_assign_energy_shorter_gets_higher_energy(self):
        """较短输入获得更高能量"""
        s_short = Seed("ab", {("f", 1)})
        s_long = Seed("abcdefghij", {("f", 2)})

        self.schedule.assign_energy([s_short, s_long])
        self.assertEqual(s_short.energy, 0.5)    # 1/2
        self.assertEqual(s_long.energy, 0.1)     # 1/10
        self.assertGreater(s_short.energy, s_long.energy)

    def test_assign_energy_multiple_seeds(self):
        """多个不同长度的种子"""
        s1 = Seed("x", set())         # len=1 → 1.0
        s2 = Seed("abc", set())       # len=3 → 0.333...
        s3 = Seed("abcdefgh", set())  # len=8 → 0.125

        self.schedule.assign_energy([s1, s2, s3])
        self.assertAlmostEqual(s1.energy, 1.0)
        self.assertAlmostEqual(s2.energy, 1.0 / 3)
        self.assertAlmostEqual(s3.energy, 0.125)

    def test_assign_energy_empty_population(self):
        """空种群不报错"""
        self.schedule.assign_energy([])

    # ========== 边界条件测试 ==========

    def test_empty_string_gets_max_energy(self):
        """空字符串获得最大能量，避免除零"""
        seed = Seed("", {("f", 1)})
        self.schedule.assign_energy([seed])
        self.assertEqual(seed.energy, SizeBasedPowerSchedule.MAX_ENERGY_FOR_EMPTY)
        self.assertGreater(seed.energy, 1.0)

    def test_single_character_gets_energy_one(self):
        """单字符输入 energy = 1.0"""
        seed = Seed("x", set())
        self.schedule.assign_energy([seed])
        self.assertEqual(seed.energy, 1.0)

    def test_very_long_input_gets_very_low_energy(self):
        """极长输入获得极低能量"""
        seed = Seed("x" * 10000, set())
        self.schedule.assign_energy([seed])
        self.assertAlmostEqual(seed.energy, 0.0001)
        self.assertGreater(seed.energy, 0)

    def test_energy_is_always_positive(self):
        """能量始终为正（不会为零或负）"""
        for length in [0, 1, 5, 100, 1000]:
            seed = Seed("x" * length, set())
            self.schedule.assign_energy([seed])
            self.assertGreater(seed.energy, 0,
                               f"length={length} should have positive energy")

    def test_same_length_seeds_get_same_energy(self):
        """相同长度的种子获得相同能量"""
        s1 = Seed("abc", set())
        s2 = Seed("xyz", set())
        self.schedule.assign_energy([s1, s2])
        self.assertEqual(s1.energy, s2.energy)
        self.assertAlmostEqual(s1.energy, 1.0 / 3)

    # ========== choose 集成测试 ==========

    def test_choose_respects_energy_distribution(self):
        """统计验证：短输入被选中的概率远高于长输入"""
        random.seed(42)

        s_short = Seed("ab", set())        # len=2 → energy=0.5
        s_long = Seed("abcdefghij", set())  # len=10 → energy=0.1

        population = [s_short, s_long]

        count = {"short": 0, "long": 0}
        total = 10000
        for _ in range(total):
            chosen = self.schedule.choose(population)
            if chosen.data == "ab":
                count["short"] += 1
            else:
                count["long"] += 1

        # short (energy 0.5) 应该被选中约 5 倍于 long (energy 0.1)
        ratio = count["short"] / max(count["long"], 1)
        self.assertGreater(ratio, 3.0,
                           f"short应该远多于long，实际ratio={ratio:.2f}")

    def test_choose_returns_seed_instance(self):
        """choose() 返回 Seed 实例"""
        seed = Seed("test", {("f", 1)})
        self.schedule.assign_energy([seed])
        chosen = self.schedule.choose([seed])
        self.assertIsInstance(chosen, Seed)
        self.assertEqual(chosen.data, "test")

    def test_choose_with_empty_seed(self):
        """包含空字符串种群的 choose 正常工作"""
        s_empty = Seed("", set())
        s_normal = Seed("hello", {("f", 1)})

        self.schedule.assign_energy([s_empty, s_normal])
        chosen = self.schedule.choose([s_empty, s_normal])
        self.assertIsInstance(chosen, Seed)
        self.assertIn(chosen.data, {"", "hello"})


if __name__ == '__main__':
    unittest.main(verbosity=2)
