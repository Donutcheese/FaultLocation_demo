# 电网拓扑 + SQLite + 双端行波测距 Demo（可运行）

## 你会得到什么

- 一个很小的电网拓扑：3 个站（A/B/C），2 条线路（A-B、B-C）
- SQLite 数据库（`demo.db`）里保存：
  - 站名（`station`）
  - 线路号与长度、两端站点（`line`）
  - 双端到达时间与波速（`measurement`）
- 一个简化的双端行波测距定位计算：
  - \(t_A = d/v\)
  - \(t_B = (L-d)/v\)
  - \(d = (L + v \cdot (t_A - t_B))/2\)

## 运行方式（Windows / PowerShell）

在项目根目录执行：

```powershell
.\run.ps1
```

或用 cmd：

```bat
run.cmd
```

首次运行会自动下载 `sqlite-jdbc` 到 `deps/`，编译到 `out/`，并运行默认命令 `demo`。

## 可用命令

```powershell
.\run.ps1 init
.\run.ps1 seed
.\run.ps1 simulate
.\run.ps1 locate
```

- `demo`：初始化 + 种子拓扑 + 插入一条样例测距 + 输出定位结果
- `simulate`：只插入一条样例测距记录（演示噪声）
- `locate`：对最新一条测距记录做定位并打印

