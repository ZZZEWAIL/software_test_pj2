# C部分：概率加权轮询调度策略实现文档

## 一、任务说明

本部分负责实现核心文件`prob_weight_schedule.py`，该文件提供基于概率加权轮询的测试用例调度策略，核心目标是根据测试用例的权重分配选中概率，在轮询过程中按照权重比例随机选择测试用例执行，满足不同测试用例有不同执行优先级的调度需求。

## 二、概率加权轮询调度器（ProbabilityWeightedRoundRobinSchedule）

### 2\.1 设计思路

测试用例调度的核心诉求是：让重要程度高的测试用例有更高的被选中执行概率，同时保证调度过程的随机性（避免固定轮询顺序导致的测试场景单一）。

**权重的定义**：测试用例的重要性量化值，权重越高，被选中执行的概率越大，权重非负（默认初始权重为 1\.0）。

**调度原则**：

1\. 基于权重计算每个用例的选中概率（概率 = 用例权重 / 总权重）；

2\. 总权重为 0 时，所有用例均等概率被选中（避免调度逻辑异常）；

3\. 支持动态更新用例权重，权重变更后实时影响后续调度结果；

4\. 保证调度过程的可重置性，便于复用调度器实例。

### 2\.2 实现要点

```python
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
```

核心属性与方法说明：

|元素|类型 / 返回值|功能说明|
|---|---|---|
|`testcase_weights`|Dict\[int, float\]|存储已注册测试用例的 ID 与对应权重，保证用例与权重的一一映射|
|`testcases`|List\[int\]|维护已注册用例的 ID 列表，作为调度遍历的基础顺序|
|`total_weight`|float|实时累加所有用例的权重总和，用于概率计算的分母|
|`register_testcase`|无返回值|注册新测试用例，校验唯一性，初始化权重并更新总权重|
|`update_weight`|无返回值|动态更新用例权重，保证权重非负，实时调整总权重|
|`select_next`|int|核心调度逻辑，按权重随机选择用例，总权重为 0 时均等选择|
|`reset`|无返回值|清空所有状态，支持调度器实例复用|

### 2\.3 核心调度逻辑解析

`select_next` 方法采用「权重区间划分 \+ 随机值命中」的经典加权随机算法：

1\. 生成 0 到总权重之间的随机值 `random_val`；

2\. 遍历所有用例，累加权重得到「当前权重和」`current_sum`；

3\. 当 `current_sum ≥ random_val` 时，选中当前用例（该用例的权重区间包含随机值）；

4\. 总权重为 0 时，退化为纯随机选择（所有用例概率均等）。

示例：

\- 用例 A（权重 2）、用例 B（权重 3）、用例 C（权重 5），总权重 = 10；

\- 随机值落在 \[0,2\) → 选中 A（概率 20%）；

\- 随机值落在 \[2,5\) → 选中 B（概率 30%）；

\- 随机值落在 \[5,10\) → 选中 C（概率 50%）；

\- 完全符合「权重比例 = 选中概率」的设计目标。

## 三、测试验证

### 3\.1 测试环境

\- Python 3\.11\.6

\- 操作系统：Windows

\- 无第三方依赖，仅使用 Python 标准库

### 3\.2 单元测试整体结果

本次针对概率加权轮询调度器编写全套单元测试，覆盖正常功能、边界场景、异常捕获、权重计算、状态重置等全部核心逻辑，共计9项测试用例，所有测试全部通过，整体运行稳定无异常。完整测试运行日志如下：

test\_register\_duplicate\_testcase \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_register\_duplicate\_testcase\)
测试重复注册用例（应抛出异常） \.\.\. ok

test\_register\_testcase \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_register\_testcase\)
测试注册用例的正常逻辑 \.\.\. ok

test\_reset \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_reset\)
测试重置调度器 \.\.\. ok

test\_select\_next\_empty\_testcases \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_select\_next\_empty\_testcases\)
测试空用例列表选择（应抛出异常） \.\.\. ok

test\_select\_next\_probability\_distribution \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_select\_next\_probability\_distribution\)
验证选中概率与权重匹配（统计次数） \.\.\. ok

test\_select\_next\_single\_case \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_select\_next\_single\_case\)
测试单个用例时的选择逻辑 \.\.\. ok

test\_select\_next\_total\_weight\_zero \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_select\_next\_total\_weight\_zero\)
测试总权重为0时的均等概率选择 \.\.\. ok

test\_update\_nonexistent\_testcase \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_update\_nonexistent\_testcase\)
测试更新未注册用例（应抛出异常） \.\.\. ok

test\_update\_weight \(\_\_main\_\_\.TestProbabilityWeightedRoundRobinSchedule\.test\_update\_weight\)
测试更新用例权重 \.\.\. ok

\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-\-

Ran 9 tests in 0\.005s

OK

### 3\.3 测试场景分项说明

|测试用例名称|测试验证目标|测试结果|
|---|---|---|
|test\_register\_testcase|验证测试用例正常注册逻辑，校验权重、用例列表、总权重初始化准确性|通过|
|test\_register\_duplicate\_testcase|验证重复注册同一用例时，是否正常抛出指定异常，防止数据冲突|通过|
|test\_update\_weight|验证正常更新用例权重，校验总权重同步更新、权重非负兜底逻辑有效性|通过|
|test\_update\_nonexistent\_testcase|验证更新未注册用例权重时，正常抛出异常，拦截非法操作|通过|
|test\_select\_next\_empty\_testcases|验证无任何注册用例时，调用选择方法会抛出异常，规避空调度错误|通过|
|test\_select\_next\_single\_case|验证仅注册单个用例时，调度器始终选中该用例，逻辑正常|通过|
|test\_select\_next\_total\_weight\_zero|验证所有用例权重为0时，调度器降级为均等随机选择，无逻辑卡死|通过|
|test\_select\_next\_probability\_distribution|通过多次统计抽样，验证用例选中概率与自身权重占比匹配，核心加权算法有效|通过|
|test\_reset|验证重置方法可清空所有权重、用例、总权重状态，支持实例复用|通过|

### 3\.4 测试结果总结分析

本次测试全覆盖了调度器的**正常功能、边界场景、异常防护、算法准确性、状态重置**五大核心维度。9项测试用例全部通过。

功能层面：用例注册、权重更新、状态重置功能正常，数据同步准确；算法层面：加权概率分配精准，零权重降级策略生效；异常层面：各类非法操作、空场景均可正确抛出异常，程序健壮性极强，完全满足测试调度的业务需求。

## 四、设计说明

### 4\.1 异常处理设计

|异常场景|处理方式|设计理由|
|---|---|---|
|重复注册用例|抛出 ValueError|保证用例 ID 唯一性，避免权重映射冲突|
|更新未注册用例权重|抛出 ValueError|防止修改不存在的用例权重，避免数据不一致|
|无注册用例时选择|抛出 RuntimeError|空调度无意义，明确提示用户先注册用例|
|权重设为负数|自动修正为 0\.0|权重代表重要性，非负是合理约束，避免总权重异常|

### 4\.2 精度处理说明

在判断总权重是否为 0 时，使用`total_weight <= 1e-9` 而非直接判断 `== 0.0`，原因是：

\- 浮点数运算存在精度误差（如多次更新权重后，总权重可能是 `1e-15` 而非严格 0）；

\- `1e-9` 是工程上的极小值阈值，既避免精度误差导致的逻辑错误，又保证「接近 0 的总权重」按均等概率处理。

### 4\.3 性能优化点

\- 用例注册时直接追加到列表，避免频繁插入 / 删除导致的列表重构；

\- 权重更新时仅调整总权重的差值，而非重新计算所有用例权重之和（时间复杂度从 O\(n\) 降为 O\(1\)）；

\- 选择用例时遍历列表而非字典，保证遍历顺序稳定且无需额外排序开销。

该实现的时间复杂度：

\- 注册用例：O\(1\)；

\- 更新权重：O\(1\)；

\- 选择用例：O\(n\)（n 为用例数量，测试用例数量通常在千级以内，O\(n\) 可接受）；

\- 重置调度器：O\(1\)（清空容器为常数时间）。
