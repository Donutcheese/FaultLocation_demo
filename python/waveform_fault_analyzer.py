from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import find_peaks

from current_data import CurrentData
from fault_location_algorithms import (
    sample_index_to_time_ms,
    single_end_by_two_wave_times,
)


class Phase(enum.Enum):
    """
    相别枚举.

    A/B/C 三相.
    """

    A = "A"
    B = "B"
    C = "C"


@dataclass
class AnalyzerConfig:
    """
    单端测距配置参数.

    字段:
    - sampling_interval_ms: 采样间隔, ms.
    - wave_speed_km_per_ms: 行波速度, km/ms.
    - line_length_km: 线路长度, km.
    - min_prominence: 波头检测最小突出度.
    - min_distance_samples: 邻近峰之间的最小样本间隔.
    """

    sampling_interval_ms: float = 0.01
    wave_speed_km_per_ms: float = 200.0
    line_length_km: float = 300.0
    min_prominence: float = 20.0
    min_distance_samples: int = 100


@dataclass
class SingleEndResult:
    """
    单端测距分析结果.

    字段:
    - file_name: 源 .all 文件名.
    - phase: 使用的相别.
    - first_index/second_index: 入射波与反射波峰值索引.
    - first_time_ms/second_time_ms: 对应时间, ms.
    - distance_km: 距测量端的距离, km.
    - config: 使用的配置.
    """

    file_name: str
    phase: Phase
    first_index: int
    second_index: int
    first_time_ms: float
    second_time_ms: float
    distance_km: float
    config: AnalyzerConfig


def _select_phase_data(df: CurrentData, phase: Phase) -> np.ndarray:
    """
    根据相别选择一相波形并转换为 numpy 数组.
    """
    if phase == Phase.B:
        data = df.data_b
    elif phase == Phase.C:
        data = df.data_c
    else:
        data = df.data_a
    return np.asarray(data[: df.data_length], dtype=float)


def analyze_single_end(df: CurrentData, cfg: AnalyzerConfig, phase: Phase) -> Optional[SingleEndResult]:
    """
    使用 scipy.signal.find_peaks 对指定相别做单端故障测距分析.

    输入:
    - df: 解析后的 CurrentData.
    - cfg: 分析和测距配置.
    - phase: 相别 A/B/C.

    输出:
    - SingleEndResult, 若未能找到合适的入射波与反射波则返回 None.
    """
    x = _select_phase_data(df, phase)
    n = len(x)
    if n < 10:
        return None

    # 1. 使用差分信号增强波头, 减少直流分量影响
    dx = np.diff(x)

    # 2. 使用 scipy.signal.find_peaks 寻找显著峰值
    #    prominence 控制“峰的突出度”, distance 控制最小间隔
    peaks, props = find_peaks(np.abs(dx), prominence=cfg.min_prominence, distance=cfg.min_distance_samples)
    if len(peaks) < 2:
        return None

    # 3. 选取前两个显著峰作为入射波与反射波
    #    可根据应用需求更精细筛选
    first_index = int(peaks[0]) + 1  # diff 后索引与原信号对齐, 故 +1
    second_index = int(peaks[1]) + 1

    t1_ms = sample_index_to_time_ms(first_index, cfg.sampling_interval_ms)
    t2_ms = sample_index_to_time_ms(second_index, cfg.sampling_interval_ms)
    distance_km = single_end_by_two_wave_times(cfg.wave_speed_km_per_ms, t1_ms, t2_ms)

    return SingleEndResult(
        file_name=df.file_name,
        phase=phase,
        first_index=first_index,
        second_index=second_index,
        first_time_ms=t1_ms,
        second_time_ms=t2_ms,
        distance_km=distance_km,
        config=cfg,
    )

