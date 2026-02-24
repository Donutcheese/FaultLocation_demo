import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * 电网拓扑仓储模块。
 *
 * 主要职责：
 * 1. 对 station / line 两张表做增删查（本 Demo 只用到插入与简单查询）；
 * 2. 提供“种子拓扑”的初始化方法，方便快速搭建一个小电网模型；
 * 3. 将关于线路的结构信息（长度、两端站点）封装成 LineInfo 模型对象。
 *
 * 注意：这里所有方法都使用静态方法形式，简化 Demo 使用，
 * 在真实工程中可以进一步抽象成接口 + 实现类，方便依赖注入与单元测试。
 */
public class GridTopologyRepository {

    /**
     * 如果当前拓扑表为空，则插入一个非常小的示例电网：
     * S1_A站 —(L1001, 50km)— S2_B站 —(L2001, 30km)— S3_C站。
     *
     * 这个方法只在 station 或 line 存在记录时跳过，避免重复插入。
     */
    public static void seedTopologyIfEmpty(Connection conn) throws SQLException {
        if (count(conn, "station") > 0 || count(conn, "line") > 0) {
            return;
        }

        long a = insertStation(conn, "S1_A站");
        long b = insertStation(conn, "S2_B站");
        long c = insertStation(conn, "S3_C站");

        insertLine(conn, "L1001", a, b, 50.0);
        insertLine(conn, "L2001", b, c, 30.0);
    }

    /**
     * 按线路号查询一条线路的关键参数。
     *
     * @param lineNo 线路号（例如 "L1001"）
     * @return 包含线路主键、两端站点主键以及线路长度的 LineInfo
     */
    public static LineInfo getLineByNo(Connection conn, String lineNo) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(
                "SELECT id, from_station_id, to_station_id, length_km FROM line WHERE line_no = ?;")) {
            ps.setString(1, lineNo);
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) {
                    throw new SQLException("line not found: " + lineNo);
                }
                return new LineInfo(
                        rs.getLong("id"),
                        rs.getLong("from_station_id"),
                        rs.getLong("to_station_id"),
                        rs.getDouble("length_km"));
            }
        }
    }

    // ----------------- 下方是内部辅助方法：对 station/line 进行基础增查 -----------------

    /**
     * 向 station 表插入一个新站点，并返回生成的自增主键。
     */
    private static long insertStation(Connection conn, String name) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(
                "INSERT INTO station(name) VALUES(?);",
                Statement.RETURN_GENERATED_KEYS)) {
            ps.setString(1, name);
            ps.executeUpdate();
            try (ResultSet keys = ps.getGeneratedKeys()) {
                keys.next();
                return keys.getLong(1);
            }
        }
    }

    /**
     * 向 line 表插入一条新线路，并返回生成的自增主键。
     */
    private static long insertLine(Connection conn, String lineNo, long fromStationId,
            long toStationId, double lengthKm) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(
                "INSERT INTO line(line_no, from_station_id, to_station_id, length_km) VALUES(?,?,?,?);",
                Statement.RETURN_GENERATED_KEYS)) {
            ps.setString(1, lineNo);
            ps.setLong(2, fromStationId);
            ps.setLong(3, toStationId);
            ps.setDouble(4, lengthKm);
            ps.executeUpdate();
            try (ResultSet keys = ps.getGeneratedKeys()) {
                keys.next();
                return keys.getLong(1);
            }
        }
    }

    /**
     * 统计指定表中的总行数，用于判断表是否为空。
     */
    private static long count(Connection conn, String table) throws SQLException {
        try (Statement st = conn.createStatement();
                ResultSet rs = st.executeQuery("SELECT COUNT(1) AS c FROM " + table + ";")) {
            rs.next();
            return rs.getLong("c");
        }
    }

    /**
     * 线路基础信息数据模型。
     *
     * 封装了多张表中与“线路”有关的关键字段，便于在行波测距模块中直接使用。
     */
    public static final class LineInfo {
        public final long id;
        public final long fromStationId;
        public final long toStationId;
        public final double lengthKm;

        public LineInfo(long id, long fromStationId, long toStationId, double lengthKm) {
            this.id = id;
            this.fromStationId = fromStationId;
            this.toStationId = toStationId;
            this.lengthKm = lengthKm;
        }
    }
}
