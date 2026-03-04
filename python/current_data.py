from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class CurrentData:
    """
    保存一次 .all 文件解析得到的头部信息和三相波形数据.
    作为后续波头识别与故障测距算法的标准输入数据结构.
    """
    station: int
    line: int
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int

    micro_second: str
    gps_frequency: str

    gps_flag: int
    break_flag: int
    startup_type: int
    startup_value1: float
    startup_value2: float
    startup_value3: float

    data_length: int
    # 【优化】使用 numpy 数组替代 List
    data_a: np.ndarray 
    data_b: np.ndarray
    data_c: np.ndarray

    file_name: str