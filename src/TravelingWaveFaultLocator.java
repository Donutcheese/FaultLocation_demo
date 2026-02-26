import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Instant;
import java.util.Locale;

/**
 * 行波测距算法模块。
 *
 * 这个类把与“双端行波测距 Demo”强相关的逻辑收拢在一起，包括：
 * - 如何在某条线路上“虚构”一个故障并生成双端到达时间（用于日常算法联调/教学演示）；
 * - 如何把一次测距记录（tA/tB/波速等）写入 SQLite 表；
 * - 如何从数据库中读取最新或指定测距记录，并根据拓扑信息计算故障点距离；
 * - 输出人类可读的结果说明。
 *
 * 这样 Main 只需要负责“调用接口 + 打印命令成功与否”，
 * 算法细节则集中在本模块中，更加清晰。
 */
public class TravelingWaveFaultLocator {

    /**
     * 针对指定线路号（此处为 L1001）“模拟”一条测距记录，并写入 measurement 表。
     *
     * 逻辑说明：
     * - 假设在线路上距离 A 端 20km 处发生故障；
     * - 利用简化行波传播模型计算到达 A/B 两端的理论时间 tA/tB；
     * - 为了更贴近工程实际，在理论值基础上叠加微小随机噪声；
     * - 将 (tA, tB, v, 线路信息) 一并存入 measurement 表。
     *
     * @return 新插入的测距记录主键 ID
     */
    public static long simulateOneSample(Connection conn) throws SQLException {
        // 例子：在线路 L1001 上，距离 A 站 20km 处发生故障
        GridTopologyRepository.LineInfo line = GridTopologyRepository.getLineByNo(conn, "L1001");

        // 行波传播速度 v，单位 km/ms（约 2e5 km/s，仅用于演示）
        double v = 200.0;
        // 预设故障点到 A 端的距离（公里）
        double faultFromA = 20.0;
        // 给测量时间叠加一个很小的随机扰动（单位 ms），模拟采样误差/同步误差
        double noiseMs = 0.00005; // 0.05 微秒量级的演示噪声

        // 理论到达时间：tA = d/v, tB = (L-d)/v
        double tA = faultFromA / v;
        double tB = (line.lengthKm - faultFromA) / v;
        // 在理论值基础上加上随机噪声
        tA += (Math.random() * 2 - 1) * noiseMs;
        tB += (Math.random() * 2 - 1) * noiseMs;

        return insertMeasurement(conn, line.id, line.fromStationId, line.toStationId, tA, tB, v);
    }

    /**
     * 针对当前表中最新的一条测距记录执行故障定位。
     * 如果表中没有任何记录，会给出友好提示。
     */
    public static void locateLatest(Connection conn) throws SQLException {
        Long id = queryLong(conn, "SELECT id FROM measurement ORDER BY id DESC LIMIT 1;");
        if (id == null) {
            System.out.println("No measurement found. Run `simulate` first.");
            return;
        }
        locateById(conn, id);
    }

    /**
     * 针对指定 ID 的测距记录执行故障定位并打印结果。
     *
     * 定位核心公式（对称双端行波测距、简化推导）：
     * tA = d / v
     * tB = (L - d) / v
     * => d = (L + v * (tA - tB)) / 2
     * 其中：
     * - L 为整条线路长度；
     * - d 为故障到 A 端的距离；
     * - v 为行波在该线路上的传播速度。
     */
    public static void locateById(Connection conn, long measId) throws SQLException {
        String sql = "SELECT m.id AS meas_id, m.t_a_ms, m.t_b_ms, m.v_km_per_ms, m.created_at, " +
                "l.line_no, l.length_km, " +
                "sa.name AS station_a, sb.name AS station_b " +
                "FROM measurement m " +
                "JOIN line l ON l.id = m.line_id " +
                "JOIN station sa ON sa.id = m.station_a_id " +
                "JOIN station sb ON sb.id = m.station_b_id " +
                "WHERE m.id = ?;";

        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, measId);
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) {
                    System.out.println("Measurement not found: id=" + measId);
                    return;
                }

                double tA = rs.getDouble("t_a_ms");
                double tB = rs.getDouble("t_b_ms");
                double v = rs.getDouble("v_km_per_ms");
                double L = rs.getDouble("length_km");

                String lineNo = rs.getString("line_no");
                String sta = rs.getString("station_a");
                String stb = rs.getString("station_b");

                // 双端行波测距（简化演示）
                // tA = d/v, tB = (L-d)/v => d = (L + v*(tA - tB))/2
                double dFromA = (L + v * (tA - tB)) / 2.0;
                // 出于鲁棒性考虑，把结果限定在 [0, L] 之间，避免由于噪声导致“超出线路范围”
                dFromA = clamp(dFromA, 0.0, L);
                double dFromB = L - dFromA;

                // 将所有关键参数一起打印出来，方便对照公式进行人工校验
                System.out.println("=== Traveling-Wave Double-End Fault Location (Demo) ===");
                System.out.println("measurement.id = " + rs.getLong("meas_id"));
                System.out.println("created_at     = " + rs.getString("created_at"));
                System.out
                        .println("line           = " + lineNo + " (" + sta + " <-> " + stb + "), L=" + fmt(L) + " km");
                System.out.println("v              = " + fmt(v) + " km/ms");
                System.out.println("tA/tB          = " + fmt(tA) + " ms / " + fmt(tB) + " ms");
                System.out.println("fault location = " + fmt(dFromA) + " km from " + sta + "  (" + fmt(dFromB)
                        + " km from " + stb + ")");
            }
        }
    }

    // ----------------- 下方是 measurement 表相关的数据读写与小工具方法 -----------------

    /**
     * 向 measurement 表写入一条双端测距记录。
     */
    private static long insertMeasurement(Connection conn, long lineId, long stationAId, long stationBId,
            double tAms, double tBms, double vKmPerMs) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(
                "INSERT INTO measurement(line_id, station_a_id, station_b_id, t_a_ms, t_b_ms, v_km_per_ms, created_at) "
                        +
                        "VALUES(?,?,?,?,?,?,?);",
                Statement.RETURN_GENERATED_KEYS)) {
            ps.setLong(1, lineId);
            ps.setLong(2, stationAId);
            ps.setLong(3, stationBId);
            ps.setDouble(4, tAms);
            ps.setDouble(5, tBms);
            ps.setDouble(6, vKmPerMs);
            ps.setString(7, Instant.now().toString());
            ps.executeUpdate();
            try (ResultSet keys = ps.getGeneratedKeys()) {
                keys.next();
                return keys.getLong(1);
            }
        }
    }

    /**
     * 执行一条只关心“第一列为 long 值”的查询，并返回该值（或 null）。
     */
    private static Long queryLong(Connection conn, String sql) throws SQLException {
        try (Statement st = conn.createStatement();
                ResultSet rs = st.executeQuery(sql)) {
            if (!rs.next()) {
                return null;
            }
            long v = rs.getLong(1);
            return rs.wasNull() ? null : v;
        }
    }

    /**
     * 将浮点数格式化为统一的 6 位小数，方便日志阅读与结果对比。
     */
    private static String fmt(double x) {
        return String.format(Locale.ROOT, "%.6f", x);
    }

    /**
     * 简单的限幅函数，用于把结果约束在 [min, max] 区间内。
     */
    private static double clamp(double x, double min, double max) {
        if (x < min)
            return min;
        if (x > max)
            return max;
        return x;
    }
}
