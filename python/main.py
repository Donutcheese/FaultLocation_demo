from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Optional

from all_file_decoder import decode_all_file
from waveform_fault_analyzer import (
    AnalyzerConfig,
    Phase,
    analyze_single_end,
)
from nicegui import ui, events


def _print_summary(df) -> None:
    """
    打印与 Java 版本类似的 .all 文件概要信息.
    """
    print(f"站号: {df.station}, 线路: {df.line}")
    print(
        "日期时间: "
        f"{df.year:04d}-{df.month:02d}-{df.day:02d} "
        f"{df.hour:02d}:{df.minute:02d}:{df.second:02d}.{df.micro_second}"
    )
    print(f"数据点数: {df.data_length}")
    print(f"GPS频率: {df.gps_frequency}, GPS标志: {df.gps_flag}, 跳闸标志: {df.break_flag}")
    n = min(df.data_length, 10)
    print(f"前 {n} 个 A 相数据:")
    for i in range(n):
        print(f"A[{i}] = {df.data_a[i]}")


def _ask_phase() -> Phase:
    """
    从标准输入读取 A/B/C, 默认返回 A.
    """
    try:
        s = input("请选择测距相别 (A/B/C), 直接回车默认为 A 相: ").strip().upper()
    except EOFError:
        return Phase.A
    if not s:
        return Phase.A
    ch = s[0]
    if ch == "B":
        return Phase.B
    if ch == "C":
        return Phase.C
    return Phase.A


def main() -> int:
    """
    Python 版本命令行入口函数.

    行为:
    - 输入 data 目录下的文件名.
    - 解析文件并打印概要信息.
    - 询问相别, 调用单端测距模块, 打印结果.
    """
    # 自动定位 data 目录 (假设在项目根目录 data)
    # 脚本位置: .../python/main.py -> 项目根目录: .../
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    data_dir = project_root / "src" / "data"

    if not data_dir.exists():
        # 回退: 尝试当前工作目录下的 data
        data_dir = Path("data").resolve()

    filename = input(f"请输入 data 目录下的文件名 (位于 {data_dir}): ").strip()
    if not filename:
        print("未输入文件名")
        return 1

    path = data_dir / filename
    if not path.exists():
        print(f"文件不存在: {path}")
        return 1

    df = decode_all_file(path)
    print(f"\n=== 解析并分析指定 .all 文件 ===")
    print(f"目标文件: {path.resolve()}")
    _print_summary(df)

    phase = _ask_phase()
    cfg = AnalyzerConfig()
    result = analyze_single_end(df, cfg, phase)
    if result is None:
        print("自动波头识别失败, 无法给出单端测距结果, 请检查波形或调整参数.")
        return 0

    print("\n=== 基于 .all 波形的单端故障测距结果 (Python) ===")
    print(f"文件名        = {result.file_name}")
    print(f"测距相别      = {result.phase.value}")
    print(
        f"入射波 t1    = 样本索引 {result.first_index}, "
        f"时间 {result.first_time_ms:.6f} ms"
    )
    print(
        f"反射波 t2    = 样本索引 {result.second_index}, "
        f"时间 {result.second_time_ms:.6f} ms"
    )
    print(f"测距结果      = 距测量端 {result.distance_km:.6f} km")
    print(
        "假定参数      = "
        f"行波速度 {result.config.wave_speed_km_per_ms:.6f} km/ms, "
        f"采样间隔 {result.config.sampling_interval_ms:.6f} ms, "
        f"线路全长约 {result.config.line_length_km:.2f} km"
    )
    print(
        f"最终故障点位置（相对本端）= {result.distance_km:.6f} km"
    )
    return 0


def _build_waveform_series(df, phase: Phase) -> list[list[float]]:
    """根据相别生成用于前端绘图的 [x, y] 序列."""
    if phase == Phase.B:
        data = df.data_b
    elif phase == Phase.C:
        data = df.data_c
    else:
        data = df.data_a
    return [[i, float(data[i])] for i in range(df.data_length)]


def run_gui() -> None:
    """基于 NiceGUI 的图形化前端."""

    ui.colors(
        primary="#42a5f5",
        secondary="#90caf9",
        accent="#1e88e5",
        dark=True,
    )

    ui.add_head_html(
        """
        <style>
        body {
            margin: 0;
            background:
                radial-gradient(circle at 0% 0%, #0f172a 0, #020617 45%, #000 100%);
            color: #e5e7eb;
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        </style>
        """
    )

    uploaded_bytes: Optional[bytes] = None
    selected_phase_code: str = "A"
    waveform_chart = None  # type: ignore[assignment]
    summary_label = None  # type: ignore[assignment]
    distance_label = None  # type: ignore[assignment]
    detail_label = None  # type: ignore[assignment]

    def get_phase() -> Phase:
        code = (selected_phase_code or "A").upper()
        if code == "B":
            return Phase.B
        if code == "C":
            return Phase.C
        return Phase.A

    def on_phase_change(e) -> None:
        nonlocal selected_phase_code
        selected_phase_code = str(e.value or "A")

    def update_waveform(df, phase: Phase) -> None:
        nonlocal waveform_chart
        if waveform_chart is None:
            return
        series = _build_waveform_series(df, phase)
        waveform_chart.options = {
            "backgroundColor": "transparent",
            "textStyle": {"color": "#e5e7eb"},
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 48, "right": 32, "top": 32, "bottom": 56},
            "xAxis": {
                "type": "value",
                "name": "样本点",
                "axisLine": {"lineStyle": {"color": "#60a5fa"}},
                "axisLabel": {"color": "#cbd5f5"},
            },
            "yAxis": {
                "type": "value",
                "name": "幅值",
                "axisLine": {"lineStyle": {"color": "#60a5fa"}},
                "splitLine": {"lineStyle": {"color": "#1e293b"}},
                "axisLabel": {"color": "#cbd5f5"},
            },
            # 同时支持横向和纵向缩放
            "dataZoom": [
                {"type": "inside", "xAxisIndex": [0], "yAxisIndex": [0]},
                {"type": "slider", "xAxisIndex": [0]},
                {"type": "slider", "yAxisIndex": [0], "orient": "vertical"},
            ],
            "series": [
                {
                    "type": "line",
                    "name": f"{phase.value} 相",
                    "data": series,
                    "showSymbol": False,
                    "lineStyle": {"color": "#42a5f5", "width": 1.5},
                }
            ],
        }

    async def on_upload(e: events.UploadEventArguments) -> None:
        nonlocal uploaded_bytes, waveform_chart, summary_label, distance_label, detail_label
        # 兼容当前 NiceGUI 的上传事件: 从 e.file 中读取字节内容
        try:
            uploaded_bytes = await e.file.read()
        except Exception as exc:  # noqa: BLE001
            uploaded_bytes = None
            ui.notify(f"读取上传文件失败: {exc}", color="negative")
            return

        if summary_label is not None:
            summary_label.text = f"已选择文件: {getattr(e.file, 'name', '')}"
        if distance_label is not None:
            distance_label.text = ""
        if detail_label is not None:
            detail_label.text = ""
        if waveform_chart is not None:
            waveform_chart.options = {}

    def on_run_click() -> None:
        nonlocal uploaded_bytes, summary_label, distance_label, detail_label
        if uploaded_bytes is None or len(uploaded_bytes) == 0:
            ui.notify("请先选择一个有效的 .all 文件", color="negative")
            return

        # 将上传的内容写入临时文件, 复用现有解析逻辑
        with tempfile.NamedTemporaryFile(delete=False, suffix=".all") as tmp:
            tmp.write(uploaded_bytes)
            tmp_path = Path(tmp.name)

        try:
            df = decode_all_file(tmp_path)
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"解析 .all 文件失败: {exc}", color="negative")
            return

        phase = get_phase()
        cfg = AnalyzerConfig()
        result = analyze_single_end(df, cfg, phase)
        if result is None:
            ui.notify(
                "自动波头识别失败, 无法给出单端测距结果, 请检查波形或调整参数。",
                color="warning",
            )
            return

        update_waveform(df, phase)

        if summary_label is not None:
            summary_label.text = (
                f"站号 {df.station} · 线路 {df.line} · 采样点数 {df.data_length} · "
                f"触发时间 {df.year:04d}-{df.month:02d}-{df.day:02d} "
                f"{df.hour:02d}:{df.minute:02d}:{df.second:02d}.{df.micro_second}"
            )
        if distance_label is not None:
            distance_label.text = f"测距结果: 距测量端 {result.distance_km:.6f} km"
        if detail_label is not None:
            detail_label.text = (
                f"相别 {result.phase.value} 相 | "
                f"入射波 t1 = {result.first_time_ms:.6f} ms, "
                f"反射波 t2 = {result.second_time_ms:.6f} ms | "
                f"行波速度 {cfg.wave_speed_km_per_ms:.3f} km/ms, "
                f"采样间隔 {cfg.sampling_interval_ms:.5f} ms, "
                f"线路全长约 {cfg.line_length_km:.2f} km"
            )

    with ui.column().classes("items-stretch justify-center min-h-screen").style(
        "padding: 24px 16px;"
    ):
        with ui.card().classes("w-full q-pa-xl").style(
            "max-width: 960px; margin: 24px auto; "
            "background: rgba(15, 23, 42, 0.86); "
            "backdrop-filter: blur(22px); -webkit-backdrop-filter: blur(22px); "
            "border-radius: 24px; "
            "border: 1px solid rgba(148, 163, 184, 0.45); "
            "box-shadow: 0 24px 60px rgba(15, 23, 42, 0.95); "
            "color: #e5e7eb;"
        ):
            ui.label("行波故障测距分析 (Python)").classes(
                "text-h5 text-weight-bold text-blue-200"
            )
            ui.label("选择 .all 文件和相别, 一键完成解析、波形展示与测距。").classes(
                "text-body2 text-blue-100 q-mb-md"
            )

            with ui.row().classes("items-end q-gutter-md q-mt-md"):
                ui.upload(
                    label="选择 .all 文件",
                    max_files=1,
                    auto_upload=True,
                    on_upload=on_upload,
                ).props("accept=.all color=primary flat bordered").classes(
                    "flex-grow-1"
                )

                ui.radio(
                    ["A", "B", "C"],
                    value="A",
                    on_change=on_phase_change,
                ).props("inline").classes("text-blue-100")

                ui.button("运行解析与测距", on_click=on_run_click).props(
                    "color=primary unelevated rounded"
                ).classes("q-px-lg")

            ui.separator().classes("q-my-md q-dark")

            ui.label("波形与测距结果").classes("text-subtitle1 text-blue-100 q-mb-xs")

            waveform_chart = ui.echart({}).classes("w-full").style("height: 360px;")

            with ui.column().classes("q-mt-md q-gutter-xs"):
                summary_label = ui.label().classes("text-sm text-blue-200")
                distance_label = ui.label().classes(
                    "text-2xl text-weight-bold text-blue-300"
                )
                detail_label = ui.label().classes("text-sm text-grey-3")

    ui.run(title="行波故障测距分析", reload=False, port = 8001)


if __name__ == "__main__":
    # 默认启动 NiceGUI 前端; 如需命令行模式, 可在其他脚本中导入并调用 main().
    run_gui()
