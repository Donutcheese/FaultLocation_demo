import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * .all 波形文件解析模块.
 *
 * 类作用:
 * - 从磁盘读取 .all 文件的二进制内容.
 * - 切分头部字段和数据区.
 * - 将头部字段和三相波形数据封装为 CurrentData 实例.
 *
 * 使用方式:
 * - 外部调用 decode(path) 获得 CurrentData.
 */
public final class AllFileDecoder {

    /** 与 C 代码中的 MAXDATALENGTH 一致: 512 * 1024 字节. */
    private static final int MAX_DATA_LENGTH = 512 * 1024;

    private AllFileDecoder() {
    }

    /**
     * 解析单个 .all 文件.
     *
     * 输入:
     * - path: .all 文件路径.
     *
     * 输出:
     * - 解析成功返回 CurrentData.
     * - 解析失败抛出 IOException.
     */
    public static CurrentData decode(Path path) throws IOException {
        byte[] buf = Files.readAllBytes(path);
        if (buf.length == 0) {
            throw new IOException("文件为空: " + path);
        }
        if (buf.length > MAX_DATA_LENGTH) {
            throw new IOException("文件过大(> " + MAX_DATA_LENGTH + " bytes): " + path);
        }

        // ---------- 1. 在前 80 字节内寻找 16 个空格， ----------
        int[] pos = new int[16];
        int j = 0;
        int limit = Math.min(80, buf.length);
        for (int i = 0; i < limit && j < 16; i++) {
            if (buf[i] == ' ') {
                pos[j++] = i;
            }
        }
        if (j < 16) {
            throw new IOException("头部格式异常：未找到 16 个空格，文件=" + path);
        }

        // start = pos[15] + 2，假定头部行以 CRLF (\r\n) 结束
        int start = pos[15] + 2;
        if (start >= buf.length) {
            throw new IOException("数据区起始位置超出文件长度，文件=" + path);
        }

        // ---------- 2. 解析头部各字段 ----------
        int station = parseIntField(buf, 0, pos[0]);
        int line = parseIntField(buf, pos[0], pos[1]);
        int year = parseIntField(buf, pos[1], pos[2]);
        int month = parseIntField(buf, pos[2], pos[3]);
        int day = parseIntField(buf, pos[3], pos[4]);
        int hour = parseIntField(buf, pos[4], pos[5]);
        int minute = parseIntField(buf, pos[5], pos[6]);
        int second = parseIntField(buf, pos[6], pos[7]);

        String microSecond = parseStringField(buf, pos[7], pos[8]);
        String gpsFrequency = parseStringField(buf, pos[8], pos[9]);

        int gpsFlag = parseIntField(buf, pos[9], pos[10]);
        int breakFlag = parseIntField(buf, pos[10], pos[11]);
        int startupType = parseIntField(buf, pos[11], pos[12]);
        double startupValue1 = parseDoubleField(buf, pos[12], pos[13]);
        double startupValue2 = parseDoubleField(buf, pos[13], pos[14]);
        double startupValue3 = parseDoubleField(buf, pos[14], pos[15]);

        // ---------- 3. 解析数据区（三相波形） ----------
        int rawDataBytes = buf.length - start;
        if (rawDataBytes < 0) {
            throw new IOException("数据区长度为负，文件=" + path);
        }

        int dataLength = rawDataBytes / 6; // 每个采样点 3 相 * 2 字节 = 6 字节
        if (dataLength <= 0) {
            throw new IOException("数据点数为 0，文件=" + path);
        }

        double[] dataA = new double[dataLength + 150];
        double[] dataB = new double[dataLength + 150];
        double[] dataC = new double[dataLength + 150];

        // 小于 32769 点时按 12bit 编码解码，否则按 16bit 短整型解码
        if (dataLength < 32769) {
            // 12bit 数据：((b1 << 4) | b0) - 0x800
            for (int i = 0; i < dataLength; i++) {
                int base = start + i * 6;
                int a0 = buf[base] & 0xFF;
                int a1 = buf[base + 1] & 0xFF;
                int b0 = buf[base + 2] & 0xFF;
                int b1 = buf[base + 3] & 0xFF;
                int c0 = buf[base + 4] & 0xFF;
                int c1 = buf[base + 5] & 0xFF;

                dataA[i] = ((a1 << 4) | a0) - 0x800;
                dataB[i] = ((b1 << 4) | b0) - 0x800;
                dataC[i] = ((c1 << 4) | c0) - 0x800;
            }
        } else {
            // 16bit 小端短整型
            for (int i = 0; i < dataLength; i++) {
                int base = start + i * 6;
                short a = (short) ((buf[base] & 0xFF) | ((buf[base + 1] & 0xFF) << 8));
                short b = (short) ((buf[base + 2] & 0xFF) | ((buf[base + 3] & 0xFF) << 8));
                short c = (short) ((buf[base + 4] & 0xFF) | ((buf[base + 5] & 0xFF) << 8));

                dataA[i] = a;
                dataB[i] = b;
                dataC[i] = c;
            }
        }

        return new CurrentData(
                station,
                line,
                year,
                month,
                day,
                hour,
                minute,
                second,
                microSecond,
                gpsFrequency,
                gpsFlag,
                breakFlag,
                startupType,
                startupValue1,
                startupValue2,
                startupValue3,
                dataLength,
                dataA,
                dataB,
                dataC,
                path.getFileName().toString());
    }

    // ------------------------- 头部字段解析辅助方法 -------------------------

    /**
     * 将 [from, to) 范围内的字节解析为 int.
     * 空字符串返回 0.
     */
    private static int parseIntField(byte[] buf, int from, int to) {
        String s = parseStringField(buf, from, to);
        if (s.isEmpty()) {
            return 0;
        }
        return Integer.parseInt(s);
    }

    /**
     * 将 [from, to) 范围内的字节解析为 double.
     * 空字符串返回 0.0.
     */
    private static double parseDoubleField(byte[] buf, int from, int to) {
        String s = parseStringField(buf, from, to);
        if (s.isEmpty()) {
            return 0.0;
        }
        return Double.parseDouble(s);
    }

    /**
     * 从 [from, to) 区间提取 ASCII 文本字段, 去掉前后空白.
     *
     * 输入:
     * - buf: 原始字节数组.
     * - from, to: 字节区间.
     *
     * 输出:
     * - 去掉空白后的字符串.
     */
    private static String parseStringField(byte[] buf, int from, int to) {
        int begin = Math.max(0, from);
        int end = Math.min(buf.length, to);
        // 去掉开头结尾的空白字符
        while (begin < end && isWhitespace(buf[begin])) {
            begin++;
        }
        while (end > begin && isWhitespace(buf[end - 1])) {
            end--;
        }
        if (end <= begin) {
            return "";
        }
        return new String(buf, begin, end - begin, StandardCharsets.US_ASCII);
    }

    /**
     * 判断单个字节是否为空白字符.
     */
    private static boolean isWhitespace(byte b) {
        return b == ' ' || b == '\t' || b == '\r' || b == '\n';
    }
}
