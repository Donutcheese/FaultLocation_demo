from __future__ import annotations
from pathlib import Path
import numpy as np

from current_data import CurrentData

MAX_DATA_LENGTH = 512 * 1024  # 与 C/Java 实现一致

def _parse_string_field(buf: memoryview, start: int, end: int) -> str:
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
    s = _parse_string_field(buf, start, end)
    return int(s) if s else 0

def _parse_float_field(buf: memoryview, start: int, end: int) -> float:
    s = _parse_string_field(buf, start, end)
    return float(s) if s else 0.0

def decode_all_file(path: Path) -> CurrentData:
    """解析单个 .all 文件 (NumPy 向量化极致优化版)"""
    raw = path.read_bytes()
    if not raw:
        raise IOError(f"文件为空: {path}")
    if len(raw) > MAX_DATA_LENGTH:
        raise IOError(f"文件过大(>{MAX_DATA_LENGTH} bytes): {path}")

    buf = memoryview(raw)

    # 1. 寻找头部结束位置 (16个空格)
    pos = []
    limit = min(80, len(buf))
    for i in range(limit):
        if buf[i] == ord(" "):
            pos.append(i)
            if len(pos) == 16:
                break
    if len(pos) < 16:
        raise ValueError(f"头部格式异常: 未找到 16 个空格, 文件={path}")

    start = pos[15] + 2
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

    # 3. 解析数据区（NumPy 零拷贝内存映射）
    raw_data = buf[start:]
    data_length = len(raw_data) // 6
    if data_length <= 0:
        raise ValueError(f"数据点数为 0, 文件={path}")
    
    # 截断多余的字节，确保长度是 6 的严格倍数
    valid_bytes = raw_data[:data_length * 6]

    if data_length < 32769:
        # --- 12bit 数据解码优化 ---
        raw_np = np.frombuffer(valid_bytes, dtype=np.uint8)
        
        # 提取各个字节并转为 int16 防止位移溢出
        a0 = raw_np[0::6].astype(np.int16)
        a1 = raw_np[1::6].astype(np.int16)
        b0 = raw_np[2::6].astype(np.int16)
        b1 = raw_np[3::6].astype(np.int16)
        c0 = raw_np[4::6].astype(np.int16)
        c1 = raw_np[5::6].astype(np.int16)

        # 向量化位运算
        data_a = ((a1 << 4) | a0) - 0x800
        data_b = ((b1 << 4) | b0) - 0x800
        data_c = ((c1 << 4) | c0) - 0x800
    else:
        # --- 16bit 小端短整型解码优化 ---
        # 直接按 int16 (小端 '<i2') 读取整块内存并重塑为 N行3列
        reshaped = np.frombuffer(valid_bytes, dtype='<i2').reshape(-1, 3)
        data_a = reshaped[:, 0].astype(float)
        data_b = reshaped[:, 1].astype(float)
        data_c = reshaped[:, 2].astype(float)

    # 尾部安全区补齐 (原代码逻辑)
    data_a = np.pad(data_a, (0, 150), 'constant').astype(float)
    data_b = np.pad(data_b, (0, 150), 'constant').astype(float)
    data_c = np.pad(data_c, (0, 150), 'constant').astype(float)

    return CurrentData(
        station=station, line=line, year=year, month=month, day=day,
        hour=hour, minute=minute, second=second, micro_second=micro_second,
        gps_frequency=gps_frequency, gps_flag=gps_flag, break_flag=break_flag,
        startup_type=startup_type, startup_value1=startup_value1,
        startup_value2=startup_value2, startup_value3=startup_value3,
        data_length=data_length,
        data_a=data_a, data_b=data_b, data_c=data_c, # 直接传入 NumPy 数组
        file_name=path.name
    )