# Role A: `mutator.py` 变异策略完善 — 实现与测试报告

## 一、实现概述

在原有 7 种变异策略基础上，新增 3 种策略，修复 2 个 Bug，并对字节级变异函数的编解码机制进行了根本性改进。最终 `Mutator` 类包含 **10 种变异策略**。

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `utils/mutator.py` | 修改 | 新增策略 + Bug 修复 |
| `tests/test_mutator.py` | 新建 | 63 项单元测试 |

---

## 二、新增变异策略

### 2.1 `delete_random_bytes` — 随机删除

```
删除 N 个连续字节 (N = 1 ~ min(8, len-1))，缩短字符串长度。
删除后至少保留 1 字节，避免空字符串。
```

**对应 AFL 策略**: random havoc 中的 delete 操作

### 2.2 `clone_random_bytes` — 随机克隆/重复

```
从字符串中复制一段 N 字节 (N = 1 ~ min(8, len))，插入到随机位置。
100% 使用原文内容（与 havoc_random_insert 的 75%/25% 区分）。
```

**对应 AFL 策略**: random havoc 中的 clone 操作

### 2.3 `overwrite_with_random_bytes` — 随机字节覆盖

```
用随机字节（范围 0~255，含控制字符）覆盖 N 字节 (N = 1 ~ min(8, len))。
与 havoc_random_replace 区别：100% 使用随机字节，不复制原文。
```

**对应 AFL 策略**: random havoc 中的 overwrite 操作

---

## 三、Bug 修复

### 3.1 字节级操作的编解码修复

**问题**: 原代码使用 `s.encode('utf-8')` + `data.decode('utf-8', errors='ignore')` 进行字节与字符串的转换。当位翻转/算术变异产生非法 UTF-8 字节序列时，`errors='ignore'` 会**静默丢弃**这些字节，导致：
- 数据意外丢失
- 变异后的字符串长度不可预测地缩短

**修复**: 引入 `_to_bytes()` / `_to_str()` 辅助函数，采用 **latin-1 优先 + UTF-8 回退** 的编解码策略：

```python
def _to_bytes(s: str) -> bytearray:
    try:
        return bytearray(s.encode('latin-1'))    # latin-1 无损: 256 字节 ↔ 256 字符
    except UnicodeEncodeError:
        return bytearray(s.encode('utf-8'))      # 非 latin-1 字符回退 UTF-8

def _to_str(data: bytearray) -> str:
    return data.decode('latin-1')                 # 始终成功，无数据丢失
```

**优势**: latin-1 编码保证每个字节 0-255 与一个 Unicode 字符 (U+0000-U+00FF) 一一对应，实现真正的无损往返。对含中文等非 latin-1 字符的输入，回退 UTF-8 编码后 latin-1 解码同样无数据丢失。

### 3.2 `havoc_random_replace` 边界条件修复

**问题**: 当 `replace_len == length` 时（替换长度等于字符串总长），无法从原文其他位置复制内容，原代码设定 `replace_bytes = bytearray()`（空），导致替换操作等价于删除——字节长度意外缩短。

**修复**: 当 `length - replace_len <= 0` 时，回退为生成随机字节替换，保持字节长度不变：

```python
if length - replace_len <= 0:
    replace_bytes = bytearray(random.randint(0x20, 0x7E) for _ in range(replace_len))
```

---

## 四、完整变异策略列表（10 种）

| # | 策略函数 | 类型 | N 范围 | 字节长度变化 |
|---|----------|------|--------|-------------|
| 1 | `insert_random_character` | 单字符插入 | 1 字符 | +1 |
| 2 | `flip_random_bits` | 位翻转 | 1, 2, 4 位 | 不变 |
| 3 | `arithmetic_random_bytes` | 算术变异 | 1, 2, 4 字节 | 不变 |
| 4 | `interesting_random_bytes` | 趣味值替换 | 1, 2, 4 字节 | 不变 |
| 5 | `havoc_random_insert` | 随机插入 | 1~16 字节 | +insert_len |
| 6 | `havoc_random_replace` | 随机替换 | 1~16 字节 | 不变 |
| 7 | `random_block_swap` | 块交换 | L1+L2 (各 1~8) | 不变 |
| 8 | **`delete_random_bytes`** | **随机删除** | **1~8 字节** | **-N** |
| 9 | **`clone_random_bytes`** | **随机克隆** | **1~8 字节** | **+N** |
| 10 | **`overwrite_with_random_bytes`** | **随机覆盖** | **1~8 字节** | **不变** |

> 粗体为本次新增的 3 种策略。

---

## 五、测试结果

### 5.1 测试概览

- **测试框架**: pytest (Python 标准库 unittest)
- **测试文件**: `simple_fuzzer/tests/test_mutator.py`
- **测试用例数**: **63 项**
- **通过率**: **63/63 = 100%**

### 5.2 测试分类

| 测试类 | 用例数 | 覆盖范围 |
|--------|--------|----------|
| `TestInsertRandomCharacter` | 6 | 正常插入、边界（空串/单字符）、非 ASCII 输入、插入范围验证 |
| `TestFlipRandomBits` | 7 | 正常翻转、空串、单字符、N 值覆盖、短输入保护、XOR 性质验证 |
| `TestArithmeticRandomBytes` | 5 | 正常算术、取模边界验证、值域 [0,255] 验证 |
| `TestInterestingRandomBytes` | 5 | 正常替换、interesting value 构造验证、短输入保护 |
| `TestHavocRandomInsert` | 4 | 正常插入、空串、插入源类型（75%/25%）验证 |
| `TestHavocRandomReplace` | 4 | 正常替换、字节长度保持性验证（修复后） |
| `TestRandomBlockSwap` | 5 | 正常交换、交换实际发生验证、字节长度保持性 |
| `TestDeleteRandomBytes` | 6 | 正常删除、空串/单字符/双字符保护、删除范围验证 |
| `TestCloneRandomBytes` | 5 | 正常克隆、长度增加验证、插入位置多样性 |
| `TestOverwriteWithRandomBytes` | 5 | 正常覆盖、字节范围 0-255 验证、长度保持性 |
| `TestMutator` | 5 | 策略注册数量验证、mutate 接口验证 |
| `TestEncodingIntegrity` | 3 | ASCII/Unicode/大输入编码完整性 |
| `TestEdgeCases` | 3 | 空串/单字符/特殊字符综合测试 |

### 5.3 测试执行输出

```
============================= test session starts =============================
platform win32 -- Python 3.13.13, pytest-9.0.3, pluggy-1.6.0
collected 63 items

tests/test_mutator.py::TestInsertRandomCharacter::test_empty_string PASSED [  1%]
tests/test_mutator.py::TestInsertRandomCharacter::test_insert_at_beginning_possible PASSED [  3%]
tests/test_mutator.py::TestInsertRandomCharacter::test_insert_at_end_possible PASSED [  4%]
tests/test_mutator.py::TestInsertRandomCharacter::test_inserted_char_in_printable_range PASSED [  6%]
tests/test_mutator.py::TestInsertRandomCharacter::test_non_ascii_input PASSED [  7%]
tests/test_mutator.py::TestInsertRandomCharacter::test_normal_insert PASSED [  9%]
tests/test_mutator.py::TestFlipRandomBits::test_bit_flip_reversible PASSED [ 11%]
tests/test_mutator.py::TestFlipRandomBits::test_empty_string PASSED [ 12%]
tests/test_mutator.py::TestFlipRandomBits::test_n_values PASSED [ 14%]
tests/test_mutator.py::TestFlipRandomBits::test_non_ascii_input PASSED [ 15%]
tests/test_mutator.py::TestFlipRandomBits::test_normal_flip PASSED [ 17%]
tests/test_mutator.py::TestFlipRandomBits::test_short_input_less_than_n_bits PASSED [ 19%]
tests/test_mutator.py::TestFlipRandomBits::test_single_char PASSED [ 20%]
tests/test_mutator.py::TestArithmeticRandomBytes::test_delta_modulo PASSED [ 22%]
tests/test_mutator.py::TestArithmeticRandomBytes::test_empty_string PASSED [ 23%]
tests/test_mutator.py::TestArithmeticRandomBytes::test_normal_arithmetic PASSED [ 25%]
tests/test_mutator.py::TestArithmeticRandomBytes::test_short_string PASSED [ 26%]
tests/test_mutator.py::TestArithmeticRandomBytes::test_value_range PASSED [ 28%]
tests/test_mutator.py::TestInterestingRandomBytes::test_empty_string PASSED [ 30%]
tests/test_mutator.py::TestInterestingRandomBytes::test_interesting_value_types PASSED [ 31%]
tests/test_mutator.py::TestInterestingRandomBytes::test_interesting_values_exist PASSED [ 33%]
tests/test_mutator.py::TestInterestingRandomBytes::test_normal_replacement PASSED [ 34%]
tests/test_mutator.py::TestInterestingRandomBytes::test_short_input_cannot_replace PASSED [ 36%]
tests/test_mutator.py::TestHavocRandomInsert::test_empty_string PASSED [ 38%]
tests/test_mutator.py::TestHavocRandomInsert::test_insert_source_type PASSED [ 39%]
tests/test_mutator.py::TestHavocRandomInsert::test_normal_insert PASSED [ 41%]
tests/test_mutator.py::TestHavocRandomInsert::test_single_char_input PASSED [ 42%]
tests/test_mutator.py::TestHavocRandomReplace::test_empty_string PASSED [ 44%]
tests/test_mutator.py::TestHavocRandomReplace::test_length_preservation PASSED [ 46%]
tests/test_mutator.py::TestHavocRandomReplace::test_normal_replace PASSED [ 47%]
tests/test_mutator.py::TestHavocRandomReplace::test_single_char_input PASSED [ 49%]
tests/test_mutator.py::TestRandomBlockSwap::test_byte_length_preserved PASSED [ 50%]
tests/test_mutator.py::TestRandomBlockSwap::test_empty_string PASSED [ 52%]
tests/test_mutator.py::TestRandomBlockSwap::test_normal_swap PASSED [ 53%]
tests/test_mutator.py::TestRandomBlockSwap::test_short_string PASSED [ 55%]
tests/test_mutator.py::TestRandomBlockSwap::test_swap_actually_happens PASSED [ 57%]
tests/test_mutator.py::TestDeleteRandomBytes::test_delete_range PASSED [ 58%]
tests/test_mutator.py::TestDeleteRandomBytes::test_empty_string PASSED [ 60%]
tests/test_mutator.py::TestDeleteRandomBytes::test_non_ascii_input PASSED [ 61%]
tests/test_mutator.py::TestDeleteRandomBytes::test_normal_delete PASSED [ 63%]
tests/test_mutator.py::TestDeleteRandomBytes::test_single_char PASSED [ 65%]
tests/test_mutator.py::TestDeleteRandomBytes::test_two_chars PASSED [ 66%]
tests/test_mutator.py::TestCloneRandomBytes::test_clone_insert_positions PASSED [ 68%]
tests/test_mutator.py::TestCloneRandomBytes::test_empty_string PASSED [ 69%]
tests/test_mutator.py::TestCloneRandomBytes::test_length_increases PASSED [ 71%]
tests/test_mutator.py::TestCloneRandomBytes::test_normal_clone PASSED [ 73%]
tests/test_mutator.py::TestCloneRandomBytes::test_single_char PASSED [ 74%]
tests/test_mutator.py::TestOverwriteWithRandomBytes::test_byte_length_preserved PASSED [ 76%]
tests/test_mutator.py::TestOverwriteWithRandomBytes::test_empty_string PASSED [ 77%]
tests/test_mutator.py::TestOverwriteWithRandomBytes::test_normal_overwrite PASSED [ 79%]
tests/test_mutator.py::TestOverwriteWithRandomBytes::test_overwrite_range_includes_control_chars PASSED [ 80%]
tests/test_mutator.py::TestOverwriteWithRandomBytes::test_single_char PASSED [ 82%]
tests/test_mutator.py::TestMutator::test_all_ten_mutators_registered PASSED [ 84%]
tests/test_mutator.py::TestMutator::test_expected_mutator_names PASSED [ 85%]
tests/test_mutator.py::TestMutator::test_mutate_covers_all_strategies PASSED [ 87%]
tests/test_mutator.py::TestMutator::test_mutate_empty_string PASSED [ 88%]
tests/test_mutator.py::TestMutator::test_mutate_returns_string PASSED [ 90%]
tests/test_mutator.py::TestEncodingIntegrity::test_ascii_roundtrip PASSED [ 92%]
tests/test_mutator.py::TestEncodingIntegrity::test_large_input PASSED [ 93%]
tests/test_mutator.py::TestEncodingIntegrity::test_unicode_no_crash PASSED [ 95%]
tests/test_mutator.py::TestEdgeCases::test_all_funcs_handle_empty_string PASSED [ 96%]
tests/test_mutator.py::TestEdgeCases::test_all_funcs_handle_single_char PASSED [ 98%]
tests/test_mutator.py::TestEdgeCases::test_non_string_like_inputs PASSED [100%]

============================= 63 passed in 0.08s ==============================
```

---

## 六、集成验证

使用更新后的 `mutator.py` 运行完整 fuzzer 管线（5 秒短测试）：

```
$ python main.py --sample 1 --run-time 5 --quiet

Covered Lines: 10 (sample1: 6,7,8,9,10,11,12,14; trace/coverage infra)
Unique Crashes: 5 (5 种不同的崩溃签名)
```

Fuzzer 正常运行，变异策略被正确集成到 `GreyBoxFuzzer` → `create_candidate()` → `Mutator.mutate()` 调用链中。

---

## 七、技术决策说明

| 决策 | 选择 | 理由 |
|------|------|------|
| 字节编码 | latin-1 优先 + UTF-8 回退 | latin-1 保证 256 字节 ↔ 256 字符无损往返；UTF-8 回退覆盖中文/emoji |
| 解码方式 | 始终 latin-1 | 任意字节序列均可成功解码，零数据丢失 |
| 删除保护 | 至少保留 1 字节 | 空字符串作为 fuzz 输入无意义，且会破坏后续变异 |
| 替换回退 | 无法复制时回退随机字节 | 保持字节长度不变的语义一致性 |
| 测试驱动 | TDD（先写测试再实现） | 确保每种策略的边界条件和正常行为都被验证 |

---

## 八、运行测试命令

```bash
cd simple_fuzzer

# 运行全部 mutator 测试
python -m pytest tests/test_mutator.py -v

# 运行集成测试（fuzzer 全流程）
python main.py --sample 1 --run-time 5
python main.py --sample 2 --run-time 5
python main.py --sample 3 --run-time 5
python main.py --sample 4 --run-time 5
```
