from __future__ import annotations

from pathlib import Path
from datetime import datetime
import tempfile
from typing import Optional

# 请确保这些模块与您本地的文件名和类名完全对应
from all_file_decoder import decode_all_file
from double_end_fault_location import (
    AnalyzerConfig,
    Phase,
    analyze_single_end,
    double_end_by_times,
)
from nicegui import ui, events


def _micro_to_int(micro_raw: str) -> int:
    """将头字段中的“微秒字符串”转换为整数微秒, 保留 6 位精度."""
    s = micro_raw.strip()
    if not s:
        return 0
    val: int
    try:
        if "." in s:
            micro_val = float(s)
            val = int(round(micro_val * 10.0))
        else:
            val = int(s)
    except ValueError:
        digits = "".join(ch for ch in s if ch.isdigit())
        if not digits:
            return 0
        if len(digits) > 6:
            digits = digits[:6]
        val = int(digits)
        
    if val < 0:
        return 0
    if val > 999_999:
        return 999_999
    return val


def _format_timestamp(df) -> str:
    """将头字段中的时间格式化为小数点后 6 位."""
    micro_int = _micro_to_int(str(df.micro_second))
    micro_str = f"{micro_int:06d}"
    return (
        f"{df.year:04d}-{df.month:02d}-{df.day:02d} "
        f"{df.hour:02d}:{df.minute:02d}:{df.second:02d}.{micro_str}"
    )


def _header_to_datetime(df) -> datetime:
    """将 CurrentData 头字段转换为标准 datetime 对象."""
    micro_int = _micro_to_int(str(df.micro_second))
    return datetime(
        df.year, df.month, df.day, 
        df.hour, df.minute, df.second, micro_int
    )


def _print_summary(df) -> None:
    """打印 .all 文件概要信息"""
    print(f"站号: {df.station}, 线路: {df.line}")
    print(f"日期时间: {_format_timestamp(df)}")
    print(f"数据点数: {df.data_length}")
    print(f"GPS频率: {df.gps_frequency}, GPS标志: {df.gps_flag}, 跳闸标志: {df.break_flag}")
    if df.data_length > 0:
        peak_a = max(abs(float(v)) for v in df.data_a[: df.data_length])
        peak_b = max(abs(float(v)) for v in df.data_b[: df.data_length])
        peak_c = max(abs(float(v)) for v in df.data_c[: df.data_length])
        print(f"峰值(A/B/C): {peak_a:.3f}, {peak_b:.3f}, {peak_c:.3f}")
    n = min(df.data_length, 10)
    print(f"前 {n} 个 A 相数据:")
    for i in range(n):
        print(f"  A[{i}] = {df.data_a[i]}")


def _ask_phase() -> Phase:
    """从标准输入读取 A/B/C, 默认返回 A."""
    try:
        s = input("请选择测距相别 (A/B/C), 直接回车默认为 A 相: ").strip().upper()
    except EOFError:
        return Phase.A
    if not s:
        return Phase.A
    if s[0] == "B": return Phase.B
    if s[0] == "C": return Phase.C
    return Phase.A


def main() -> int:
    """
    Python 版本命令行入口函数.
    行为: 解析文件 -> 打印概要 -> 询问相别 -> 运行单端波头检测算法 -> 输出结果.
    """
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    data_dir = project_root / "src" / "data"

    if not data_dir.exists():
        data_dir = Path("data").resolve()

    filename = input(f"请输入 data 目录下的文件名 (位于 {data_dir}): ").strip()
    if not filename:
        print("未输入文件名")
        return 1

    path = data_dir / filename
    if not path.exists():
        print(f"文件不存在: {path}")
        return 1

    # 1. 解析文件
    try:
        df = decode_all_file(path)
    except Exception as e:
        print(f"解析文件失败: {e}")
        return 1
        
    print(f"\n=== 解析指定 .all 文件 ===")
    print(f"目标文件: {path.resolve()}")
    _print_summary(df)

    # 2. 运行单端测距/波头检测算法
    phase = _ask_phase()
    
    # 采用默认配置 (1MHz采样率, 300km/ms波速)
    cfg = AnalyzerConfig(
        sampling_interval_ms=0.001, 
        wave_speed_km_per_ms=299.79, 
        line_length_km=300.0
    )
    
    print("\n🚀 正在运行多尺度小波变换波头检测...")
    result = analyze_single_end(df, cfg, phase)
    
    if result:
        print("\n✅ 波头检测成功！")
        print(f"👉 检出相别: {result.phase.value}")
        print(f"👉 突变点索引: {result.first_index}")
        print(f"👉 相对到达时间: {result.first_time_ms:.6f} ms")
    else:
        print("\n❌ 波头检测失败：未能找到符合跨尺度校验的有效故障行波。")

    return 0


def run_gui() -> None:
    """基于 NiceGUI 的图形化前端（包含完整双端测距闭环逻辑）."""

    # 浅色主题
    ui.colors(primary="#1565c0", secondary="#90caf9", accent="#1e88e5", dark=False)
    ui.add_head_html(
        """
        <style>
        body {
            margin: 0;
            background: #f3f4f6; /* 整体浅灰背景 */
            color: #111827;
            font-family: system-ui, -apple-system, sans-serif;
        }
        </style>
        """
    )

    uploaded_a_bytes: Optional[bytes] = None
    uploaded_b_bytes: Optional[bytes] = None
    df_a_cache = None  
    df_b_cache = None  

    # 算法默认参数
    sampling_rate_khz: float = 1250.0  # 1MHz 
    time_window_us: float = 4000.0  
    line_length_km: float = 300.0  
    wave_speed_km_per_s: float = 299.79  

    summary_a_label = None  
    summary_b_label = None  
    info_label = None  

    sr_input, tw_input, L_input, v_input = None, None, None, None

    async def on_upload_a(e: events.UploadEventArguments) -> None:
        nonlocal uploaded_a_bytes, summary_a_label
        try:
            # 使用 NiceGUI 官方推荐的 e.file.read() 读取字节内容
            uploaded_a_bytes = await e.file.read()
        except Exception as exc:  # noqa: BLE001
            uploaded_a_bytes = None
            ui.notify(f"A 端文件读取失败: {exc}", color="negative")
            return
        if summary_a_label is not None:
            name = getattr(e.file, "name", None) or getattr(e, "name", "")
            summary_a_label.text = f"已加载 A 端文件: {name}"

    async def on_upload_b(e: events.UploadEventArguments) -> None:
        nonlocal uploaded_b_bytes, summary_b_label
        try:
            uploaded_b_bytes = await e.file.read()
        except Exception as exc:  # noqa: BLE001
            uploaded_b_bytes = None
            ui.notify(f"B 端文件读取失败: {exc}", color="negative")
            return
        if summary_b_label is not None:
            name = getattr(e.file, "name", None) or getattr(e, "name", "")
            summary_b_label.text = f"已加载 B 端文件: {name}"

    def _build_summary_text(df, side: str) -> str:
        lines = [
            f"{side} 端 | 站号: {df.station}, 线路: {df.line}",
            f"{side} 端 | 日期时间: {_format_timestamp(df)}",
            f"{side} 端 | 数据点数: {df.data_length}",
            f"{side} 端 | GPS同步: {'是' if df.gps_flag == 1 else '否 (警告: 失步)'}",
        ]
        if df.data_length > 0:
            peak_a = max(abs(float(v)) for v in df.data_a[: df.data_length])
            peak_b = max(abs(float(v)) for v in df.data_b[: df.data_length])
            peak_c = max(abs(float(v)) for v in df.data_c[: df.data_length])
            lines.append(
                f"{side} 端 | 峰值(A/B/C): {peak_a:.3f}, {peak_b:.3f}, {peak_c:.3f}"
            )
        return "\n".join(lines)

    def on_parse_click() -> None:
        nonlocal uploaded_a_bytes, uploaded_b_bytes, summary_a_label, summary_b_label, info_label, df_a_cache, df_b_cache

        if not uploaded_a_bytes:
            ui.notify("请先选择 A 端 .all 文件", color="negative")
            return
        if not uploaded_b_bytes:
            ui.notify("请先选择 B 端 .all 文件", color="negative")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".all") as tmp_a:
            tmp_a.write(uploaded_a_bytes)
            tmp_a_path = Path(tmp_a.name)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".all") as tmp_b:
            tmp_b.write(uploaded_b_bytes)
            tmp_b_path = Path(tmp_b.name)

        try:
            df_a_cache = decode_all_file(tmp_a_path)
            if summary_a_label: summary_a_label.text = _build_summary_text(df_a_cache, "A")
        except Exception as exc:  
            ui.notify(f"A 端解析失败: {exc}", color="negative")

        try:
            df_b_cache = decode_all_file(tmp_b_path)
            if summary_b_label: summary_b_label.text = _build_summary_text(df_b_cache, "B")
        except Exception as exc:  
            ui.notify(f"B 端解析失败: {exc}", color="negative")

        if info_label:
            info_label.text = "解析完成。请点击“运行”执行测距算法。"

    def on_save_params() -> None:
        nonlocal sampling_rate_khz, time_window_us, line_length_km, wave_speed_km_per_s
        try:
            if sr_input and sr_input.value: sampling_rate_khz = float(sr_input.value)
            if tw_input and tw_input.value: time_window_us = float(tw_input.value)
            if L_input and L_input.value: line_length_km = float(L_input.value)
            if v_input and v_input.value: wave_speed_km_per_s = float(v_input.value)
            ui.notify("算法参数已更新。", color="positive")
        except ValueError:
            ui.notify("参数格式错误。", color="negative")

    def on_run_click() -> None:
        """运行双端测距 (包含绝对时间对齐的核心修正)"""
        nonlocal df_a_cache, df_b_cache, line_length_km, wave_speed_km_per_s, sampling_rate_khz, info_label

        if df_a_cache is None or df_b_cache is None:
            ui.notify("请先完成解析，再运行双端测距。", color="warning")
            return
            
        # 风险提示：如果 GPS 未同步，双端算出来的数据没有意义
        if df_a_cache.gps_flag != 1 or df_b_cache.gps_flag != 1:
            ui.notify("警告：检测到文件 GPS 未同步，测距结果可能存在偏差！", color="warning")

        # 1. 配置准备
        sampling_interval_ms = 1.0 / float(sampling_rate_khz) if sampling_rate_khz > 0 else 0.001
        wave_speed_km_per_ms = wave_speed_km_per_s / 1000.0

        cfg = AnalyzerConfig(
            sampling_interval_ms=sampling_interval_ms,
            wave_speed_km_per_ms=wave_speed_km_per_ms,
            line_length_km=line_length_km,
        )

        # 2. 对两端分别做波头检测
        res_a = analyze_single_end(df_a_cache, cfg, Phase.A)
        res_b = analyze_single_end(df_b_cache, cfg, Phase.A)

        if not res_a or not res_b:
            msg = "波头识别失败！请检查波形或调整容错时间窗。"
            ui.notify(msg, color="negative")
            if info_label: info_label.text = msg
            return

        # 3. 将头文件时间与波头相对时间融合，计算真正的全网时间差
        dt_a = _header_to_datetime(df_a_cache)
        dt_b = _header_to_datetime(df_b_cache)
        
        # 计算头文件的绝对时间差 (毫秒)
        header_diff_ms = (dt_a - dt_b).total_seconds() * 1000.0
        # 计算波头的相对时间差 (毫秒)
        relative_diff_ms = res_a.first_time_ms - res_b.first_time_ms
        
        # 全局真正的时差: tA - tB
        total_delta_ms = header_diff_ms + relative_diff_ms

        # 巧妙复用您的 double_end_by_times 函数：直接将差值传入 tA，让 tB = 0
        result = double_end_by_times(
            line_length_km=line_length_km,
            wave_speed_km_per_ms=wave_speed_km_per_ms,
            t_a_ms=total_delta_ms,
            t_b_ms=0.0,
        )

        later_side = "A" if total_delta_ms >= 0 else "B"

        summary_lines = [
            "双端行波测距计算完毕:",
            f"- 线路全长 L = {line_length_km:.3f} km",
            f"- 行波速度 v = {wave_speed_km_per_s:.1f} km/s",
            f"- A 端到达时刻 (绝对参考): {_format_timestamp(df_a_cache)} + {res_a.first_time_ms:.4f} ms",
            f"- B 端到达时刻 (绝对参考): {_format_timestamp(df_b_cache)} + {res_b.first_time_ms:.4f} ms",
            f"- 全网同步时间差 (tA - tB) = {total_delta_ms:.6f} ms (靠后端为 {later_side} 端)",
            "--------------------------------------------------",
            f"最终定位结果: 距 A 端 {result.distance_from_a:.3f} km, 距 B 端 {result.distance_from_b:.3f} km"
        ]

        if info_label:
            info_label.text = "\n".join(summary_lines)
        ui.notify("双端测距成功定位！", color="positive")


    # --- UI 布局构建 ---
    with ui.column().classes("items-stretch justify-center min-h-screen").style("padding: 24px 16px;"):
        with ui.card().classes("w-full q-pa-xl").style(
            "max-width: 1300px; margin: 24px auto; background: rgba(255, 255, 255, 0.9); "
            "backdrop-filter: blur(18px); border-radius: 24px; "
            "border: 1px solid rgba(148, 163, 184, 0.6); color: #111827;"
        ):
            ui.label("行波故障测距分析 · 双端模式").classes("text-h5 text-weight-bold")
            ui.label("上传两端 .all 数据文件，通过多尺度小波变换联合定位故障点。").classes("text-body2 q-mb-md")

            with ui.row().classes("items-end q-gutter-md q-mt-md"):
                ui.upload(label="A 端 .all 文件", max_files=1, auto_upload=True, on_upload=on_upload_a).props("accept=.all color=primary flat bordered").classes("flex-grow-1")
                ui.upload(label="B 端 .all 文件", max_files=1, auto_upload=True, on_upload=on_upload_b).props("accept=.all color=primary flat bordered").classes("flex-grow-1")


            with ui.row().classes("items-center q-gutter-md q-mt-md"):
              
                sr_input = ui.number("采样率 (kHz)", value=sampling_rate_khz, format="%.1f").classes("w-32")
                tw_input = ui.number("时间窗 (µs)", value=time_window_us, format="%.1f").classes("w-32")
                L_input = ui.number("线路全长 L (km)", value=line_length_km, format="%.1f").classes("w-40")
                v_input = ui.number("行波速度 v (km/s)", value=wave_speed_km_per_s, format="%.1f").classes("w-48")
                ui.button("保存参数", on_click=on_save_params).props("color=primary flat rounded")

            with ui.row().classes("items-center q-gutter-md q-mt-sm"):
                ui.button("解析", on_click=on_parse_click).props("color=primary unelevated rounded").classes("q-px-lg")
                ui.button("运行", on_click=on_run_click).props("color=accent unelevated rounded").classes("q-px-lg")

            ui.separator().classes("q-my-md q-dark")

            with ui.row().classes("q-gutter-md"):
                with ui.column().classes("col"):
                    ui.label("A 端信息").classes("text-subtitle1 q-mb-xs")
                    summary_a_label = ui.label("等待上传...").classes("text-sm").style("white-space: pre-wrap;")
                with ui.column().classes("col"):
                    ui.label("B 端信息").classes("text-subtitle1 q-mb-xs")
                    summary_b_label = ui.label("等待上传...").classes("text-sm").style("white-space: pre-wrap;")

            ui.label("测距计算结果").classes("text-subtitle1 q-mt-lg q-mb-xs")
            info_label = ui.label("暂无数据。").classes("text-md").style(
                "white-space: pre-wrap; background: rgba(209, 213, 219, 0.6); "
                "padding: 16px; border-radius: 8px; width: 100%; font-family: monospace; color: #111827;"
            )

    ui.run(title="智能电网双端行波测距", reload=False, port=8002)


if __name__ == "__main__":
    # 默认启动 GUI。如果在服务器纯终端环境运行，可以将下面的 run_gui() 改为 main()。
    run_gui()