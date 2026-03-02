from __future__ import annotations

from dataclasses import dataclass


def double_end_by_times(
    line_length_km: float,
    wave_speed_km_per_ms: float,
    t_a_ms: float,
    t_b_ms: float,
) -> "DoubleEndResult":
    """
    双端行波故障测距.

    数学关系:
    - tA = d / v
    - tB = (L - d) / v
    - d = (L + v * (tA - tB)) / 2

    输入:
    - line_length_km: 线路总长度 L, km.
    - wave_speed_km_per_ms: 行波速度 v, km/ms.
    - t_a_ms: A 端到达时间 tA, ms.
    - t_b_ms: B 端到达时间 tB, ms.

    输出:
    - DoubleEndResult, 包含距 A 端和距 B 端的距离, km.
    """
    L = line_length_km
    v = wave_speed_km_per_ms
    d_from_a = (L + v * (t_a_ms - t_b_ms)) / 2.0
    d_from_a = max(0.0, min(L, d_from_a))
    d_from_b = L - d_from_a
    return DoubleEndResult(distance_from_a=d_from_a, distance_from_b=d_from_b)


def single_end_by_two_wave_times(
    wave_speed_km_per_ms: float,
    t1_ms: float,
    t2_ms: float,
) -> float:
    """
    单端行波故障测距.

    数学关系:
    - d ≈ v * (t2 - t1) / 2

    输入:
    - wave_speed_km_per_ms: 行波速度 v, km/ms.
    - t1_ms: 入射波到达时间 t1, ms.
    - t2_ms: 反射波到达时间 t2, ms.

    输出:
    - 距测量端的距离 d, km; 若 t2 <= t1 返回 0.0.
    """
    dt = t2_ms - t1_ms
    if dt <= 0.0:
        return 0.0
    return wave_speed_km_per_ms * dt / 2.0


def sample_index_to_time_ms(sample_index: int, sampling_interval_ms: float) -> float:
    """
    将采样点序号转换为时间.

    输入:
    - sample_index: 采样点序号, 从 0 开始.
    - sampling_interval_ms: 采样间隔, ms.

    输出:
    - 时间 t = sample_index * 采样间隔, ms.
    """
    return sample_index * sampling_interval_ms


@dataclass(frozen=True)
class DoubleEndResult:
    """
    双端行波测距结果数据结构.

    字段:
    - distance_from_a: 故障点到 A 端距离, km.
    - distance_from_b: 故障点到 B 端距离, km.
    """

    distance_from_a: float
    distance_from_b: float

