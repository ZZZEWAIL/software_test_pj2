from typing import Dict, Sequence, Set

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed
from utils.coverage import Location


class RareLinePowerSchedule(PowerSchedule):
    """基于罕见代码行的调度策略。

    统计每一行代码的被触发频率，如果一个 Seed 触发了几乎没怎么被触发过的"罕见行"，
    它应该获得极高的能量。具体地，seed 的能量等于其覆盖的所有行的"罕见度"之和，
    其中某行的罕见度 = 1 / 该行被触发的总次数。
    """

    def __init__(self) -> None:
        super().__init__()
        # 全局行频率表：key = Location (函数名, 行号), value = 被触发次数
        self.line_frequency: Dict[Location, int] = {}

    def update_line_frequency(self, coverage: Set[Location]) -> None:
        """更新全局行频率表（由 Fuzzer 在每次运行后调用）"""
        for loc in coverage:
            self.line_frequency[loc] = self.line_frequency.get(loc, 0) + 1

    def assign_energy(self, population: Sequence[Seed]) -> None:
        """根据 seed 覆盖的罕见行分配能量

        每行的罕见度 = 1 / line_frequency[loc]（首次出现的行频率为1，罕见度最高）
        seed 的能量 = 其覆盖的所有行的罕见度之和
        """
        for seed in population:
            energy = 0.0
            for loc in seed.coverage:
                freq = self.line_frequency.get(loc, 1)
                energy += 1.0 / freq
            # 保证最低能量，避免归一化时除零
            seed.energy = max(energy, 1e-6)
