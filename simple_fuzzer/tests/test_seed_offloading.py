"""
grey_box_fuzzer 持久化/offload 机制单元测试

覆盖种子卸载、重载、中间结果持久化等关键路径
"""
import unittest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fuzzer.grey_box_fuzzer import GreyBoxFuzzer, IN_MEMORY_SEED_LIMIT
from schedule.power_schedule import PowerSchedule
from utils.seed import Seed
from utils.object_utils import load_object, get_md5_of_object


class TestSeedOffloading(unittest.TestCase):
    """测试 GreyBoxFuzzer 的种子持久化与回收机制"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.schedule = PowerSchedule()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_fuzzer(self, persist_dir=None, use_temp=True):
        """创建最小化的 GreyBoxFuzzer 实例，只用于测试持久化。

        Args:
            persist_dir: 显式持久化目录路径。
            use_temp: 当 persist_dir 未指定时，是否使用临时目录。
                      设为 False 可测试 persist_dir=None 的行为。
        """
        if persist_dir is not None:
            target = persist_dir
        elif use_temp:
            target = self.temp_dir
        else:
            target = None
        return GreyBoxFuzzer(
            seeds=["seed1"],
            schedule=self.schedule,
            is_print=False,
            persist_dir=target,
        )

    def _make_seed(self, data="test", coverage=None):
        """快捷创建 Seed"""
        if coverage is None:
            coverage = {("f", 1)}
        seed = Seed(data, coverage)
        return seed

    # ========== _try_offload_population 测试 ==========

    def test_no_offload_when_below_limit(self):
        """种群数量未超阈值时不触发卸载"""
        fuzzer = self._make_fuzzer()
        # 添加少量种子（远低于 500）
        for i in range(100):
            fuzzer.population.append(self._make_seed(f"seed{i}"))

        fuzzer._try_offload_population()

        self.assertEqual(len(fuzzer.population), 100)
        self.assertEqual(len(fuzzer._offloaded_index), 0)

    def test_offload_triggers_when_above_limit(self):
        """超过阈值时精确卸载多余种子"""
        fuzzer = self._make_fuzzer()
        excess = 10
        total = IN_MEMORY_SEED_LIMIT + excess

        for i in range(total):
            fuzzer.population.append(self._make_seed(f"seed{i}"))

        fuzzer._try_offload_population()

        # 内存中应保留正好 IN_MEMORY_SEED_LIMIT 个
        self.assertEqual(len(fuzzer.population), IN_MEMORY_SEED_LIMIT)
        # 卸载索引应有 excess 条记录
        self.assertEqual(len(fuzzer._offloaded_index), excess)

    def test_offload_keeps_high_energy_seeds(self):
        """排序后低能量种子排在前面被卸载，高能量种子保留"""
        fuzzer = self._make_fuzzer()
        # 创建 3 个种子，能量各不相同
        s_low = self._make_seed("low")
        s_low.energy = 0.1
        s_mid = self._make_seed("mid")
        s_mid.energy = 0.5
        s_high = self._make_seed("high")
        s_high.energy = 100.0
        fuzzer.population = [s_high, s_low, s_mid]  # 故意乱序

        # 直接测试排序逻辑：低能量在前
        fuzzer.population.sort(key=lambda s: s.energy)
        self.assertEqual(fuzzer.population[0].data, "low")
        self.assertEqual(fuzzer.population[1].data, "mid")
        self.assertEqual(fuzzer.population[2].data, "high")

        # 模拟卸载前 2 个（低能量）
        excess = 2
        for seed in fuzzer.population[:excess]:
            fuzzer._offload_seed(seed)
        fuzzer.population = fuzzer.population[excess:]

        # 只保留 high
        self.assertEqual(len(fuzzer.population), 1)
        self.assertEqual(fuzzer.population[0].data, "high")
        self.assertEqual(fuzzer.population[0].energy, 100.0)
        self.assertEqual(len(fuzzer._offloaded_index), 2)

    def test_offloaded_seed_written_to_disk(self):
        """卸载后磁盘上存在对应的 pickle 文件"""
        fuzzer = self._make_fuzzer()
        seed = self._make_seed("disk_test")
        fuzzer.population = [seed]
        fuzzer.population[0].energy = 0.0

        import fuzzer.grey_box_fuzzer as gbf
        original_limit = gbf.IN_MEMORY_SEED_LIMIT
        gbf.IN_MEMORY_SEED_LIMIT = 0

        try:
            fuzzer._try_offload_population()
            self.assertEqual(len(fuzzer._offloaded_index), 1)
            seed_id = list(fuzzer._offloaded_index.keys())[0]
            disk_path = fuzzer._offloaded_index[seed_id]
            self.assertTrue(os.path.exists(disk_path))

            # 加载回来验证数据完整性
            loaded = load_object(disk_path)
            self.assertIsInstance(loaded, Seed)
            self.assertEqual(loaded.data, "disk_test")
        finally:
            gbf.IN_MEMORY_SEED_LIMIT = original_limit

    # ========== _reload_offloaded_seeds 测试 ==========

    def test_reload_restores_offloaded_seeds(self):
        """重载将磁盘上的种子恢复到内存"""
        fuzzer = self._make_fuzzer()

        # 创建并卸载 3 个种子
        seeds = [self._make_seed(f"reload{i}") for i in range(3)]
        fuzzer.population = seeds
        for s in fuzzer.population:
            s.energy = 0.0

        import fuzzer.grey_box_fuzzer as gbf
        original_limit = gbf.IN_MEMORY_SEED_LIMIT
        gbf.IN_MEMORY_SEED_LIMIT = 0

        try:
            fuzzer._try_offload_population()
            self.assertEqual(len(fuzzer.population), 0)
            self.assertEqual(len(fuzzer._offloaded_index), 3)
        finally:
            gbf.IN_MEMORY_SEED_LIMIT = original_limit

        # 恢复 limit 后再重载（_reload_offloaded_seeds 内部会再次调用
        # _try_offload_population，需要正常阈值才不会立即又卸载掉）
        fuzzer._reload_offloaded_seeds()
        self.assertEqual(len(fuzzer.population), 3)
        reloaded_data = {s.data for s in fuzzer.population}
        self.assertEqual(reloaded_data, {"reload0", "reload1", "reload2"})

    def test_reload_handles_missing_file(self):
        """磁盘文件丢失时，从索引中移除对应条目"""
        fuzzer = self._make_fuzzer()

        seed = self._make_seed("will_disappear")
        fuzzer.population = [seed]
        fuzzer.population[0].energy = 0.0

        import fuzzer.grey_box_fuzzer as gbf
        original_limit = gbf.IN_MEMORY_SEED_LIMIT
        gbf.IN_MEMORY_SEED_LIMIT = 0

        try:
            fuzzer._try_offload_population()
            self.assertEqual(len(fuzzer._offloaded_index), 1)
            seed_id = list(fuzzer._offloaded_index.keys())[0]

            # 手动删除磁盘文件
            os.remove(fuzzer._offloaded_index[seed_id])

            # 重载：应该清理掉这个失效条目
            fuzzer.population = []
            fuzzer._reload_offloaded_seeds()

            self.assertEqual(len(fuzzer._offloaded_index), 0)
            self.assertEqual(len(fuzzer.population), 0)
        finally:
            gbf.IN_MEMORY_SEED_LIMIT = original_limit

    def test_offload_reload_preserves_coverage(self):
        """卸载-重载循环后种子覆盖率保持不变"""
        fuzzer = self._make_fuzzer()
        coverage = {("f", 1), ("f", 2), ("f", 3)}
        seed = self._make_seed("preserve_me", coverage)
        fuzzer.population = [seed]
        fuzzer.population[0].energy = 0.0

        import fuzzer.grey_box_fuzzer as gbf
        original_limit = gbf.IN_MEMORY_SEED_LIMIT
        gbf.IN_MEMORY_SEED_LIMIT = 0

        try:
            fuzzer._try_offload_population()
        finally:
            gbf.IN_MEMORY_SEED_LIMIT = original_limit

        # 恢复 limit 后重载
        fuzzer.population = []
        fuzzer._reload_offloaded_seeds()

        self.assertEqual(len(fuzzer.population), 1)
        reloaded = fuzzer.population[0]
        self.assertEqual(reloaded.data, "preserve_me")
        self.assertEqual(reloaded.coverage, coverage)

    # ========== _persist_intermediate 测试 ==========

    def test_persist_intermediate_writes_crash_map(self):
        """中间持久化写入 crash_map 到磁盘"""
        fuzzer = self._make_fuzzer()
        fuzzer.crash_map = {"input1": "traceback1", "input2": "traceback2"}

        fuzzer._persist_intermediate()

        crash_path = os.path.join(
            fuzzer._crash_dir, "crash_map.pkl")
        self.assertTrue(os.path.exists(crash_path))
        loaded = load_object(crash_path)
        self.assertEqual(loaded, {"input1": "traceback1", "input2": "traceback2"})

    def test_persist_intermediate_empty_crash_map(self):
        """空 crash_map 时不写入文件"""
        fuzzer = self._make_fuzzer()
        fuzzer.crash_map = {}

        fuzzer._persist_intermediate()

        crash_path = os.path.join(
            fuzzer._crash_dir, "crash_map.pkl")
        self.assertFalse(os.path.exists(crash_path))

    # ========== persist_dir=None 测试 ==========

    def test_persist_dir_none_disables_offload(self):
        """persist_dir=None 时卸载方法静默返回"""
        fuzzer = self._make_fuzzer(persist_dir=None, use_temp=False)

        # 添加超量种子
        for i in range(IN_MEMORY_SEED_LIMIT + 10):
            fuzzer.population.append(self._make_seed(f"seed{i}"))

        fuzzer._try_offload_population()

        # 不应卸载任何种子
        self.assertEqual(len(fuzzer.population), IN_MEMORY_SEED_LIMIT + 10)
        self.assertEqual(len(fuzzer._offloaded_index), 0)

    def test_persist_dir_none_disables_persist_intermediate(self):
        """persist_dir=None 时 _persist_intermediate 静默返回"""
        fuzzer = self._make_fuzzer(persist_dir=None, use_temp=False)
        fuzzer.crash_map = {"inp": "trace"}

        # 不应抛异常
        fuzzer._persist_intermediate()

    def test_persist_dir_none_disables_reload(self):
        """persist_dir=None 时 _reload_offloaded_seeds 静默返回"""
        fuzzer = self._make_fuzzer(persist_dir=None, use_temp=False)
        # 不应抛异常
        fuzzer._reload_offloaded_seeds()

    # ========== assign_energy before offload 测试 ==========

    def test_assign_energy_called_before_sort_on_offload(self):
        """卸载前调用 assign_energy，防止 energy=0 的新种子被误卸载"""
        fuzzer = self._make_fuzzer()

        # 添加种子（energy 未初始化 = 0.0）
        for i in range(IN_MEMORY_SEED_LIMIT + 5):
            fuzzer.population.append(self._make_seed(f"new_seed_{i}"))

        fuzzer._try_offload_population()

        # Base PowerSchedule.assign_energy 设所有能量为 1
        # 所以所有种子能量相等，排序后卸载前 5 个
        self.assertEqual(len(fuzzer.population), IN_MEMORY_SEED_LIMIT)
        self.assertEqual(len(fuzzer._offloaded_index), 5)
        # 验证保留的种子能量都不是 0
        for seed in fuzzer.population:
            self.assertGreater(seed.energy, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
