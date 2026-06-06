# B 部分：路径频率调度策略实现文档

## 一、任务说明

本部分负责完善两个核心文件：

- `schedule/path_power_schedule.py`：基于路径频率的能量调度策略
- `fuzzer/path_grey_box_fuzzer.py`：集成路径频率追踪的灰盒 Fuzzer

## 二、路径频率调度策略（PathPowerSchedule）

### 2.1 设计思路

灰盒模糊测试的核心反馈机制是覆盖率引导：Fuzzer 优先变异那些能触达"罕见路径"的种子，以探索更多未覆盖的代码区域。

**路径的定义**：一次执行覆盖的代码行集合，即 `frozenset(seed.coverage)`——由若干 `(函数名, 行号)` 组成的不可变集合。不同的覆盖行集合代表不同的执行路径。

**能量分配原则**：路径触发频率越低，种子获得的能量越高，在后续调度中被选中变异的概率越大。

### 2.2 实现要点

```python
class PathPowerSchedule(PowerSchedule):
    def __init__(self):
        super().__init__()
        self.path_frequency: Dict[frozenset, int] = {}

    def assign_energy(self, population):
        for seed in population:
            path_id = frozenset(seed.coverage)
            freq = self.path_frequency.get(path_id, 1)
            seed.energy = 1.0 / freq
```

- `path_frequency`：字典，key 为路径标识（frozenset），value 为该路径被触发的累计次数
- `assign_energy`：为种群中每个 seed 计算能量，公式为 `energy = 1 / freq`
  - 首次出现的路径（freq=1）：能量 = 1.0（最高优先级）
  - 被触发 100 次的路径：能量 = 0.01（较低优先级）
  - 保证能量之和恒正，不会出现归一化溢出

### 2.3 为什么使用 `1/freq` 而非指数函数

初始设计使用 `2^(1-freq)` 实现指数衰减，但在长时间运行中，高频路径的指数会溢出 Python 浮点数上限（`2^1024`），且低频路径能量趋近于 0 导致归一化断言失败。`1/freq` 简洁稳健，同样满足"与频率成反比"的语义。

## 三、路径灰盒 Fuzzer（PathGreyBoxFuzzer）

### 3.1 设计思路

`PathGreyBoxFuzzer` 继承自 `GreyBoxFuzzer`，在其基础上新增路径频率追踪能力。每次执行目标函数后：

1. 从 Runner 获取本次执行的覆盖率（即路径）
2. 将路径 ID 反馈给调度器，更新全局路径频率表
3. 若发现新路径，记录发现时间和累计路径数

### 3.2 实现要点

```python
class PathGreyBoxFuzzer(GreyBoxFuzzer):
    def run(self, runner):
        result, outcome = super().run(runner)  # 复用父类覆盖率收集与种群管理

        path_id = frozenset(runner.coverage())
        if path_id not in self.schedule.path_frequency:
            self.schedule.path_frequency[path_id] = 0
            self.last_new_path_time = time.time()  # 记录新路径发现时间
            self.total_paths += 1                   # 累计路径总数
        self.schedule.path_frequency[path_id] += 1

        return result, outcome
```

**关键设计决策**：

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 路径频率存储位置 | 存储在 `schedule.path_frequency` | 调度器需要频率数据分配能量，放在 schedule 中减少数据传递 |
| 路径标识方式 | `frozenset(coverage)` | 覆盖行集合而非有序序列，因为 Python 覆盖率追踪以行为粒度 |
| 频率更新时机 | 每次 `run()` 都更新 | 即使输入没有产生新覆盖，该路径的触发次数仍需记录 |
| 打印控制 | 独立的 `is_print` 属性 | 路径 Fuzzer 的表头比父类多 2 列（Last New Path、Total Paths），需要独立控制 |

### 3.3 统计输出

在父类 5 列统计基础上新增 2 列：

| 列名 | 含义 | 来源 |
|------|------|------|
| Last New Path | 最后一次发现新路径的时间 | `self.last_new_path_time` |
| Total Paths | 累计发现的唯一路径数 | `self.total_paths` |

## 四、数据流总结

```
┌──────────────────────────────────────────────────────────┐
│                    Fuzzing 主循环                         │
│                                                          │
│  1. schedule.choose(population)                          │
│     └─ assign_energy(population)                         │
│        └─ 对每个 seed: energy = 1 / path_frequency[path] │
│     └─ normalized_energy → random.choices 加权随机选择    │
│                                                          │
│  2. mutator.mutate(seed.data) → 生成变异输入              │
│                                                          │
│  3. runner.run(input) → 执行目标, 收集覆盖率               │
│                                                          │
│  4. PathGreyBoxFuzzer.run()                              │
│     ├─ 父类: 判断新覆盖 → 加入种群 / 记录崩溃              │
│     └─ 本类: 更新 schedule.path_frequency[path_id]       │
│                                                          │
│  5. 循环，直到达到设定运行时间                              │
└──────────────────────────────────────────────────────────┘
```

## 五、测试验证

### 5.1 测试环境

- Python 3.12.1
- macOS 12.6 (Darwin 21.5.0)
- 不含 uv，使用系统 Python 直接运行

### 5.2 测试结果

| 样例 | 运行时间 | 执行次数 | 唯一路径数 | 崩溃数 | 覆盖行数 |
|------|----------|----------|------------|--------|----------|
| sample1 | 3s | ~10K | 5 | 6 | 10 |
| sample3 | 5s | ~152K | 5 | 5 | 8 |
| sample4 | 3s | ~735 | 161 | 0 | 530 |

### 5.3 结果分析

- **sample1/sample3**：代码规模小（10-14行），路径数少（5条），崩溃发现快（因类型转换、数组越界等浅层 bug）
- **sample4**：HTMLParser 库代码量大（500+行覆盖），路径丰富（161条），但因库代码健壮，无崩溃
- **路径调度效果**：`1/freq` 公式使高频路径能量快速衰减，Fuzzer 倾向于选择罕见路径的种子进行变异

## 六、补充说明

### 6.1 导入问题修复

原始项目中 `utils/`、`schedule/`、`samples/` 三个目录缺少 `__init__.py` 文件。在 Python 3 隐式命名空间包机制下，若系统 site-packages 中存在同名包（如 `utils`），会导致本地包被覆盖，引发 `ModuleNotFoundError`。已为三个目录补充 `__init__.py`，确保在任何 Python 环境下均可正确导入。

### 6.2 `--quiet` 模式支持

修改后的 `PathGreyBoxFuzzer` 完整支持 `--quiet` 命令行参数，静默模式下不打印统计表格，仅输出最终结果。
