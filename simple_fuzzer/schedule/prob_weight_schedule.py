import random
from typing import Dict, Sequence

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class ProbabilityWeightedRoundRobinSchedule(PowerSchedule):
    """概率加权轮询调度：按测试用例权重分配选中概率，轮询时随机选择

    继承自 PowerSchedule，通过 assign_energy 将权重映射为 seed 的能量，
    然后由 PowerSchedule.choose() 进行加权随机选择。
    """

    def __init__(self):
        super().__init__()
        self.testcase_weights: Dict[str, float] = {}  # seed.data -> 权重映射
        self.total_weight: float = 0.0  # 权重总和（计算概率用）

    def register_testcase(self, seed_data: str, initial_weight: float = 1.0):
        """注册测试用例并初始化权重
        :param seed_data: 用例数据（seed.data）
        :param initial_weight: 初始权重（默认1.0，值越高选中概率越大）
        """
        if seed_data in self.testcase_weights:
            raise ValueError(f"用例{seed_data}已注册")

        self.testcase_weights[seed_data] = initial_weight
        self.total_weight += initial_weight

    def update_weight(self, seed_data: str, new_weight: float):
        """更新测试用例权重
        :param seed_data: 用例数据
        :param new_weight: 新权重（≥0）
        """
        if seed_data not in self.testcase_weights:
            raise ValueError(f"用例{seed_data}未注册")

        self.total_weight -= self.testcase_weights[seed_data]
        self.testcase_weights[seed_data] = max(new_weight, 0.0)  # 确保权重非负
        self.total_weight += self.testcase_weights[seed_data]

    def assign_energy(self, population: Sequence[Seed]) -> None:
        """根据存储的权重为 population 中的 seed 分配能量

        未注册的 seed 自动以默认权重 1.0 注册。
        """
        for seed in population:
            # 自动注册尚未追踪的 seed
            if seed.data not in self.testcase_weights:
                self.testcase_weights[seed.data] = 1.0
                self.total_weight += 1.0
            seed.energy = self.testcase_weights[seed.data]

    def select_next(self) -> str:
        """选择下一个执行的测试用例数据（独立于 PowerSchedule.choose 的接口）
        :return: 选中的用例数据（seed.data）
        """
        if not self.testcase_weights:
            raise RuntimeError("无已注册测试用例")

        # 总权重为0时均等概率选择
        if self.total_weight <= 1e-9:
            return random.choice(list(self.testcase_weights.keys()))

        # 按权重随机选择
        random_val = random.uniform(0, self.total_weight)
        current_sum = 0.0
        for seed_data, weight in self.testcase_weights.items():
            current_sum += weight
            if current_sum >= random_val:
                return seed_data

        return list(self.testcase_weights.keys())[-1]  # 兜底

    def reset(self):
        """重置调度器所有状态"""
        self.testcase_weights.clear()
        self.total_weight = 0.0
