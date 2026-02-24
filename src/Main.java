import java.sql.Connection;
import java.sql.DriverManager;
import java.util.Locale;

// 说明：本 Demo 中所有类都放在“默认包”下（即未显式声明 package），
// 在这种情况下可以在 Main 中直接使用 DatabaseInitializer / GridTopologyRepository / TravelingWaveFaultLocator
// 而不需要显式 import，它们会自动处于同一命名空间。

/**
 * 程序入口类（Main）。
 *
 * 设计思路：
 * - Main 只做三件事：解析命令行参数、建立数据库连接、调用各个“业务模块”；
 * - 具体的数据库建表、拓扑数据维护、行波测距算法，都拆分到独立的类中实现；
 * - 这样可以让每个类的职责更单一，Main 本身也更加简洁、易读、易扩展。
 *
 * 可用命令：
 *   - init     : 仅初始化表结构；
 *   - seed     : 写入一个小型电网拓扑（3 个站、2 条线路），只在空库时写入一次；
 *   - simulate : 在示例线路 L1001 上“虚构”一次故障，生成一条双端测距记录；
 *   - locate   : 对最新一条测距记录执行双端行波故障定位；
 *   - demo     : 一键完成 seed + simulate + locate（默认命令）。
 */
public class Main {
    private static final String DB_URL = "jdbc:sqlite:demo.db";

    public static void main(String[] args) throws Exception {
        Locale.setDefault(Locale.ROOT);

        String cmd = (args.length == 0) ? "demo" : args[0].trim().toLowerCase(Locale.ROOT);
        try (Connection conn = DriverManager.getConnection(DB_URL)) {
            conn.setAutoCommit(true);

            // 任何命令在运行前，都需要先保证表结构已经就绪
            DatabaseInitializer.ensureSchema(conn);

            switch (cmd) {
                case "init":
                    System.out.println("OK: schema initialized: demo.db");
                    break;
                case "seed":
                    GridTopologyRepository.seedTopologyIfEmpty(conn);
                    System.out.println("OK: topology seeded (if empty).");
                    break;
                case "simulate":
                    GridTopologyRepository.seedTopologyIfEmpty(conn);
                    long measId = TravelingWaveFaultLocator.simulateOneSample(conn);
                    System.out.println("OK: inserted measurement id=" + measId);
                    break;
                case "locate":
                    GridTopologyRepository.seedTopologyIfEmpty(conn);
                    TravelingWaveFaultLocator.locateLatest(conn);
                    break;
                case "demo":
                default:
                    GridTopologyRepository.seedTopologyIfEmpty(conn);
                    long id = TravelingWaveFaultLocator.simulateOneSample(conn);
                    System.out.println("Inserted sample measurement id=" + id);
                    TravelingWaveFaultLocator.locateById(conn, id);
                    System.out.println();
                    System.out.println("You can also run:");
                    System.out.println("  init | seed | simulate | locate");
                    break;
            }
        }
    }
}