import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * 数据库初始化模块。
 *
 * 这个类专门负责：
 * 1. 打开 SQLite 外键约束；
 * 2. 创建用于 Demo 的三张表（station/line/measurement）。
 *
 * 这样可以把“建表脚本”从 Main 中拆出来，避免入口类过于臃肿，
 * 同时便于后续在别的地方（例如单元测试、工具类）复用建表逻辑。
 */
public class DatabaseInitializer {

    /**
     * 确保数据库中已经存在 Demo 所需的表结构。
     * 如果表已经存在则不会重复创建，因此可以安全地多次调用。
     */
    public static void ensureSchema(Connection conn) throws SQLException {
        try (Statement st = conn.createStatement()) {
            // SQLite 默认外键约束是关闭的，这里显式打开，保证 station/line/measurement 之间的引用关系生效
            st.execute("PRAGMA foreign_keys = ON;");

            // 站表：保存变电站/开关站等节点信息，仅包含一个唯一名称
            st.execute("CREATE TABLE IF NOT EXISTS station (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                    "name TEXT NOT NULL UNIQUE" +
                    ");");

            // 线路表：表示两站之间的一条输电线路（单回路），包含线路号、两端站、以及线路总长度（km）
            st.execute("CREATE TABLE IF NOT EXISTS line (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                    "line_no TEXT NOT NULL UNIQUE," +
                    "from_station_id INTEGER NOT NULL," +
                    "to_station_id INTEGER NOT NULL," +
                    "length_km REAL NOT NULL," +
                    "FOREIGN KEY(from_station_id) REFERENCES station(id)," +
                    "FOREIGN KEY(to_station_id) REFERENCES station(id)" +
                    ");");

            // 测距记录表：保存一次“双端行波测距”的原始量测与结果所需参数
            st.execute("CREATE TABLE IF NOT EXISTS measurement (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                    "line_id INTEGER NOT NULL," +
                    "station_a_id INTEGER NOT NULL," +
                    "station_b_id INTEGER NOT NULL," +
                    "t_a_ms REAL NOT NULL," +
                    "t_b_ms REAL NOT NULL," +
                    "v_km_per_ms REAL NOT NULL," +
                    "created_at TEXT NOT NULL," +
                    "FOREIGN KEY(line_id) REFERENCES line(id)," +
                    "FOREIGN KEY(station_a_id) REFERENCES station(id)," +
                    "FOREIGN KEY(station_b_id) REFERENCES station(id)" +
                    ");");
        }
    }
}

