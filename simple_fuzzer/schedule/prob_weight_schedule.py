import random
from typing import Dict, List, Sequence

from schedule.power_schedule import PowerSchedule
from utils.seed import Seed


class ProbabilityWeightedRoundRobinSchedule(PowerSchedule):
    """概率加权轮询调度：按测试用例权重分配选中概率

    未人工赋予权重时退化为均匀采样，可作为 baseline。
    """

    def __init__(self):
        super().__init__()
        self.testcase_weights: Dict[str, float] = {}  # seed.data → 权重
        self.total_weight: float = 0.0

    def register_testcase(self, seed_data: str, initial_weight: float = 1.0):
        """注册测试用例并设定初始权重
        :param seed_data: 用例数据
        :param initial_weight: 初始权重，默认 1.0，值越大被选中概率越高
        """
        if seed_data in self.testcase_weights:
            raise ValueError(f"用例{seed_data}已注册")

        self.testcase_weights[seed_data] = initial_weight
        self.total_weight += initial_weight

    def update_weight(self, seed_data: str, new_weight: float):
        """更新测试用例权重
        :param seed_data: 用例数据
        :param new_weight: 新权重（自动 clamp 到 ≥0）
        """
        if seed_data not in self.testcase_weights:
            raise ValueError(f"用例{seed_data}未注册")

        self.total_weight -= self.testcase_weights[seed_data]
        self.testcase_weights[seed_data] = max(new_weight, 0.0)  # 权重非负
        self.total_weight += self.testcase_weights[seed_data]

    def assign_energy(self, population: Sequence[Seed]) -> None:
        """根据存储的权重为 population 中的种子分配能量。

        未注册的种子自动以默认权重 1.0 注册；不在 population 中的
        陈旧条目会被清理。
        """
        for seed in population:
            # 自动注册尚未追踪的种子
            if seed.data not in self.testcase_weights:
                self.testcase_weights[seed.data] = 1.0
                self.total_weight += 1.0
            seed.energy = self.testcase_weights[seed.data]

        # 清理已不在 population 中的条目
        population_data = {seed.data for seed in population}
        stale = [k for k in self.testcase_weights if k not in population_data]
        for k in stale:
            self.total_weight -= self.testcase_weights[k]
            del self.testcase_weights[k]

    def select_next(self) -> str:
        """按权重随机选择下一个测试用例"""
        if not self.testcase_weights:
            raise RuntimeError("无已注册测试用例")

        # 总权重为零时均等概率选择
        if self.total_weight <= 1e-9:
            return random.choice(list(self.testcase_weights.keys()))

        # 按权重随机选择
        random_val = random.uniform(0, self.total_weight)
        current_sum = 0.0
        for seed_data, weight in self.testcase_weights.items():
            current_sum += weight
            if current_sum >= random_val:
                return seed_data

        return list(self.testcase_weights.keys())[-1]  # 浮点精度兜底

    def choose(self, population: List[Seed]) -> Seed:
        """覆盖基类 choose：将 select_next 集成到 fuzzer 的选择路径中"""
        # 同步 population → testcase_weights 并清理旧条目
        self.assign_energy(population)

        # 用 select_next 进行加权选择
        selected_data = self.select_next()

        # 将 data 字符串映射回 population 中的 Seed 对象
        for seed in population:
            if seed.data == selected_data:
                return seed

        # 兜底：正常情况不会走到这里
        return population[0]

    def reset(self):
        """重置调度器所有状态"""
        self.testcase_weights.clear()
        self.total_weight = 0.0
