import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Locale;
import java.util.stream.Stream;

/**
 * 批量遍历并解析 src/data 目录下的所有 .all 文件。
 *
 * 使用方法（在项目根目录执行）：
 * javac src\\*.java
 * java -cp src AllDataBatchRunner
 *
 * 也可以通过命令行参数指定起始目录：
 * java -cp src AllDataBatchRunner d:\\FaultLocation_demo\\src\\data
 */
public final class AllDataBatchRunner {

    private AllDataBatchRunner() {
    }

    public static void main(String[] args) throws Exception {
        Locale.setDefault(Locale.ROOT);

        Path root;
        if (args.length > 0) {
            root = Paths.get(args[0]);
        } else {
            // 默认从 src/data 开始递归查找
            root = Paths.get("src", "data");
        }

        if (!Files.exists(root)) {
            System.err.println("目录不存在: " + root.toAbsolutePath());
            return;
        }

        System.out.println("扫描目录: " + root.toAbsolutePath());
        try (Stream<Path> stream = Files.walk(root)) {
            stream.filter(p -> p.toString().toLowerCase(Locale.ROOT).endsWith(".all"))
                    .sorted()
                    .forEach(AllDataBatchRunner::handleOneFile);
        }
    }

    private static void handleOneFile(Path path) {
        System.out.println("------------------------------------------------------------");
        System.out.println("文件: " + path.toString());
        try {
            CurrentData df = AllFileDecoder.decode(path);
            printSummary(df);
        } catch (IOException e) {
            System.out.println("解析失败: " + e.getMessage());
        }
    }

    /**
     * 打印小段摘要信息，方便快速验证解析是否正确。
     */
    private static void printSummary(CurrentData df) {
        System.out.printf(Locale.ROOT,
                "站号: %d, 线路: %d%n", df.station, df.line);
        System.out.printf(Locale.ROOT,
                "日期时间: %04d-%02d-%02d %02d:%02d:%02d.%s%n",
                df.year, df.month, df.day, df.hour, df.minute, df.second, df.microSecond);
        System.out.printf(Locale.ROOT,
                "数据点数: %d%n", df.dataLength);
        System.out.printf(Locale.ROOT,
                "GPS频率: %s, GPS标志: %d, 跳闸标志: %d%n",
                df.gpsFrequency, df.gpsFlag, df.breakFlag);

        int printN = Math.min(df.dataLength, 10);
        System.out.println("前 " + printN + " 个 A 相数据:");
        for (int i = 0; i < printN; i++) {
            System.out.printf(Locale.ROOT, "A[%d] = %f%n", i, df.dataA[i]);
        }
    }
}
