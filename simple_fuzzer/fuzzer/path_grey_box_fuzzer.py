import os
import time
from typing import List, Tuple, Any, Optional

from fuzzer.grey_box_fuzzer import GreyBoxFuzzer, PERSIST_INTERVAL
from schedule.path_power_schedule import PathPowerSchedule
from schedule.rare_line_power_schedule import RareLinePowerSchedule
from runner.function_coverage_runner import FunctionCoverageRunner
from utils.object_utils import dump_object, load_object


class PathGreyBoxFuzzer(GreyBoxFuzzer):
    """统计路径/行触发频率，支持 PathPowerSchedule 和 RareLinePowerSchedule"""

    def __init__(self, seeds: List[str], schedule,
                 is_print: bool, persist_dir: Optional[str] = None):
        super().__init__(seeds, schedule, False, persist_dir)

        self.is_print = is_print
        self.last_new_path_time = self.start_time
        self.total_paths = 0
        # 用于 RareLinePowerSchedule 的路径去重集合
        self._seen_paths: set = set()

        # path_frequency 持久化目录
        self._path_freq_dir = os.path.join(persist_dir, "path_frequency") if persist_dir else None
        if self._path_freq_dir:
            os.makedirs(self._path_freq_dir, exist_ok=True)

        if self.is_print:
            print("""
┌───────────────────────┬───────────────────────┬───────────────────────┬───────────────────┬───────────────────┬────────────────┬───────────────────┬────────────────┐
│        Run Time       │     Last New Path     │    Last Uniq Crash    │    Total Execs    │    Total Paths    │  Uniq Crashes  │   Covered Lines   │  Offloaded Sds │
├───────────────────────┼───────────────────────┼───────────────────────┼───────────────────┼───────────────────┼────────────────┼───────────────────┼────────────────┤""")

    def print_stats(self):
        if not self.is_print:
            return

        def format_seconds(seconds):
            hours = int(seconds) // 3600
            minutes = int(seconds % 3600) // 60
            remaining_seconds = int(seconds) % 60
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"

        template = """│{runtime}│{path_time}│{crash_time}│{total_exec}│{total_path}│{uniq_crash}│{covered_line}│{offloaded}│
├───────────────────────┼───────────────────────┼───────────────────────┼───────────────────┼───────────────────┼────────────────┼───────────────────┼────────────────┤"""
        template = template.format(runtime=format_seconds(time.time() - self.start_time).center(23),
                                   path_time=format_seconds(self.last_new_path_time - self.start_time).center(23),
                                   crash_time=format_seconds(self.last_crash_time - self.start_time).center(23),
                                   total_exec=str(self.total_execs).center(19),
                                   total_path=str(self.total_paths).center(19),
                                   uniq_crash=str(len(set(self.crash_map.values()))).center(16),
                                   covered_line=str(len(self.covered_line)).center(19),
                                   offloaded=str(len(self._offloaded_index)).center(16))
        print(template)

    def _persist_path_frequency(self) -> None:
        """将调度器的频率数据持久化到磁盘"""
        if not self._path_freq_dir:
            return
        if isinstance(self.schedule, PathPowerSchedule) and self.schedule.path_frequency:
            path_freq_path = os.path.join(self._path_freq_dir, "path_frequency.pkl")
            dump_object(path_freq_path, self.schedule.path_frequency)
        elif isinstance(self.schedule, RareLinePowerSchedule) and self.schedule.line_frequency:
            line_freq_path = os.path.join(self._path_freq_dir, "line_frequency.pkl")
            dump_object(line_freq_path, self.schedule.line_frequency)

    def run(self, runner: FunctionCoverageRunner) -> Tuple[Any, str]:  # type: ignore
        """更新路径/行频率数据"""
        result, outcome = super().run(runner)

        coverage = runner.coverage()

        # 根据调度器类型更新频率数据
        if isinstance(self.schedule, PathPowerSchedule):
            path_id = frozenset(coverage)
            if path_id not in self.schedule.path_frequency:
                self.schedule.path_frequency[path_id] = 0
                self.last_new_path_time = time.time()
                self.total_paths += 1
            self.schedule.path_frequency[path_id] += 1

        elif isinstance(self.schedule, RareLinePowerSchedule):
            self.schedule.update_line_frequency(coverage)
            # 对 RareLine 调度，用覆盖行集合作为"路径"标识来统计新路径
            path_id = frozenset(coverage)
            if path_id not in self._seen_paths:
                self._seen_paths.add(path_id)
                self.last_new_path_time = time.time()
                self.total_paths += 1

        # 定期持久化频率数据（与父类持久化同步）
        if self._persist_counter % PERSIST_INTERVAL == 0:
            self._persist_path_frequency()

        return result, outcome
