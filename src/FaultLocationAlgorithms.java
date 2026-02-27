/**
 * 故障测距算法模块.
 *
 * 类作用:
 * - 提供双端行波测距公式和单端行波测距公式的实现.
 * - 与文件解析和波头识别解耦, 只依赖时间和线路参数.
 *
 * 使用方式:
 * - 外部先确定 tA/tB 或 t1/t2 和 v/L, 再调用对应静态方法得到距离.
 */
public final class FaultLocationAlgorithms {

    private FaultLocationAlgorithms() {
    }

    /**
     * 双端行波故障测距.
     *
     * 数学关系:
     * - tA = d / v
     * - tB = (L - d) / v
     * - d = (L + v * (tA - tB)) / 2
     *
     * 输入:
     * - lineLengthKm: 线路总长度 L, 单位 km.
     * - waveSpeedKmPerMs: 行波传播速度 v, 单位 km/ms.
     * - tAms: 故障行波到达 A 端时间 tA, 单位 ms.
     * - tBms: 故障行波到达 B 端时间 tB, 单位 ms.
     *
     * 输出:
     * - 返回 DoubleEndResult, 包含距 A 端和距 B 端的距离, 单位 km.
     * - 结果自动限制在 [0, L].
     */
    public static DoubleEndResult doubleEndByTimes(
            double lineLengthKm,
            double waveSpeedKmPerMs,
            double tAms,
            double tBms) {
        double L = lineLengthKm;
        double v = waveSpeedKmPerMs;

        double dFromA = (L + v * (tAms - tBms)) / 2.0;
        dFromA = clamp(dFromA, 0.0, L);
        double dFromB = L - dFromA;

        return new DoubleEndResult(dFromA, dFromB);
    }

    /**
     * 单端行波故障测距.
     *
     * 数学关系:
     * - d ≈ v * (t2 - t1) / 2.
     *
     * 输入:
     * - waveSpeedKmPerMs: 行波传播速度 v, 单位 km/ms.
     * - t1ms: 入射波到达测量端时间 t1, 单位 ms.
     * - t2ms: 反射波到达测量端时间 t2, 单位 ms.
     *
     * 输出:
     * - 返回距该测量端的距离 d, 单位 km.
     * - 若 t2 <= t1 则返回 0.0.
     */
    public static double singleEndByTwoWaveTimes(
            double waveSpeedKmPerMs,
            double t1ms,
            double t2ms) {
        double dt = t2ms - t1ms;
        if (dt <= 0.0) {
            // 若反射波时间未晚于入射波，返回 0，表示“无法给出有效距离”
            return 0.0;
        }
        return waveSpeedKmPerMs * dt / 2.0;
    }

    /**
     * 将采样点序号转换为时间.
     *
     * 输入:
     * - sampleIndex: 采样点序号, 从 0 开始.
     * - samplingIntervalMs: 采样间隔 Δt, 单位 ms.
     *
     * 输出:
     * - 对应时间 t = sampleIndex * Δt, 单位 ms.
     */
    public static double sampleIndexToTimeMs(long sampleIndex, double samplingIntervalMs) {
        return sampleIndex * samplingIntervalMs;
    }

    // ----------------- 辅助类型与工具方法 -----------------

    /**
     * 双端行波测距结果.
     *
     * 字段含义:
     * - distanceFromA: 故障点到 A 端的距离, km.
     * - distanceFromB: 故障点到 B 端的距离, km.
     */
    public static final class DoubleEndResult {
        /** 故障点到 A 端距离，单位 km。 */
        public final double distanceFromA;
        /** 故障点到 B 端距离，单位 km。 */
        public final double distanceFromB;

        public DoubleEndResult(double distanceFromA, double distanceFromB) {
            this.distanceFromA = distanceFromA;
            this.distanceFromB = distanceFromB;
        }
    }

    private static double clamp(double x, double min, double max) {
        if (x < min) {
            return min;
        }
        if (x > max) {
            return max;
        }
        return x;
    }
}

