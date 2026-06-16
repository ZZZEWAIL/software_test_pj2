from typing import Sequence

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class SizeBasedPowerSchedule(PowerSchedule):
    """基于输入长度的调度策略。

    偏爱较短的输入：短输入执行更快，且更容易暴露出核心逻辑的漏洞
    而不被繁杂的脏数据干扰。能量 = 1 / len(seed.data)，输入越短能量越高。
    """

    # 空字符串的最大能量（避免除零）
    MAX_ENERGY_FOR_EMPTY = 1000.0

    def assign_energy(self, population: Sequence[Seed]) -> None:
        """根据输入长度分配能量：长度越短，能量越高

        能量 = 1 / len(seed.data)
        空字符串获得最大能量 MAX_ENERGY_FOR_EMPTY
        """
        for seed in population:
            length = len(seed.data)
            if length == 0:
                seed.energy = self.MAX_ENERGY_FOR_EMPTY
            else:
                seed.energy = 1.0 / length
