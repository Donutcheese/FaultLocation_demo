/**
 * 对应 C 代码中的 CurrentData 结构体.
 *
 * 用途:
 * - 保存一次 .all 文件解析出的头部信息与三相波形数据.
 * - 作为后续波头识别与故障测距算法的输入数据结构.
 *
 * 输入来源:
 * - 由 AllFileDecoder.decode 解析得到.
 *
 * 使用方式:
 * - 只读数据载体, 字段在构造函数中一次性赋值.
 */
public final class CurrentData {

    // ------------ 头部信息字段（来自文本头部） ------------
    public final int station; // 站号
    public final int line; // 线路号
    public final int year;
    public final int month;
    public final int day;
    public final int hour;
    public final int minute;
    public final int second;

    /** 微秒字段，原始字符串（去掉前后空白）。 */
    public final String microSecond;
    /** GPS 频率字段，原始字符串（去掉前后空白）。 */
    public final String gpsFrequency;

    public final int gpsFlag;
    public final int breakFlag;
    public final int startupType;
    public final double startupValue1;
    public final double startupValue2;
    public final double startupValue3;

    /**
     * 实际数据点个数（与 C 代码中的 DataLength 含义一致）。
     * 三相波形数组中只有前 dataLength 个元素为有效点。
     */
    public final int dataLength;

    // ------------ 三相波形数据 ------------
    public final double[] dataA;
    public final double[] dataB;
    public final double[] dataC;

    /** 源文件名，便于日志输出与调试。 */
    public final String fileName;

    public CurrentData(
            int station,
            int line,
            int year,
            int month,
            int day,
            int hour,
            int minute,
            int second,
            String microSecond,
            String gpsFrequency,
            int gpsFlag,
            int breakFlag,
            int startupType,
            double startupValue1,
            double startupValue2,
            double startupValue3,
            int dataLength,
            double[] dataA,
            double[] dataB,
            double[] dataC,
            String fileName) {
        this.station = station;
        this.line = line;
        this.year = year;
        this.month = month;
        this.day = day;
        this.hour = hour;
        this.minute = minute;
        this.second = second;
        this.microSecond = microSecond;
        this.gpsFrequency = gpsFrequency;
        this.gpsFlag = gpsFlag;
        this.breakFlag = breakFlag;
        this.startupType = startupType;
        this.startupValue1 = startupValue1;
        this.startupValue2 = startupValue2;
        this.startupValue3 = startupValue3;
        this.dataLength = dataLength;
        this.dataA = dataA;
        this.dataB = dataB;
        this.dataC = dataC;
        this.fileName = fileName;
    }
}
