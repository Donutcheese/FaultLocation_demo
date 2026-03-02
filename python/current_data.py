from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CurrentData:
    """
    对应 Java 中 CurrentData 类.

    作用:
    - 保存一次 .all 文件解析得到的头部信息和三相波形数据.
    - 作为后续波头识别与故障测距算法的输入数据结构.

    字段说明:
    - station, line: 站号与线路号.
    - year..second: 触发时间年月日时分秒.
    - micro_second: 微秒字符串.
    - gps_frequency: GPS 频率字符串.
    - gps_flag: GPS 状态标志.
    - break_flag: 跳闸标志.
    - startup_type: 启动类型.
    - startup_value1/2/3: 启动相关数值.
    - data_length: 实际采样点数.
    - data_a/b/c: 三相波形数组, 长度至少 data_length.
    - file_name: 源 .all 文件名.
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
    data_a: Sequence[float]
    data_b: Sequence[float]
    data_c: Sequence[float]

    file_name: str

