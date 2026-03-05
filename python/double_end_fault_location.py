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
    sampling_interval_ms: float = 0.001     # 采样间隔 (ms)，对应 1MHz 高频录波
    wave_speed_km_per_ms: float = 299.79    # 行波速度内部单位 km/ms (≈ 2.9979e8 m/s)
    line_length_km: float = 1000.0           # 测试阶段默认 1000km
    first_wave_sigma: float = 4.0            # 波头检测显著性阈值系数

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
    return np.asarray(data[: df.data_length], dtype=np.float64)


# ---------------------------------------------------------------------------
#  小波多尺度滤波（去噪）
# ---------------------------------------------------------------------------

def _wavelet_denoise(signal: np.ndarray, wavelet: str = "db4", level: int = 4) -> np.ndarray:
    """
    4 尺度小波多尺度滤波 (VisuShrink 软阈值去噪).
    - 使用 MAD 估计噪声标准差
    - 通用阈值 (Universal Threshold): σ√(2 ln n)
    - 软阈值处理细节系数，保留近似系数
    """
    n = len(signal)
    max_level = pywt.dwt_max_level(n, pywt.Wavelet(wavelet).dec_len)
    actual_level = min(level, max_level)
    if actual_level < 1:
        return signal.copy()

    coeffs = pywt.wavedec(signal, wavelet, level=actual_level)

    # MAD (Median Absolute Deviation) 估计噪声标准差
    sigma = np.median(np.abs(coeffs[-1])) / 0.6745
    if sigma < 1e-12:
        return signal.copy()

    threshold = sigma * np.sqrt(2.0 * np.log(n))

    denoised_coeffs = [coeffs[0]]  # 近似系数保持不变
    for detail in coeffs[1:]:
        denoised_coeffs.append(pywt.threshold(detail, threshold, mode="soft"))

    rec = pywt.waverec(denoised_coeffs, wavelet)
    return rec[:n]


# ---------------------------------------------------------------------------
#  波头首达模极大值检测
# ---------------------------------------------------------------------------

def _find_first_peak(detail: np.ndarray, scale_factor: int, shift: int,
                     n: int, sigma_mult: float = 4.0) -> int:
    """
    在小波细节系数中寻找 **第一个** 显著模极大值点（而非全局最大），
    更准确地对应行波首达时刻。
    """
    abs_d = np.abs(detail)
    sigma = np.median(abs_d) / 0.6745
    threshold = sigma_mult * sigma

    if threshold < 1e-12:
        peak_max = np.max(abs_d)
        threshold = peak_max * 0.1 if peak_max > 1e-12 else 0.0

    above = np.where(abs_d > threshold)[0]

    if len(above) == 0:
        coeff_idx = int(np.argmax(abs_d))
    else:
        # 在首次过阈值附近寻找局部峰值，取最精确位置
        start = above[0]
        search_end = min(start + 5, len(abs_d))
        local_region = abs_d[start:search_end]
        coeff_idx = start + int(np.argmax(local_region))

    original_idx = coeff_idx * scale_factor - shift
    return max(0, min(n - 1, original_idx))


# ---------------------------------------------------------------------------
#  跨尺度一致性校验
# ---------------------------------------------------------------------------

def _cross_scale_select(indices: list[int], cfg_interval_ms: float,
                        tolerance_ms: float = 0.05) -> int:
    """
    跨 4 个尺度进行一致性校验：
    以尺度 1（最高分辨率）为基准，若与尺度 2/3 的偏差在容限内则直接采用；
    否则取偏差最小的两个尺度的均值。
    """
    idx1, idx2, idx3, idx4 = indices
    tol_samples = tolerance_ms / cfg_interval_ms if cfg_interval_ms > 0 else 50

    d12 = abs(idx1 - idx2)
    d13 = abs(idx1 - idx3)

    if d12 <= tol_samples or d13 <= tol_samples:
        return idx1

    diffs = [(abs(indices[i] - indices[j]), i, j)
             for i in range(4) for j in range(i + 1, 4)]
    diffs.sort()
    best_i, best_j = diffs[0][1], diffs[0][2]
    return (indices[best_i] + indices[best_j]) // 2


# ---------------------------------------------------------------------------
#  单端波头检测主函数
# ---------------------------------------------------------------------------

def analyze_single_end(df: CurrentData, cfg: AnalyzerConfig, phase: Phase) -> Optional[SingleEndResult]:
    """
    多尺度小波变换波头检测 (含预滤波 + 相移补偿 + 跨尺度校验).

    流程:
      1. 小波多尺度滤波去噪 (VisuShrink, 4 尺度 db4)
      2. 对去噪信号进行 4 尺度 db4 分解
      3. 各尺度寻找首达模极大值 + 群延迟补偿
      4. 跨尺度一致性校验，选出最可靠到达时刻
    """
    x = _select_phase_data(df, phase)
    n = len(x)
    if n < 32:
        return None

    # 1. 小波多尺度滤波去噪
    x_filtered = _wavelet_denoise(x, "db4", 4)

    # 2. 4 尺度 db4 分解
    max_level = pywt.dwt_max_level(n, pywt.Wavelet("db4").dec_len)
    actual_level = min(4, max_level)
    if actual_level < 1:
        return None

    coeffs = pywt.wavedec(x_filtered, "db4", level=actual_level)

    # 根据实际分解层数提取系数（不足 4 层时自适应）
    num_details = len(coeffs) - 1
    details = list(reversed(coeffs[1:]))  # [cD1, cD2, ..., cDn] 从细到粗
    scale_factors = [2 ** i for i in range(1, num_details + 1)]
    shifts = [3, 10, 24, 52][:num_details]

    # 3. 各尺度寻找首达模极大值
    indices = []
    for i in range(num_details):
        idx = _find_first_peak(
            details[i], scale_factors[i], shifts[i], n,
            sigma_mult=cfg.first_wave_sigma,
        )
        indices.append(idx)

    # 补齐到 4 个（不足时复制最后一个）
    while len(indices) < 4:
        indices.append(indices[-1])

    # 4. 跨尺度一致性校验
    first_index = _cross_scale_select(indices, cfg.sampling_interval_ms)
    final_time_ms = sample_index_to_time_ms(first_index, cfg.sampling_interval_ms)

    return SingleEndResult(
        file_name=df.file_name, phase=phase,
        first_index=first_index, second_index=indices[0],
        first_time_ms=final_time_ms, second_time_ms=sample_index_to_time_ms(indices[0], cfg.sampling_interval_ms),
        distance_km=0.0, config=cfg,
    )

def calculate_absolute_arrival_time(df: CurrentData, relative_time_ms: float) -> float:
    """将头文件基准时间和相对时间融合成全网唯一的毫秒级绝对时间戳"""
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