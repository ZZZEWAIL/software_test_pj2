## 审查结论：四项任务全部完成，代码运行正常

### 任务1 - mutator.py 变异策略 ✅

实现了 **10 种**变异策略，远超"多种不同类型"的要求：

- `insert_random_character` — 随机插入字符
- `flip_random_bits` — 位翻转 (1/2/4 bits)
- `arithmetic_random_bytes` — 算术增减 (1/2/4 bytes)
- `interesting_random_bytes` — interesting 值替换
- `havoc_random_insert` — 随机插入段
- `havoc_random_replace` — 随机替换段
- `random_block_swap` — 块交换
- `delete_random_bytes` — 随机删除
- `clone_random_bytes` — 随机克隆/重复
- `overwrite_with_random_bytes` — 随机字节覆盖

### 任务2 - 路径频率调度 ✅

- [path\_power\_schedule.py](file:///e:/PJ2-Fuzzing-v260530/software_test_pj2/simple_fuzzer/schedule/path_power_schedule.py) — `assign_energy` 按路径频率倒数分配能量
- [path\_grey\_box\_fuzzer.py](file:///e:/PJ2-Fuzzing-v260530/software_test_pj2/simple_fuzzer/fuzzer/path_grey_box_fuzzer.py) — `run()` 中更新 `path_frequency`，追踪新路径数

### 任务3 - 新调度策略 ✅

实现了 [rare\_line\_power\_schedule.py](file:///e:/PJ2-Fuzzing-v260530/software_test_pj2/simple_fuzzer/schedule/rare_line_power_schedule.py)（基于罕见代码行），已在 [main.py](file:///e:/PJ2-Fuzzing-v260530/software_test_pj2/simple_fuzzer/main.py) 中注册为 `--schedule rare_line` 选项。

### 任务4 - 持久化 ✅

- [grey\_box\_fuzzer.py](file:///e:/PJ2-Fuzzing-v260530/software_test_pj2/simple_fuzzer/fuzzer/grey_box_fuzzer.py) — 实现了 `_offload_seed`（低能量 seed 离线到磁盘）、`_try_offload_population`（超过 500 个 seed 时自动离线）、`_persist_intermediate`（crash\_map 定期持久化）
- [path\_grey\_box\_fuzzer.py](file:///e:/PJ2-Fuzzing-v260530/software_test_pj2/simple_fuzzer/fuzzer/path_grey_box_fuzzer.py) — 实现了 `_persist_path_frequency`（频率数据持久化）

### 运行验证结果

| 测试                            | 结果                                                                                  |
| :---------------------------- | :---------------------------------------------------------------------------------- |
| sample4 + path 调度 (30s)       | ✅ 正常运行，覆盖大量行                                                                        |
| sample1 + rare\_line 调度 (15s) | ✅ 正常运行，发现 5 个唯一崩溃                                                                   |
| sample3 + path 调度 (15s)       | ✅ 正常运行，发现 2 个唯一崩溃                                                                   |
| 持久化文件                         | ✅ `_result/persist/` 下生成了 `crash_map.pkl`、`path_frequency.pkl`、`line_frequency.pkl` |

