import random
from typing import Any


def _to_bytes(s: str) -> bytearray:
    """将字符串转换为可变字节数组（优先 latin-1 无损往返，回退 UTF-8）"""
    try:
        return bytearray(s.encode('latin-1'))
    except UnicodeEncodeError:
        # 含有 latin-1 范围外的字符（如中文、emoji），用 UTF-8
        return bytearray(s.encode('utf-8'))


def _to_str(data: bytearray) -> str:
    """将字节数组转换回字符串（latin-1 无损解码，始终成功）"""
    return data.decode('latin-1')


def insert_random_character(s: str) -> str:
    """
    向 s 中下标为 pos 的位置插入一个随机 byte
    pos 为随机生成，范围为 [0, len(s)]
    插入的 byte 为随机生成，范围为 [32, 127]
    """
    pos = random.randint(0, len(s))  # 随机位置，包括插入在末尾
    random_char = chr(random.randint(32, 126))  # ASCII 范围内可打印字符（127是DEL，不常用）
    return s[:pos] + random_char + s[pos:]


def flip_random_bits(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 bitflip 与 random havoc 实现相邻 N 位翻转（N = 1, 2, 4），其中 N 为随机生成
    从 s 中随机挑选一个 bit，将其与其后面 N - 1 位翻转（翻转即 0 -> 1; 1 -> 0）
    注意：不要越界
    """
    if not s:
        return s

    data = _to_bytes(s)
    total_bits = len(data) * 8

    N = random.choice([1, 2, 4])
    if total_bits < N:
        return s  # 不足 N 位，不翻转

    bit_index = random.randint(0, total_bits - N)

    for i in range(N):
        current_bit = bit_index + i
        byte_index = current_bit // 8
        bit_offset = current_bit % 8

        # 翻转对应位（用异或操作）
        data[byte_index] ^= (1 << (7 - bit_offset))  # 高位在前（big-endian）

    return _to_str(data)


def arithmetic_random_bytes(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 arithmetic inc/dec 与 random havoc 实现相邻 N 字节随机增减（N = 1, 2, 4），其中 N 为随机生成
    字节随机增减：
        1. 取其中一个 byte，将其转换为数字 num1；
        2. 将 num1 加上一个 [-35, 35] 的随机数，得到 num2；
        3. 用 num2 所表示的 byte 替换该 byte
    从 s 中随机挑选一个 byte，将其与其后面 N - 1 个 bytes 进行字节随机增减
    注意：不要越界；如果出现单个字节在添加随机数之后，可以通过取模操作使该字节落在 [0, 255] 之间
    """
    if not s:
        return s

    data = _to_bytes(s)
    N = random.choice([1, 2, 4])

    if len(data) < N:
        return s  # 数据长度不足 N 字节

    pos = random.randint(0, len(data) - N)

    for i in range(N):
        original = data[pos + i]
        delta = random.randint(-35, 35)
        modified = (original + delta) % 256
        data[pos + i] = modified

    return _to_str(data)


def interesting_random_bytes(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 interesting values 与 random havoc 实现相邻 N 字节随机替换为 interesting_value（N = 1, 2, 4），其中 N 为随机生成
    interesting_value 替换：
        1. 构建分别针对于 1, 2, 4 bytes 的 interesting_value 数组；
        2. 随机挑选 s 中相邻连续的 1, 2, 4 bytes，将其替换为相应 interesting_value 数组中的随机元素；
    注意：不要越界
    """
    if not s:
        return s

    # 定义各类型的 interesting values
    interesting_values = {
        1: [ord(c) for c in ['A', 'B', 'C', 'Z', '0', '9', '!', '?']],  # 单字节显示字符
        2: [int.from_bytes(b, 'big') for b in [b'OK', b'Hi', b'42', b'Go']],  # 2 字节 ASCII
        4: [int.from_bytes(b, 'big') for b in [b'TEST', b'DEAD', b'BEEF', b'GOOD']],  # 4 字节 ASCII
    }

    # 转换为可变字节数组
    data = _to_bytes(s)
    N = random.choice([1, 2, 4])

    if len(data) < N:
        return s  # 字节数不足，无法替换

    # 随机选择替换位置，确保不越界
    pos = random.randint(0, len(data) - N)

    # 随机选择一个 interesting value，并转换为字节序列
    value = random.choice(interesting_values[N])
    value_bytes = value.to_bytes(N, byteorder='big')  # 使用 big endian

    # 替换相应的 N 字节
    for i in range(N):
        data[pos + i] = value_bytes[i]

    # 返回变异后的字符串（忽略解码错误）
    return _to_str(data)


def havoc_random_insert(s: str):
    """
    基于 AFL 变异算法策略中的 random havoc 实现随机插入
    随机选取一个位置，插入一段的内容，其中 75% 的概率是插入原文中的任意一段随机长度的内容，25% 的概率是插入一段随机长度的 bytes
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)
    insert_pos = random.randint(0, length)

    # 生成插入内容长度，随机范围 1 到 length 或最大 16（防止太长）
    max_len = min(16, length) if length > 0 else 16
    insert_len = random.randint(1, max_len if max_len > 0 else 1)

    if random.random() < 0.75:
        # 75% 概率插入原文中的一段
        if length == 0:
            insert_bytes = bytearray()
        else:
            start_pos = random.randint(0, length - insert_len)
            insert_bytes = data[start_pos:start_pos + insert_len]
    else:
        # 25% 概率插入随机生成的 bytes（范围选可打印ASCII）
        insert_bytes = bytearray(random.randint(0x20, 0x7E) for _ in range(insert_len))

    # 插入 bytes
    new_data = data[:insert_pos] + insert_bytes + data[insert_pos:]

    return _to_str(new_data)


def havoc_random_replace(s: str):
    """
    基于 AFL 变异算法策略中的 random havoc 实现随机替换
    随机选取一个位置，替换随后一段随机长度的内容，其中 75% 的概率是替换为原文中的任意一段随机长度的内容，25% 的概率是替换为一段随机长度的 bytes
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)

    # 随机选择替换起始位置
    pos = random.randint(0, length - 1)

    # 替换长度随机，最大为剩余长度或16，防止过长
    max_len = min(16, length - pos)
    replace_len = random.randint(1, max_len)

    if random.random() < 0.75:
        # 75% 概率用原文中随机一段替换
        if length - replace_len <= 0:
            # 无法从原文其他位置复制（字符串太短），回退为随机字节
            replace_bytes = bytearray(random.randint(0x20, 0x7E) for _ in range(replace_len))
        else:
            start = random.randint(0, length - replace_len)
            replace_bytes = data[start:start + replace_len]
    else:
        # 25% 概率用随机生成的可打印 ASCII 替换
        replace_bytes = bytearray(random.randint(0x20, 0x7E) for _ in range(replace_len))

    # 替换指定区间
    new_data = data[:pos] + replace_bytes + data[pos + replace_len:]

    return _to_str(new_data)


def random_block_swap(s: str) -> str:
    """
    随机选取两个相邻的字节块并交换顺序
    1. 随机选定整个字符串长度内，选取一段长度 L1 (1~8) 和紧随其后的另一段长度 L2 (1~8)
    2. 交换这两段字节块的顺序
    3. 注意不要越界，且保证两段字节块相邻
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)
    if length < 2:
        return s  # 长度不足

    max_block_size = 8
    # 随机选择第一个块的长度，至少1字节，最多8或剩余长度的一半
    L1 = random.randint(1, min(max_block_size, length // 2))
    # 第二个块长度也类似，但保证相邻且不越界
    L2 = random.randint(1, min(max_block_size, length - L1))

    # 选定第一个块起始位置，使第二块紧跟其后且不越界
    start_pos = random.randint(0, length - (L1 + L2))

    block1 = data[start_pos:start_pos + L1]
    block2 = data[start_pos + L1:start_pos + L1 + L2]

    # 交换块
    new_data = data[:start_pos] + block2 + block1 + data[start_pos + L1 + L2:]

    return _to_str(new_data)


def delete_random_bytes(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 random havoc 实现随机删除
    随机选取一段连续字节（长度 1 ~ min(8, len-1)），将其从字符串中删除
    删除后至少保留 1 字节，避免返回空字符串（空字符串作为 fuzz 输入通常无意义）
    注意：不要越界
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)
    if length <= 1:
        return s  # 至少保留 1 字节

    N = random.randint(1, min(8, length - 1))
    pos = random.randint(0, length - N)

    new_data = data[:pos] + data[pos + N:]

    return _to_str(new_data)


def clone_random_bytes(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 random havoc 实现随机克隆/重复
    从字符串中随机选取一段连续字节（长度 1 ~ min(8, len)），
    将其复制并插入到字符串中的随机位置，从而增长字符串
    注意：不要越界
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)

    N = random.randint(1, min(8, length))
    src = random.randint(0, length - N)

    # 复制选中的字节段
    cloned = data[src:src + N]

    # 随机选择插入位置（可在末尾）
    insert_pos = random.randint(0, length)
    new_data = data[:insert_pos] + cloned + data[insert_pos:]

    return _to_str(new_data)


def overwrite_with_random_bytes(s: str) -> str:
    """
    基于 AFL 变异算法策略中的 random havoc 实现随机字节完全覆盖
    随机选取一段连续字节（长度 1 ~ min(8, len)），
    用完全随机的字节（范围 0~255，包含不可打印字符和控制字符）覆盖该段
    与 havoc_random_replace 的区别：本函数总是使用随机字节，不复制原文
    注意：不要越界
    """
    if not s:
        return s

    data = _to_bytes(s)
    length = len(data)

    N = random.randint(1, min(8, length))
    pos = random.randint(0, length - N)

    for i in range(N):
        data[pos + i] = random.randint(0, 255)

    return _to_str(data)


class Mutator:

    def __init__(self) -> None:
        """Constructor"""
        self.mutators = [
            insert_random_character,
            flip_random_bits,
            arithmetic_random_bytes,
            interesting_random_bytes,
            havoc_random_insert,
            havoc_random_replace,
            random_block_swap,
            delete_random_bytes,
            clone_random_bytes,
            overwrite_with_random_bytes,
        ]

    def mutate(self, inp: Any) -> Any:
        mutator = random.choice(self.mutators)
        return mutator(inp)
