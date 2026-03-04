## 双端行波测距公式 `double_end_by_times` 逐行解释

本文解释的是 Python 文件 `double_end_fault_location.py` 中的这一段代码，让不懂编程的人也能看懂它在做什么。

```python
def double_end_by_times(
    line_length_km: float,
    wave_speed_km_per_ms: float,
    t_a_ms: float,
    t_b_ms: float,
) -> DoubleEndResult:
    """
    双端行波故障测距.

    数学关系:
    - tA = d / v
    - tB = (L - d) / v
    - d = (L + v * (tA - tB)) / 2

    返回:
    - DoubleEndResult, 包含距 A 端和 B 端的距离, km.
    结果自动限制在 [0, L] 之内.
    """

    L = line_length_km
    v = wave_speed_km_per_ms
    d_from_a = (L + v * (t_a_ms - t_b_ms)) / 2.0
    d_from_a = max(0.0, min(L, d_from_a))
    d_from_b = L - d_from_a
    return DoubleEndResult(distance_from_a=d_from_a, distance_from_b=d_from_b)
```

下面逐行用**自然语言**解释。

---

### 1. 函数名称与含义

```python
def double_end_by_times(
```

- **意思**：定义一个叫做 `double_end_by_times` 的“函数”（可以理解为一个可重复使用的小公式或小工具）。
- **用途**：根据**双端测量到的行波到达时间**，计算故障点离两端的距离。

---

### 2. 输入参数（函数括号里的东西）

```python
    line_length_km: float,
    wave_speed_km_per_ms: float,
    t_a_ms: float,
    t_b_ms: float,
) -> DoubleEndResult:
```

这四个是“输入条件”，都是实数（`float`）类型：

- **`line_length_km`**：线路总长度 \(L\)，单位是 **公里（km）**。
  - 例如：300 表示整条线长 300 km。
- **`wave_speed_km_per_ms`**：行波传播速度 \(v\)，单位是 **公里/毫秒（km/ms）**。
  - 例如：200 表示行波每毫秒跑 200 km，相当于 \(2\times 10^5\) km/s。
- **`t_a_ms`**：故障行波到达 **A 端** 的时间 \(t_A\)，单位是 **毫秒（ms）**。
- **`t_b_ms`**：故障行波到达 **B 端** 的时间 \(t_B\)，单位也是 **毫秒（ms）**。

右边的 `-> DoubleEndResult` 表示：

- **这个函数的输出结果**会被包装成一个 `DoubleEndResult` 对象，里面包含：
  - `distance_from_a`：故障点到 A 端的距离（km）；
  - `distance_from_b`：故障点到 B 端的距离（km）。

换句话说：**给我 L、v、tA、tB，我给你一对“到 A 端/到 B 端的距离”。**

---

### 3. 数学公式说明（文档字符串）

```python
    """
    双端行波故障测距.

    数学关系:
    - tA = d / v
    - tB = (L - d) / v
    - d = (L + v * (tA - tB)) / 2
    """
```

这段是给人看的“说明文字”（不会参与计算），讲的是双端行波测距的数学模型：

- 设：
  - \(L\)：线路总长；
  - \(v\)：行波速度；
  - \(d\)：故障点到 A 端的距离；
  - \(t_A\)：故障行波到达 A 端的时间；
  - \(t_B\)：故障行波到达 B 端的时间。

则有：

1. **从 A 端看**：行波从故障点到 A 端走了一段距离 \(d\)，速度是 \(v\)，所以时间是：
   \[ t_A = \dfrac{d}{v} \]
2. **从 B 端看**：行波从故障点到 B 端走了一段距离 \(L - d\)，所以时间是：
   \[ t_B = \dfrac{L - d}{v} \]
3. 把上面两式联立、整理，可以解出 \(d\) 为：
   \[ d = \dfrac{L + v\,(t_A - t_B)}{2} \]

这正是最后一行公式的来源。

---

### 4. 把输入参数“起个短名字”方便后面使用

```python
    L = line_length_km
    v = wave_speed_km_per_ms
```

- 这两行只是**起了两个缩写变量**，让公式更好看：
  - 把 `line_length_km` 记为 `L`；
  - 把 `wave_speed_km_per_ms` 记为 `v`。
- 后面所有计算都用 `L` 和 `v`，避免每次写一串长名字。

---

### 5. 按公式算出“未裁剪的”距离

```python
    d_from_a = (L + v * (t_a_ms - t_b_ms)) / 2.0
```

- 这就是刚才的数学公式：

\[ d = \dfrac{L + v\,(t_A - t_B)}{2} \]

- 代码里做的事情是：
  - 用 `t_a_ms` 代表 \(t_A\)，`t_b_ms` 代表 \(t_B\)；
  - 先算括号里的 `L + v * (t_a_ms - t_b_ms)`；
  - 再除以 2，得到一个浮点数，赋值给 `d_from_a`。

注意：

- 此时的 `d_from_a` 在**数学上是正确公式的结果**，但在数值上可能：
  - 小于 0（表示“在 A 端外面”）；
  - 大于 L（表示“在 B 端外面”）；
  - 只有落在 \([0, L]\) 才是“在线路上”的物理解。

---

### 6. 把结果限制在线路范围内

```python
    d_from_a = max(0.0, min(L, d_from_a))
```

这一行做的是一个**“裁剪（clamp）”** 操作：

- `min(L, d_from_a)`：
  - 如果 `d_from_a` > L，就取 L；
  - 否则就取原值。
- `max(0.0, 前面的结果)`：
  - 如果结果 < 0，就取 0；
  - 否则取原值。

合起来等价于：

\[ d_{\text{from A}} = \begin{cases}
0, & d < 0 \\
d, & 0 \le d \le L \\
L, & d > L
\end{cases} \]

也就是说：

- **最终的 `d_from_a` 一定在 0 到 L 之间**；
- 若原始计算得到的 `d` 落在线路左侧，就认为故障点“贴在 A 端”；
- 若落在线路右侧，就认为故障点“贴在 B 端”。

这样做的原因是：

- 实际工程里，测得的 \(t_A, t_B\) 可能有偏差；
- 允许算法“超出一点”，但最后强制认为故障点不可能跑到线路外面去。

---

### 7. 算出故障点到 B 端的距离

```python
    d_from_b = L - d_from_a
```

这一行很直观：

- 既然线路总长是 L，故障点到 A 端是 `d_from_a`，那**到 B 端的距离**就是：

\[ d_{\text{from B}} = L - d_{\text{from A}} \]

代码里就是把这个差值存到 `d_from_b` 变量里。

---

### 8. 打包结果返回

```python
    return DoubleEndResult(distance_from_a=d_from_a, distance_from_b=d_from_b)
```

最后这一行把两个距离放进一个“结果盒子”里返回：

- `distance_from_a=d_from_a`：
  - 故障点离 A 端的距离（km）；
- `distance_from_b=d_from_b`：
  - 故障点离 B 端的距离（km）。

上层代码只要调用：

```python
result = double_end_by_times(...)
```

就可以通过：

- `result.distance_from_a` 看到“故障距 A 端多少 km”；
- `result.distance_from_b` 看到“故障距 B 端多少 km”。

---

### 9. 小结（给非程序员的直观理解）

可以把这个函数理解成一个“黑盒计算器”，它做的事情是：

1. 你告诉它：
   - 线路全长 \(L\)；
   - 行波速度 \(v\)；
   - 故障波到 A 端的时间 \(t_A\)；
   - 故障波到 B 端的时间 \(t_B\)。
2. 它根据物理公式：

   \[ d = \dfrac{L + v\,(t_A - t_B)}{2} \]

   算出故障点到 A 端的理论距离 \(d\)；
3. 如果这个 \(d\) 落在 0 到 L 之外，就强行“拉回”到 0 或 L，保证故障点不会跑到线路外面；
4. 再用 \(L - d\) 算出到 B 端的距离；
5. 最后把“距 A 端 / 距 B 端”的两个数一起返回给调用者使用。

这么理解即可：**这是一个把「时间差」翻译成「空间位置」的小工具，前提是你给它的线路长度和行波速度是可信的。**

