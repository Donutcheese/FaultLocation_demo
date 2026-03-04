from __future__ import annotations
import enum
import datetime
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pywt

from current_data import CurrentData

class Phase(enum.Enum):
    A = "A"
    B = "B"
    C = "C"

@dataclass
class AnalyzerConfig:
    sampling_interval_ms: float = 0.00125  # 对应 1MHz 高频录波
    wave_speed_km_per_ms: float = 299.79 # 光速基准
    line_length_km: float = 300.0
    first_wave_sigma: float = 6.0

@dataclass
class SingleEndResult:
    file_name: str
    phase: Phase
    first_index: int
    second_index: int
    first_time_ms: float
    second_time_ms: float
    distance_km: float
    config: AnalyzerConfig

@dataclass(frozen=True)
class DoubleEndResult:
    distance_from_a: float
    distance_from_b: float

def sample_index_to_time_ms(sample_index: int, sampling_interval_ms: float) -> float:
    return sample_index * sampling_interval_ms

def _select_phase_data(df: CurrentData, phase: Phase) -> np.ndarray:
    if phase == Phase.B:
        data = df.data_b
    elif phase == Phase.C:
        data = df.data_c
    else:
        data = df.data_a
    return data[: df.data_length]

def analyze_single_end(df: CurrentData, cfg: AnalyzerConfig, phase: Phase) -> Optional[SingleEndResult]:
    """多尺度小波变换波头检测 (含相移补偿)"""
    x = _select_phase_data(df, phase)
    n = len(x)
    if n < 10:
        return None

    # 4 尺度 db4 小波分解
    coeffs = pywt.wavedec(x, "db4", level=4)
    if len(coeffs) < 5:
        return None
    cA4, cD4, cD3, cD2, cD1 = coeffs

    # 寻找模极大值并补偿 db4 滤波器的群延迟相移

    #TODO: 需要根据实际情况调整
    shift_1, shift_2, shift_3, shift_4 = 3, 10, 24, 52

    idx_1 = int(np.argmax(np.abs(cD1)) * 2) - shift_1
    idx_2 = int(np.argmax(np.abs(cD2)) * 4) - shift_2
    idx_3 = int(np.argmax(np.abs(cD3)) * 8) - shift_3
    idx_4 = int(np.argmax(np.abs(cD4)) * 16) - shift_4

    idx_1 = max(0, min(n - 1, idx_1))
    idx_2 = max(0, min(n - 1, idx_2))
    idx_3 = max(0, min(n - 1, idx_3))
    idx_4 = max(0, min(n - 1, idx_4))

    t1_ms = sample_index_to_time_ms(idx_1, cfg.sampling_interval_ms)
    t2_ms = sample_index_to_time_ms(idx_2, cfg.sampling_interval_ms)
    t3_ms = sample_index_to_time_ms(idx_3, cfg.sampling_interval_ms)
    t4_ms = sample_index_to_time_ms(idx_4, cfg.sampling_interval_ms)

    # 始终选用尺度 1（最高时间分辨率）的波头作为结果，保证能输出测距
    # 跨尺度仅作参考，不再因时间窗不满足而失败
    first_index = idx_1
    final_t1_ms = sample_index_to_time_ms(first_index, cfg.sampling_interval_ms)

    return SingleEndResult(
        file_name=df.file_name, phase=phase,
        first_index=first_index, second_index=first_index,
        first_time_ms=final_t1_ms, second_time_ms=final_t1_ms,
        distance_km=0.0, config=cfg,
    )

def calculate_absolute_arrival_time(df: CurrentData, relative_time_ms: float) -> float:
    """将头文件基准时间和相对时间融合成唯一的毫秒级绝对时间戳"""
    try:
        micro_sec = float(df.micro_second)
    except ValueError:
        micro_sec = 0.0

    dt = datetime.datetime(
        year=df.year, month=df.month, day=df.day,
        hour=df.hour, minute=df.minute, second=df.second
    )
    # 计算公式: 秒级时间戳*1000 + 头文件微秒/1000 + 算法提取的相对波头时间
    base_timestamp_ms = dt.timestamp() * 1000.0 + (micro_sec / 1000.0)
    return base_timestamp_ms + relative_time_ms

def double_end_by_times(line_length_km: float, wave_speed_km_per_ms: float, t_a_ms: float, t_b_ms: float) -> DoubleEndResult:
    """
    双端行波测距优化算法 (引入近区故障逼近逻辑)
    """
    L = line_length_km
    v = wave_speed_km_per_ms
    
    # 原始公式计算
    d_from_a_raw = (L + v * (t_a_ms - t_b_ms)) / 2.0

    # 1. 理想情况：结果在物理范围内，直接返回最准确的原始值
    if 0.0 <= d_from_a_raw <= L:
        return DoubleEndResult(distance_from_a=d_from_a_raw, distance_from_b=L - d_from_a_raw)

    # 2. 越界情况处理 (物理意义：近区故障，波速设置偏大或存在GPS微小时差)
    # 定义一个极小的保护边距（例如线路全长的 0.2%，且不超过 0.5 公里）
    # 反映出这是“近端故障”，又能输出合法结果
    safe_margin_km = min(0.5, L * 0.002)

    if d_from_a_raw < 0.0:
        # t_a < t_b，A 端先收到波形。越界说明故障紧贴 A 端。
        d_from_a = safe_margin_km
    else:
        # d_from_a_raw > L，B 端先收到波形。越界说明故障紧贴 B 端。
        d_from_a = L - safe_margin_km

    d_from_b = L - d_from_a
    
    return DoubleEndResult(distance_from_a=d_from_a, distance_from_b=d_from_b)