import java.util.Locale;

/**
 * 基于 .all 解析出的波形做简单单端测距分析的模块。
 *
 * 说明：这里实现的是一个“教学 Demo 级别”的波头自动识别算法，
 * 仅用于帮助理解从录波 → 波头时刻 → 单端测距的大致流程。
 * 工程上可根据需要替换为更复杂、更稳健的波头识别算法。
 */
public final class WaveformFaultAnalyzer {

    private WaveformFaultAnalyzer() {
    }

    /**
     * 用单端法对某一相波形进行故障测距分析（默认使用 A 相）。
     */
    public static Result analyzeSingleEnded(CurrentData df, Config cfg) {
        return analyzeSingleEnded(df, cfg, Phase.A);
    }

    /**
     * 用单端法对指定相别（A/B/C）波形进行故障测距分析。
     *
     * @param df    解析自 .all 的波形数据
     * @param cfg   测距配置参数（采样间隔、行波速度、线路长度等）
     * @param phase 相别：A / B / C
     * @return 分析结果，如果自动识别失败则返回 null
     */
    public static Result analyzeSingleEnded(CurrentData df, Config cfg, Phase phase) {
        double[] x;
        switch (phase) {
            case B:
                x = df.dataB;
                break;
            case C:
                x = df.dataC;
                break;
            case A:
            default:
                x = df.dataA;
                break;
        }
        int n = df.dataLength;
        if (n < 10) {
            return null;
        }

        // 1. 用前 preN 个样本估计“背景噪声”
        int preN = Math.min(1000, Math.max(50, n / 10));
        double mean = 0.0;
        for (int i = 0; i < preN; i++) {
            mean += x[i];
        }
        mean /= preN;

        // 计算差分的标准差，用于设置阈值
        double sumSq = 0.0;
        for (int i = 1; i < preN; i++) {
            double dx = (x[i] - mean) - (x[i - 1] - mean);
            sumSq += dx * dx;
        }
        double noiseStd = Math.sqrt(sumSq / Math.max(1, preN - 1));
        double threshold1 = cfg.firstWaveSigma * noiseStd;
        double threshold2 = cfg.secondWaveSigma * noiseStd;

        // 2. 寻找第一个大幅突变点，作为“入射波” t1
        int t1Index = -1;
        for (int i = preN; i < n; i++) {
            double dx = (x[i] - mean) - (x[i - 1] - mean);
            if (Math.abs(dx) > threshold1) {
                t1Index = i;
                break;
            }
        }
        if (t1Index < 0) {
            return null; // 没找到明显入射波
        }

        // 3. 在 t1 之后一定间隔内寻找下一个大幅突变，作为“反射波” t2
        int minGap = (int) Math.max(cfg.minSamplesBetweenWaves, n * 0.02); // 至少相隔 2% 采样点
        int searchStart = Math.min(n - 1, t1Index + minGap);
        int t2Index = -1;
        double bestDx = 0.0;
        for (int i = searchStart; i < n; i++) {
            double dx = (x[i] - mean) - (x[i - 1] - mean);
            double adx = Math.abs(dx);
            if (adx > threshold2 && adx > bestDx) {
                bestDx = adx;
                t2Index = i;
            }
        }
        if (t2Index < 0 || t2Index <= t1Index) {
            return null; // 没有找到可靠的反射波
        }

        // 4. 采样点 → 时间（ms），并套用单端测距公式
        double t1ms = FaultLocationAlgorithms.sampleIndexToTimeMs(t1Index, cfg.samplingIntervalMs);
        double t2ms = FaultLocationAlgorithms.sampleIndexToTimeMs(t2Index, cfg.samplingIntervalMs);
        double distanceKm = FaultLocationAlgorithms.singleEndByTwoWaveTimes(cfg.waveSpeedKmPerMs, t1ms, t2ms);

        return new Result(df.fileName, phase, t1Index, t2Index, t1ms, t2ms, distanceKm, cfg);
    }

    // ----------------- 配置与结果类型 -----------------

    /** 相别枚举。 */
    public enum Phase {
        A, B, C
    }

    /**
     * 单端测距所需的配置参数。
     */
    public static final class Config {
        /** 采样间隔（ms），例如 100kHz 采样则为 0.01 ms。 */
        public final double samplingIntervalMs;
        /** 行波传播速度（km/ms），例如 2e5 km/s ≈ 200 km/ms。 */
        public final double waveSpeedKmPerMs;
        /** 线路总长（km），主要用于对结果进行工程对比，本算法本身不直接用到。 */
        public final double lineLengthKm;
        /** 识别入射波时使用的噪声倍数阈值。 */
        public final double firstWaveSigma;
        /** 识别反射波时使用的噪声倍数阈值。 */
        public final double secondWaveSigma;
        /** 入射波与反射波之间至少间隔的采样点数。 */
        public final int minSamplesBetweenWaves;

        public Config(double samplingIntervalMs,
                double waveSpeedKmPerMs,
                double lineLengthKm,
                double firstWaveSigma,
                double secondWaveSigma,
                int minSamplesBetweenWaves) {
            this.samplingIntervalMs = samplingIntervalMs;
            this.waveSpeedKmPerMs = waveSpeedKmPerMs;
            this.lineLengthKm = lineLengthKm;
            this.firstWaveSigma = firstWaveSigma;
            this.secondWaveSigma = secondWaveSigma;
            this.minSamplesBetweenWaves = minSamplesBetweenWaves;
        }

        /**
         * 提供一个较为保守的默认配置，便于快速试跑。
         * 你可以根据实际线路情况（采样频率、行波速度、线路长度等）进行调整。
         */
        public static Config defaultConfig() {
            double samplingIntervalMs = 0.01; // 假定 100kHz 采样
            double waveSpeedKmPerMs = 200.0; // 约 2e5 km/s
            double lineLengthKm = 300.0; // 假定 300km，供结果对比参考
            double firstSigma = 6.0;
            double secondSigma = 5.0;
            int minGap = 500; // 至少间隔 500 个采样点
            return new Config(samplingIntervalMs, waveSpeedKmPerMs, lineLengthKm, firstSigma, secondSigma, minGap);
        }
    }

    /**
     * 单端测距分析结果。
     */
    public static final class Result {
        public final String fileName;
        public final Phase phase;
        public final int firstWaveIndex;
        public final int secondWaveIndex;
        public final double firstWaveTimeMs;
        public final double secondWaveTimeMs;
        public final double distanceFromMeasuredEndKm;
        public final Config config;

        public Result(String fileName,
                Phase phase,
                int firstWaveIndex,
                int secondWaveIndex,
                double firstWaveTimeMs,
                double secondWaveTimeMs,
                double distanceFromMeasuredEndKm,
                Config config) {
            this.fileName = fileName;
            this.phase = phase;
            this.firstWaveIndex = firstWaveIndex;
            this.secondWaveIndex = secondWaveIndex;
            this.firstWaveTimeMs = firstWaveTimeMs;
            this.secondWaveTimeMs = secondWaveTimeMs;
            this.distanceFromMeasuredEndKm = distanceFromMeasuredEndKm;
            this.config = config;
        }

        public void printToConsole() {
            System.out.println("=== 基于 .all 波形的单端故障测距结果 ===");
            System.out.println("文件名        = " + fileName);
            System.out.println("测距相别      = " + phase);
            System.out.printf(Locale.ROOT, "入射波 t1    = 样本索引 %d, 时间 %.6f ms%n", firstWaveIndex, firstWaveTimeMs);
            System.out.printf(Locale.ROOT, "反射波 t2    = 样本索引 %d, 时间 %.6f ms%n", secondWaveIndex, secondWaveTimeMs);
            System.out.printf(Locale.ROOT, "测距结果      = 距测量端 %.6f km%n", distanceFromMeasuredEndKm);
            System.out.printf(Locale.ROOT, "假定参数      = 行波速度 %.6f km/ms, 采样间隔 %.6f ms, 线路全长约 %.2f km%n",
                    config.waveSpeedKmPerMs, config.samplingIntervalMs, config.lineLengthKm);
        }
    }
}

