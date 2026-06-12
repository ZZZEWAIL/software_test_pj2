import unittest
import random
from simple_fuzzer.schedule.prob_weight_schedule import ProbabilityWeightedRoundRobinSchedule

import sys
import os

test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(test_dir)
sys.path.insert(0, project_root)

from simple_fuzzer.schedule.prob_weight_schedule import ProbabilityWeightedRoundRobinSchedule

class TestProbabilityWeightedRoundRobinSchedule(unittest.TestCase):
    def setUp(self):
        """每个测试用例执行前初始化调度器"""
        self.scheduler = ProbabilityWeightedRoundRobinSchedule()

    # ========== 基础功能测试 ==========
    def test_register_testcase(self):
        """测试注册用例的正常逻辑"""
        # 注册单个用例
        self.scheduler.register_testcase(1, 2.0)
        self.assertEqual(self.scheduler.testcases, [1])
        self.assertEqual(self.scheduler.testcase_weights[1], 2.0)
        self.assertEqual(self.scheduler.total_weight, 2.0)

        # 注册多个用例
        self.scheduler.register_testcase(2, 3.0)
        self.assertEqual(self.scheduler.testcases, [1, 2])
        self.assertEqual(self.scheduler.testcase_weights[2], 3.0)
        self.assertEqual(self.scheduler.total_weight, 5.0)

    def test_update_weight(self):
        """测试更新用例权重"""
        self.scheduler.register_testcase(1, 2.0)
        # 更新为更大的权重
        self.scheduler.update_weight(1, 5.0)
        self.assertEqual(self.scheduler.testcase_weights[1], 5.0)
        self.assertEqual(self.scheduler.total_weight, 5.0)

        # 更新为更小的权重（含0）
        self.scheduler.update_weight(1, 0.0)
        self.assertEqual(self.scheduler.testcase_weights[1], 0.0)
        self.assertEqual(self.scheduler.total_weight, 0.0)

        # 权重为负数时自动转为0
        self.scheduler.update_weight(1, -10.0)
        self.assertEqual(self.scheduler.testcase_weights[1], 0.0)
        self.assertEqual(self.scheduler.total_weight, 0.0)

    def test_select_next_single_case(self):
        """测试单个用例时的选择逻辑"""
        self.scheduler.register_testcase(1, 10.0)
        # 无论随机值如何，只能选中唯一用例
        selected = self.scheduler.select_next()
        self.assertEqual(selected, 1)

    def test_reset(self):
        """测试重置调度器"""
        self.scheduler.register_testcase(1, 2.0)
        self.scheduler.register_testcase(2, 3.0)
        self.scheduler.reset()

        self.assertEqual(self.scheduler.testcases, [])
        self.assertEqual(self.scheduler.testcase_weights, {})
        self.assertEqual(self.scheduler.total_weight, 0.0)

    # ========== 边界条件测试 ==========
    def test_register_duplicate_testcase(self):
        """测试重复注册用例（应抛出异常）"""
        self.scheduler.register_testcase(1, 2.0)
        with self.assertRaises(ValueError) as ctx:
            self.scheduler.register_testcase(1, 3.0)
        self.assertEqual(str(ctx.exception), "用例1已注册")

    def test_update_nonexistent_testcase(self):
        """测试更新未注册用例（应抛出异常）"""
        with self.assertRaises(ValueError) as ctx:
            self.scheduler.update_weight(999, 5.0)
        self.assertEqual(str(ctx.exception), "用例999未注册")

    def test_select_next_empty_testcases(self):
        """测试空用例列表选择（应抛出异常）"""
        with self.assertRaises(RuntimeError) as ctx:
            self.scheduler.select_next()
        self.assertEqual(str(ctx.exception), "无已注册测试用例")

    def test_select_next_total_weight_zero(self):
        """测试总权重为0时的均等概率选择"""
        # 注册两个权重为0的用例
        self.scheduler.register_testcase(1, 0.0)
        self.scheduler.register_testcase(2, 0.0)
        # 多次选择，验证两个用例都能被选中（随机均等）
        selected_ids = set()
        for _ in range(100):
            selected = self.scheduler.select_next()
            selected_ids.add(selected)
        self.assertEqual(selected_ids, {1, 2})

    # ========== 概率合理性测试（统计层面） ==========
    def test_select_next_probability_distribution(self):
        """验证选中概率与权重匹配（统计次数）"""
        # 固定随机种子，保证测试可复现
        random.seed(42)
        # 注册3个用例，权重分别为1、2、3（总权重6，概率1/6、2/6、3/6）
        self.scheduler.register_testcase(1, 1.0)
        self.scheduler.register_testcase(2, 2.0)
        self.scheduler.register_testcase(3, 3.0)

        # 执行10000次选择，统计次数
        count = {1: 0, 2: 0, 3: 0}
        total_runs = 10000
        for _ in range(total_runs):
            selected = self.scheduler.select_next()
            count[selected] += 1

        # 计算实际概率（允许±1%的误差）
        prob1 = count[1] / total_runs
        prob2 = count[2] / total_runs
        prob3 = count[3] / total_runs

        # 预期概率
        expected_prob1 = 1/6  # ≈0.1667
        expected_prob2 = 2/6  # ≈0.3333
        expected_prob3 = 3/6  # ≈0.5

        # 验证误差在1%以内
        self.assertAlmostEqual(prob1, expected_prob1, delta=0.01)
        self.assertAlmostEqual(prob2, expected_prob2, delta=0.01)
        self.assertAlmostEqual(prob3, expected_prob3, delta=0.01)

if __name__ == '__main__':
    unittest.main(verbosity=2)