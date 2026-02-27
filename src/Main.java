import java.util.Locale;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.Files;
import java.io.BufferedReader;
import java.io.InputStreamReader;

/**
 * 程序入口类 Main.
 *
 * 类作用:
 * - 从固定目录中选择一个 .all 文件作为输入.
 * - 调用 AllFileDecoder 解析录波头部和三相数据.
 * - 打印基本信息, 询问用户选择 A/B/C 相, 调用单端测距模块输出结果.
 *
 * 注意:
 * - 当前版本不使用数据库, 仅处理本地 .all 文件.
 */
public class Main {
    /**
     * .all 文件所在的根目录, 相对于工程根目录.
     * 所有示例数据默认放在 src/data 下.
     */
    private static final Path DATA_ROOT = Paths.get("src", "data");

    /**
     * 需要分析的 .all 文件名.
     * 用户可修改为 src/data 下的任意文件名.
     */
    private static final String TARGET_FILE_NAME = "140423231753杨马线M0053.all";

    /**
     * 程序入口.
     *
     * 输入:
     * - args: 当前未使用, 保留扩展.
     *
     * 输出:
     * - 在控制台打印解析信息和故障测距结果.
     */
    public static void main(String[] args) throws Exception {
        Locale.setDefault(Locale.ROOT);

        if (!Files.exists(DATA_ROOT)) {
            System.out.println("数据目录不存在: " + DATA_ROOT.toAbsolutePath());
            return;
        }

        // 1. 对代码中指定的某个 .all 文件做解析和单端测距分析
        if (TARGET_FILE_NAME != null && !TARGET_FILE_NAME.isEmpty()) {
            Path target = DATA_ROOT.resolve(TARGET_FILE_NAME);

            if (target == null) {
                System.out.println();
                System.out.println("未在 " + DATA_ROOT.toAbsolutePath() + " 下找到指定文件: " + TARGET_FILE_NAME);
                return;
            }

            System.out.println();
            System.out.println("=== 解析并分析指定 .all 文件 ===");
            System.out.println("目标文件: " + target.toAbsolutePath());

            CurrentData df = AllFileDecoder.decode(target);
            // 先打印一段概要信息
            printSummary(df);

            // 询问用户选择测距相别
            WaveformFaultAnalyzer.Phase phase = askPhaseFromConsole();

            // 再做单端测距分析
            WaveformFaultAnalyzer.Config cfg = WaveformFaultAnalyzer.Config.defaultConfig();
            WaveformFaultAnalyzer.Result result = WaveformFaultAnalyzer.analyzeSingleEnded(df, cfg, phase);
            if (result == null) {
                System.out.println("自动波头识别失败，无法给出单端测距结果，请检查波形或调整算法参数。");
            } else {
                // 打印详细结果
                result.printToConsole();
                // 在 Main 中额外给出一行“最终故障点”摘要，便于快速查看
                System.out.printf(Locale.ROOT,
                        "最终故障点位置（相对本端）= %.6f km%n",
                        result.distanceFromMeasuredEndKm);
            }
        }
    }

    /**
     * 在控制台询问用户选择 A/B/C 相, 默认 A 相.
     *
     * 输入:
     * - 无, 从标准输入读取一个字符.
     *
     * 输出:
     * - 返回用户选择的相别 Phase, 输入无效或出错时返回 A 相.
     */
    private static WaveformFaultAnalyzer.Phase askPhaseFromConsole() {
        System.out.print("请选择测距相别 (A/B/C)，直接回车默认为 A 相: ");
        try {
            BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
            String line = br.readLine();
            if (line == null || line.trim().isEmpty()) {
                return WaveformFaultAnalyzer.Phase.A;
            }
            char ch = Character.toUpperCase(line.trim().charAt(0));
            switch (ch) {
                case 'B':
                    return WaveformFaultAnalyzer.Phase.B;
                case 'C':
                    return WaveformFaultAnalyzer.Phase.C;
                case 'A':
                default:
                    return WaveformFaultAnalyzer.Phase.A;
            }
        } catch (Exception e) {
            System.out.println("读取相别输入失败，默认使用 A 相。错误: " + e.getMessage());
            return WaveformFaultAnalyzer.Phase.A;
        }
    }

    /**
     * 打印指定 .all 文件解析出的概要信息.
     *
     * 输入:
     * - df: 解析后的 CurrentData.
     *
     * 输出:
     * - 在控制台打印站号、线路号、时间、点数、GPS 信息和前若干个 A 相采样值.
     */
    private static void printSummary(CurrentData df) {
        System.out.printf(Locale.ROOT, "站号: %d, 线路: %d%n", df.station, df.line);
        System.out.printf(Locale.ROOT, "日期时间: %04d-%02d-%02d %02d:%02d:%02d.%s%n",
                df.year, df.month, df.day, df.hour, df.minute, df.second, df.microSecond);
        System.out.printf(Locale.ROOT, "数据点数: %d%n", df.dataLength);
        System.out.printf(Locale.ROOT, "GPS频率: %s, GPS标志: %d, 跳闸标志: %d%n",
                df.gpsFrequency, df.gpsFlag, df.breakFlag);

        int printN = Math.min(df.dataLength, 10);
        System.out.println("前 " + printN + " 个 A 相数据:");
        for (int i = 0; i < printN; i++) {
            System.out.printf(Locale.ROOT, "A[%d] = %f%n", i, df.dataA[i]);
        }
    }
}