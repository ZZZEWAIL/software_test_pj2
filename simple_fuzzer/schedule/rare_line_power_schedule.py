from typing import Dict, Sequence, Set

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed
from utils.coverage import Location


class RareLinePowerSchedule(PowerSchedule):
    """基于罕见代码行的调度策略。

    每行代码的罕见度 = 1 / 该行被触发次数，
    种子的能量 = 其覆盖的所有行的罕见度之和。
    """

    def __init__(self) -> None:
        super().__init__()
        # 全局行频率表：key = Location, value = 触发次数
        self.line_frequency: Dict[Location, int] = {}

    def update_line_frequency(self, coverage: Set[Location]) -> None:
        """更新全局行频率（由 Fuzzer 在每次运行后调用）"""
        for loc in coverage:
            self.line_frequency[loc] = self.line_frequency.get(loc, 0) + 1

    def assign_energy(self, population: Sequence[Seed]) -> None:
        """为每个种子按罕见行分配能量"""
        for seed in population:
            energy = 0.0
            for loc in seed.coverage:
                freq = self.line_frequency.get(loc, 1)
                energy += 1.0 / freq
            # 保证最低能量，避免归一化时除零
            seed.energy = max(energy, 1e-6)
