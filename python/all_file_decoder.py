from __future__ import annotations

import io
from pathlib import Path
from typing import Tuple

import numpy as np

from current_data import CurrentData


MAX_DATA_LENGTH = 512 * 1024  # 与 C/Java 实现一致


def _parse_string_field(buf: memoryview, start: int, end: int) -> str:
    """
    从 [start, end) 提取 ASCII 字符串, 去掉前后空白.

    输入:
    - buf: memoryview, 对底层 bytes 的只读视图.
    - start, end: 字节区间.

    输出:
    - 去掉空白后的字符串.
    """
    start = max(0, start)
    end = min(len(buf), end)
    while start < end and buf[start] in b" \t\r\n":
        start += 1
    while end > start and buf[end - 1] in b" \t\r\n":
        end -= 1
    if end <= start:
        return ""
    return bytes(buf[start:end]).decode("ascii", errors="ignore")


def _parse_int_field(buf: memoryview, start: int, end: int) -> int:
    """
    将 [start, end) 提取为 int, 空字符串返回 0.
    """
    s = _parse_string_field(buf, start, end)
    return int(s) if s else 0


def _parse_float_field(buf: memoryview, start: int, end: int) -> float:
    """
    将 [start, end) 提取为 float, 空字符串返回 0.0.
    """
    s = _parse_string_field(buf, start, end)
    return float(s) if s else 0.0


def decode_all_file(path: Path) -> CurrentData:
    """
    解析单个 .all 文件.

    输入:
    - path: .all 文件路径.

    输出:
    - CurrentData 实例, 包含头部字段与三相波形.

    异常:
    - IOError / OSError: 文件读写错误.
    - ValueError: 格式不符合预期.
    """
    raw = path.read_bytes()
    if not raw:
        raise IOError(f"文件为空: {path}")
    if len(raw) > MAX_DATA_LENGTH:
        raise IOError(f"文件过大(>{MAX_DATA_LENGTH} bytes): {path}")

    buf = memoryview(raw)

    # 1. 在前 80 字节内寻找 16 个空格位置
    pos = []
    limit = min(80, len(buf))
    for i in range(limit):
        if buf[i] == ord(" "):
            pos.append(i)
            if len(pos) == 16:
                break
    if len(pos) < 16:
        raise ValueError(f"头部格式异常: 未找到 16 个空格, 文件={path}")

    start = pos[15] + 2  # 对应 C/Java 中 pos[15] + 2
    if start >= len(buf):
        raise ValueError(f"数据区起始位置超出文件长度, 文件={path}")

    # 2. 解析头部字段
    station = _parse_int_field(buf, 0, pos[0])
    line = _parse_int_field(buf, pos[0], pos[1])
    year = _parse_int_field(buf, pos[1], pos[2])
    month = _parse_int_field(buf, pos[2], pos[3])
    day = _parse_int_field(buf, pos[3], pos[4])
    hour = _parse_int_field(buf, pos[4], pos[5])
    minute = _parse_int_field(buf, pos[5], pos[6])
    second = _parse_int_field(buf, pos[6], pos[7])

    micro_second = _parse_string_field(buf, pos[7], pos[8])
    gps_frequency = _parse_string_field(buf, pos[8], pos[9])

    gps_flag = _parse_int_field(buf, pos[9], pos[10])
    break_flag = _parse_int_field(buf, pos[10], pos[11])
    startup_type = _parse_int_field(buf, pos[11], pos[12])
    startup_value1 = _parse_float_field(buf, pos[12], pos[13])
    startup_value2 = _parse_float_field(buf, pos[13], pos[14])
    startup_value3 = _parse_float_field(buf, pos[14], pos[15])

    # 3. 解析数据区
    raw_data = buf[start:]
    raw_len = len(raw_data)
    if raw_len <= 0:
        raise ValueError(f"数据点数为 0, 文件={path}")

    data_length = raw_len // 6  # 每点 3 相 * 2 字节
    if data_length <= 0:
        raise ValueError(f"数据点数为 0, 文件={path}")

    # 使用 numpy 数组便于后续数值运算
    data_a = np.zeros(data_length + 150, dtype=float)
    data_b = np.zeros(data_length + 150, dtype=float)
    data_c = np.zeros(data_length + 150, dtype=float)

    if data_length < 32769:
        # 12bit 编码, 与 C/Java 解码公式一致
        for i in range(data_length):
            base = i * 6
            a0 = raw_data[base]
            a1 = raw_data[base + 1]
            b0 = raw_data[base + 2]
            b1 = raw_data[base + 3]
            c0 = raw_data[base + 4]
            c1 = raw_data[base + 5]

            data_a[i] = ((a1 & 0x0F) << 8 | a0) - 0x800
            data_b[i] = ((b1 & 0x0F) << 8 | b0) - 0x800
            data_c[i] = ((c1 & 0x0F) << 8 | c0) - 0x800
    else:
        # 16bit 小端短整型
        for i in range(data_length):
            base = i * 6
            a = int.from_bytes(raw_data[base:base + 2], byteorder="little", signed=True)
            b = int.from_bytes(raw_data[base + 2:base + 4], byteorder="little", signed=True)
            c = int.from_bytes(raw_data[base + 4:base + 6], byteorder="little", signed=True)
            data_a[i] = a
            data_b[i] = b
            data_c[i] = c

    return CurrentData(
        station=station,
        line=line,
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        micro_second=micro_second,
        gps_frequency=gps_frequency,
        gps_flag=gps_flag,
        break_flag=break_flag,
        startup_type=startup_type,
        startup_value1=startup_value1,
        startup_value2=startup_value2,
        startup_value3=startup_value3,
        data_length=data_length,
        data_a=data_a.tolist(),
        data_b=data_b.tolist(),
        data_c=data_c.tolist(),
        file_name=path.name,
    )
