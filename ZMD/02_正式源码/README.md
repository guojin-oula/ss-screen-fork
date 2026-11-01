# 正式源码导航

真实目录：[`src/ssscreen/`](../../src/ssscreen/)

这里的代码是项目当前权威实现。`references/` 中的 notebook 和旧源码只用于追溯来源，不能覆盖 `src/` 的行为结论。

## 模块地图

| 导航页 | 真实目录/文件 | 职责 |
|---|---|---|
| [data.md](data.md) | [`src/ssscreen/data/`](../../src/ssscreen/data/) | MP/WBM 数据标准化、robocrys condensation、文件 I/O |
| [pair.md](pair.md) | [`src/ssscreen/pair/`](../../src/ssscreen/pair/) | 组成模板、环境匹配、过滤、带隙反馈和材料对枚举 |
| [stability.md](stability.md) | [`src/ssscreen/stability/`](../../src/ssscreen/stability/) | SQS、MACE 弛豫/混合焓、有限位移声子谱、MP 竞争相凸包与综合推荐 |
| [cli.md](cli.md) | [`src/ssscreen/cli/`](../../src/ssscreen/cli/) | Click 命令、参数校验和阶段编排 |
| [gui.md](gui.md) | [`src/ssscreen/gui/`](../../src/ssscreen/gui/) | 可选 PySide6 桌面工作台、工程树、参数页和 CLI 子进程调用 |
| 配置 | [`src/ssscreen/config.py`](../../src/ssscreen/config.py) | 所有筛选/推荐阈值、元素排除集合和组成排列 |
| 包入口 | [`src/ssscreen/__init__.py`](../../src/ssscreen/__init__.py) | 包说明与 `__version__` |

## 依赖方向

```text
config.py
   ↓
data/ ─────→ pair/
               ↓
          stability/
               ↑
cli/app.py ─────┴── 编排所有阶段
   ↑
gui/app.py 作为可选前端调用真实 CLI
```

`pair/` 不依赖 AiiDA。`stability/` 的 SQS 核心不加载重型后端；只有显式运行 MACE 弛豫或声子力时才延迟加载 `[mlp]` 中的 MACE/Torch，默认 CI 仍不需要 GPU。

## 推荐阅读顺序

1. [`config.py`](../../src/ssscreen/config.py)
2. [data.md](data.md)
3. [pair.md](pair.md)
4. [cli.md](cli.md)
5. [gui.md](gui.md)
6. [stability.md](stability.md)
7. [测试导航](../03_测试与测试数据/README.md)

## 最近同步

- 2026-09-07：新增可选 `src/ssscreen/gui/` 桌面工作台；`ss-screen-gui` 调用真实 CLI，
  不替代 `ss-screen` 命令行入口。
- 2026-08-03：新增 Stage 11 `stability/recommendation.py`；当前共有 25 个正式 Python 源文件。
- 2026-07-31：新增 Stage 10 MP 竞争相与同 MACE 能量基准凸包；当前共有 24 个正式 Python 源文件。
- 2026-07-31：新增 Stage 9 Phonopy/MACE 声子谱；当时共有 23 个正式 Python 源文件。
- 2026-07-30：新增 Stage 8 混合焓计算与严格能量来源核验；当前共有 22 个正式 Python 源文件。
- 2026-07-30：新增 Stage 7 MACE 后端和可恢复弛豫结果编排。
- 2026-07-22：依据当前 19 个 Python 源文件建立初始模块索引。
