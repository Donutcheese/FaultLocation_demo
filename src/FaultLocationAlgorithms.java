/**
 * 故障测距算法模块。
 *
 * 设计原则：
 * - 本类只关心“数学公式”和“物理含义”，不依赖数据库、文件格式等外部细节；
 * - 对外暴露“双端行波测距公式”“单端行波测距公式”等纯算法接口；
 * - 其他模块（例如 TravelingWaveFaultLocator、.all 文件处理流程）只需要传入
 *   已经推算好的到达时间 / 采样点序号等参数即可。
 */
public final class FaultLocationAlgorithms {

    private FaultLocationAlgorithms() {
    }

    /**
     * 双端行波故障测距（对称线路，简化模型）。
     *
     * 公式推导与含义：
     *   设整条线路长度为 L，行波传播速度为 v，
     *   故障点到 A 端距离为 d，
     *   行波从故障点到 A、B 两端的走时分别为 tA、tB。
     *
     *   tA = d / v
     *   tB = (L - d) / v
     *   =>
     *   d = (L + v * (tA - tB)) / 2
     *
     * 为提高鲁棒性，本实现会将 d 限制在 [0, L] 区间内。
     *
     * @param lineLengthKm   线路总长度 L，单位 km
     * @param waveSpeedKmPerMs 行波传播速度 v，单位 km/ms（约 200 km/ms ≈ 2×10^5 km/s）
     * @param tAms           故障行波到达 A 端的时间 tA，单位 ms（相对某共同时刻）
     * @param tBms           故障行波到达 B 端的时间 tB，单位 ms
     * @return 双端测距结果（从 A 端、B 端分别量测的距离，单位 km）
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
     * 单端行波故障测距（“入射波 + 反射波”模型，简化公式）。
     *
     * 常见简化模型：
     *   - 在线路上某处发生故障；
     *   - 以 A 端为测量端，能够在该端同时观测到“故障入射波”和“远端反射波”；
     *   - 设入射波到达 A 端的时间为 t1，反射波（由远端或故障点再次反射）到达 A 端的时间为 t2；
     *   - 行波传播速度为 v。
     *
     * 则可近似认为：
     *   故障点到 A 端的距离 d ≈ v * (t2 - t1) / 2
     *
     * 注意：
     *   - 这里假设 (t2 - t1) 足够小、线路为均匀单回路、反射路径简化为“往返一次”；
     *   - 在工程上需要结合实际线路模型和波头识别算法进行修正。
     *
     * @param waveSpeedKmPerMs 行波传播速度 v，单位 km/ms
     * @param t1ms             入射波到达测量端的时间 t1，单位 ms
     * @param t2ms             相应反射波到达测量端的时间 t2，单位 ms
     * @return 故障点到该测量端的距离 d，单位 km
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
     * 若已经通过波头识别算法得到了“采样点序号”而非时间，
     * 可先将采样点转为时间，再调用 doubleEndByTimes/singleEndByTwoWaveTimes。
     *
     * @param sampleIndex      采样点序号（从 0 开始）
     * @param samplingIntervalMs 采样间隔 Δt，单位 ms
     * @return 对应时间 t = sampleIndex * Δt，单位 ms
     */
    public static double sampleIndexToTimeMs(long sampleIndex, double samplingIntervalMs) {
        return sampleIndex * samplingIntervalMs;
    }

    // ----------------- 辅助类型与工具方法 -----------------

    /**
     * 双端行波测距结果。
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

