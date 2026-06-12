import random
from typing import List, Dict

class ProbabilityWeightedRoundRobinSchedule:
    """概率加权轮询调度：按测试用例权重分配选中概率，轮询时随机选择"""
    def __init__(self):
        self.testcase_weights: Dict[int, float] = {}  # 用例ID-权重映射
        self.testcases: List[int] = []  # 已注册用例ID列表
        self.total_weight: float = 0.0  # 权重总和（计算概率用）

    def register_testcase(self, testcase_id: int, initial_weight: float = 1.0):
        """注册测试用例并初始化权重
        :param testcase_id: 用例唯一ID
        :param initial_weight: 初始权重（默认1.0，值越高选中概率越大）
        """
        if testcase_id in self.testcase_weights:
            raise ValueError(f"用例{testcase_id}已注册")
        
        self.testcases.append(testcase_id)
        self.testcase_weights[testcase_id] = initial_weight
        self.total_weight += initial_weight

    def update_weight(self, testcase_id: int, new_weight: float):
        """更新测试用例权重
        :param testcase_id: 用例ID
        :param new_weight: 新权重（≥0）
        """
        if testcase_id not in self.testcase_weights:
            raise ValueError(f"用例{testcase_id}未注册")
        
        self.total_weight -= self.testcase_weights[testcase_id]
        self.testcase_weights[testcase_id] = max(new_weight, 0.0)  # 确保权重非负
        self.total_weight += self.testcase_weights[testcase_id]

    def select_next(self) -> int:
        """选择下一个执行的测试用例（核心调度逻辑）
        :return: 选中的用例ID
        """
        if not self.testcases:
            raise RuntimeError("无已注册测试用例")
        
        # 总权重为0时均等概率选择
        if self.total_weight <= 1e-9:
            return random.choice(self.testcases)
        
        # 按权重随机选择
        random_val = random.uniform(0, self.total_weight)
        current_sum = 0.0
        for testcase_id in self.testcases:
            current_sum += self.testcase_weights[testcase_id]
            if current_sum >= random_val:
                return testcase_id
        
        return self.testcases[-1]  # 兜底（理论上不会执行）

    def reset(self):
        """重置调度器所有状态"""
        self.testcase_weights.clear()
        self.testcases.clear()
        self.total_weight = 0.0