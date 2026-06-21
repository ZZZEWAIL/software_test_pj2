import os
import time
from typing import List, Any, Tuple, Set, Optional

import random

from fuzzer.fuzzer import Fuzzer
from runner.runner import Runner
from utils.coverage import Location
from utils.mutator import Mutator
from runner.function_coverage_runner import FunctionCoverageRunner
from schedule.power_schedule import PowerSchedule
from utils.object_utils import dump_object, load_object, get_md5_of_object

from utils.seed import Seed

# 内存中保留的最大 seed 数量，超过此阈值后低能量 seed 被持久化到磁盘
IN_MEMORY_SEED_LIMIT = 500
# 每隔多少次执行进行一次中间结果持久化
PERSIST_INTERVAL = 1000
# 每隔多少次执行将被 offload 的 seed 重新加载回内存（让调度器重新见到它们）
OFFLOAD_RELOAD_INTERVAL = 5000


class GreyBoxFuzzer(Fuzzer):

    def __init__(self, seeds: List[str], schedule: PowerSchedule,
                 is_print: bool, persist_dir: Optional[str] = None) -> None:
        """构造函数。
        `seeds` — 初始种子列表。
        `schedule` — 调度策略。
        `is_print` — 是否打印统计表。
        `persist_dir` — 持久化目录，None 时禁用。
        """
        super().__init__()
        self.is_print = is_print
        self.last_crash_time = self.start_time
        self.population: List[Seed] = []
        self.file_map = {}
        self.covered_line: Set[Location] = set()
        self.seed_index = 0
        self.crash_map = dict()
        self.seeds = seeds
        self.mutator = Mutator()
        self.schedule = schedule

        # 持久化相关
        self.persist_dir = persist_dir
        self._offloaded_seeds_dir = os.path.join(persist_dir, "seeds") if persist_dir else None
        self._crash_dir = os.path.join(persist_dir, "crashes") if persist_dir else None
        # 离线 seed 索引：key = seed 的 md5, value = 磁盘文件路径
        self._offloaded_index: dict = {}
        self._persist_counter = 0
        self._offload_reload_counter = 0

        if persist_dir:
            os.makedirs(self._offloaded_seeds_dir, exist_ok=True)
            os.makedirs(self._crash_dir, exist_ok=True)

        if is_print:
            print("""
┌───────────────────────┬───────────────────────┬───────────────────┬────────────────┬───────────────────┬────────────────┐
│        Run Time       │    Last Uniq Crash    │    Total Execs    │  Uniq Crashes  │   Covered Lines   │  Offloaded Sds │
├───────────────────────┼───────────────────────┼───────────────────┼────────────────┼───────────────────┼────────────────┤""")

    def _offload_seed(self, seed: Seed) -> None:
        """将 seed 持久化到磁盘并从内存中移除"""
        if not self._offloaded_seeds_dir:
            return
        seed_id = get_md5_of_object(seed)
        path = os.path.join(self._offloaded_seeds_dir, f"{seed_id}.pkl")
        dump_object(path, seed)
        self._offloaded_index[seed_id] = path

    def _load_offloaded_seed(self, seed_id: str) -> Optional[Seed]:
        """从磁盘加载离线 seed"""
        path = self._offloaded_index.get(seed_id)
        if path and os.path.exists(path):
            return load_object(path)
        return None

    def _reload_offloaded_seeds(self) -> None:
        """将磁盘上的种子重新加载回 population。

        定期重载可避免 offload 沦为永久删除。重载后立即再次尝试
        offload，按当前能量重新淘汰低价值种子。
        """
        if not self._offloaded_index:
            return
        loaded_count = 0
        failed_ids = []
        for seed_id, path in list(self._offloaded_index.items()):
            seed = self._load_offloaded_seed(seed_id)
            if seed is not None:
                self.population.append(seed)
                loaded_count += 1
            else:
                failed_ids.append(seed_id)
        for seed_id in failed_ids:
            del self._offloaded_index[seed_id]
        # 重载后立即尝试再次 offload，让低能量 seed 再次被卸载
        self._try_offload_population()

    def _persist_intermediate(self) -> None:
        """定期持久化中间结果（crash_map 等）到磁盘，释放内存"""
        if not self.persist_dir:
            return
        # 持久化 crash_map
        if self.crash_map:
            crash_path = os.path.join(self._crash_dir, "crash_map.pkl")
            dump_object(crash_path, self.crash_map)

    def _try_offload_population(self) -> None:
        """population 超过阈值时，将低能量种子持久化到磁盘。

        先调用 assign_energy 再排序，防止刚添加的种子（energy=0）
        被误淘汰。
        """
        if not self._offloaded_seeds_dir:
            return
        if len(self.population) <= IN_MEMORY_SEED_LIMIT:
            return

        # 先让调度器为所有 seed 重新分配能量，防止新 seed（energy=0）被误卸载
        self.schedule.assign_energy(self.population)

        # 按能量排序，低能量的先离线
        self.population.sort(key=lambda s: s.energy)
        excess = len(self.population) - IN_MEMORY_SEED_LIMIT
        to_offload = self.population[:excess]

        for seed in to_offload:
            self._offload_seed(seed)

        # 只保留高能量的 seed 在内存中
        self.population = self.population[excess:]

    def create_candidate(self) -> str:
        """从 population 中选择种子，经多重变异生成新输入"""
        # 定期将 offloaded 种子重载回内存
        self._offload_reload_counter += 1
        if self._offload_reload_counter % OFFLOAD_RELOAD_INTERVAL == 0:
            self._reload_offloaded_seeds()

        seed = self.schedule.choose(self.population)

        # 多重变异叠加
        candidate = seed.data
        trials = min(len(candidate), 1 << random.randint(1, 5))
        for i in range(trials):
            candidate = self.mutator.mutate(candidate)
        return candidate

    def fuzz(self) -> str:
        """先返回所有初始种子各一次，之后通过变异生成新输入"""
        if self.seed_index < len(self.seeds):
            # 初始种子阶段
            self.inp = self.seeds[self.seed_index]
            self.seed_index += 1
        else:
            # 变异阶段
            self.inp = self.create_candidate()

        return self.inp

    def print_stats(self):
        if not self.is_print:
            return

        def format_seconds(seconds):
            hours = int(seconds) // 3600
            minutes = int(seconds % 3600) // 60
            remaining_seconds = int(seconds) % 60
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"

        template = """│{runtime}│{crash_time}│{total_exec}│{uniq_crash}│{covered_line}│{offloaded}│
├───────────────────────┼───────────────────────┼───────────────────┼────────────────┼───────────────────┼────────────────┤"""

        template = template.format(runtime=format_seconds(time.time() - self.start_time).center(23),
                                   crash_time=format_seconds(self.last_crash_time - self.start_time).center(23),
                                   total_exec=str(self.total_execs).center(19),
                                   uniq_crash=str(len(set(self.crash_map.values()))).center(16),
                                   covered_line=str(len(self.covered_line)).center(19),
                                   offloaded=str(len(self._offloaded_index)).center(16))
        print(template)

    def run(self, runner: FunctionCoverageRunner) -> Tuple[Any, str]:  # type: ignore
        """执行被测函数并追踪覆盖率，发现新覆盖时保存种子"""
        result, outcome = super().run(runner)
        # 用集合差集判断是否为新覆盖（修复 Bug 3）
        new_coverage = runner.all_coverage - self.covered_line
        if new_coverage:
            self.covered_line |= new_coverage
            # 保存种子——崩溃但发现新代码路径的种子同样有价值
            seed = Seed(self.inp, runner.coverage())
            self.population.append(seed)
        if outcome == Runner.FAIL:
            self.last_crash_time = time.time()
            self.crash_map[self.inp] = result

        # 定期持久化中间结果并尝试离线低能量 seed
        self._persist_counter += 1
        if self._persist_counter % PERSIST_INTERVAL == 0:
            self._persist_intermediate()
            self._try_offload_population()

        return result, outcome
