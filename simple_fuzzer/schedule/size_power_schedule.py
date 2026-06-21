from typing import Sequence

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class SizeBasedPowerSchedule(PowerSchedule):
    """基于输入长度的调度策略。

    短输入执行更快、干扰更少，更容易暴露核心逻辑的漏洞。
    能量 = 1 / len(seed.data)，输入越短能量越高。
    """

    # 空字符串的最大能量（避免除零）
    MAX_ENERGY_FOR_EMPTY = 1000.0

    def assign_energy(self, population: Sequence[Seed]) -> None:
        """按输入长度分配能量：越短能量越高"""
        for seed in population:
            length = len(seed.data)
            if length == 0:
                seed.energy = self.MAX_ENERGY_FOR_EMPTY
            else:
                seed.energy = 1.0 / length
