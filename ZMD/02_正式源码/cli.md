# CLI 导航

真实入口：[`src/ssscreen/cli/app.py`](../../src/ssscreen/cli/app.py)

包入口：[`src/ssscreen/cli/__init__.py`](../../src/ssscreen/cli/__init__.py)

`pyproject.toml` 把终端命令 `ss-screen` 映射到 `ssscreen.cli.app:cli`。

桌面入口 `ss-screen-gui` 映射到 `ssscreen.gui.launcher:main`，但 GUI 只作为前端调用本页所述真实 CLI；不得把 `cli/app.py` 替换为预览或 mock 命令面。

`ss-screen --version` 输出固定的纯 ASCII `SS-SCREEN` 启动 Logo 和软件版本；该输出由 `VERSION_BANNER` 及 eager Click 回调实现，适用于真实终端、自动测试和操作手册截图。

## 命令清单

| 命令 | 阶段 | 主要实现 |
|---|---|---|
| `dataset mp` | MP 数据标准化及数据库/query provenance | [`data/mp.py`](../../src/ssscreen/data/mp.py) |
| `dataset wbm` | WBM extxyz 标准化 | [`data/wbm.py`](../../src/ssscreen/data/wbm.py) |
| `dataset structures` | 本地 POSCAR/CIF/vasp/json 结构文件夹标准化 | [`data/structures.py`](../../src/ssscreen/data/structures.py) |
| `valence-filter` | 价态预过滤 | [`pair/filters.py`](../../src/ssscreen/pair/filters.py) |
| `composition-screen` | 组成模板候选 | [`pair/grouping.py`](../../src/ssscreen/pair/grouping.py) |
| `condense` | 生成 robocrys 描述 | [`data/condense.py`](../../src/ssscreen/data/condense.py) |
| `condense-index` | 建立归档索引 | [`data/condense.py`](../../src/ssscreen/data/condense.py) |
| `condense-validate` | 校验归档 | [`data/condense.py`](../../src/ssscreen/data/condense.py) |
| `structure-match` | 局部环境匹配 | [`pair/structure_match.py`](../../src/ssscreen/pair/structure_match.py) |
| `gap-export` | 版本化任务、JSON/CIF/POSCAR 结构和结果/方法模板导出 | [`pair/gap_export.py`](../../src/ssscreen/pair/gap_export.py) |
| `gap-collect-vasp` | 批量扫描 `task_id/vasprun.xml[.gz]`，提取带隙、directness、跃迁、收敛和VASP版本，并审计四种状态 | [`pair/gap_collect_vasp.py`](../../src/ssscreen/pair/gap_collect_vasp.py) |
| `gap-validate` | 外部 gap 结果身份/schema/数值校验，输出规范表、拒绝表和审计报告 | [`pair/gap_export.py`](../../src/ssscreen/pair/gap_export.py) |
| `pair` | gap 回填和材料对枚举 | [`pair/gap_feedback.py`](../../src/ssscreen/pair/gap_feedback.py)、[`pair/pairing.py`](../../src/ssscreen/pair/pairing.py) |
| `gap-compare` | 多理论方法比较 | [`pair/gap_feedback.py`](../../src/ssscreen/pair/gap_feedback.py) |
| `stability sqs-generate` | 初步合金结构生成 | [`stability/sqs.py`](../../src/ssscreen/stability/sqs.py) |
| `stability relax` | MACE 弛豫和能量/力/应力结果 | [`stability/mlp.py`](../../src/ssscreen/stability/mlp.py)、[`stability/relax.py`](../../src/ssscreen/stability/relax.py) |
| `stability mixing-enthalpy` | 同能量基准的 SQS 混合焓 | [`stability/thermodynamics.py`](../../src/ssscreen/stability/thermodynamics.py) |
| `stability phonon-export` | Phonopy 参考/位移超胞和任务 manifest | [`stability/phonon.py`](../../src/ssscreen/stability/phonon.py) |
| `stability phonon-forces` | MACE 固定结构能量/力/应力和断点续算 | [`stability/mlp.py`](../../src/ssscreen/stability/mlp.py)、[`stability/phonon.py`](../../src/ssscreen/stability/phonon.py) |
| `stability phonon-collect` | 力常数、网格、频带、DOS、图和状态汇总 | [`stability/phonon.py`](../../src/ssscreen/stability/phonon.py) |
| `stability phonon-run` | MACE 声子谱端到端便捷入口 | [`stability/phonon.py`](../../src/ssscreen/stability/phonon.py) |
| `stability competing-export` | 从 MP API 或显式离线快照导出竞争相结构/manifest | [`stability/competing.py`](../../src/ssscreen/stability/competing.py) |
| `stability competing-relax` | 使用同一 MACE 契约弛豫竞争相 | [`stability/competing.py`](../../src/ssscreen/stability/competing.py)、[`stability/relax.py`](../../src/ssscreen/stability/relax.py) |
| `stability convex-hull` | 严格同源能量凸包、分解和完整性审计 | [`stability/competing.py`](../../src/ssscreen/stability/competing.py) |
| `stability phase-diagram` | MP API/离线查询、MACE 弛豫和凸包端到端入口 | [`stability/competing.py`](../../src/ssscreen/stability/competing.py) |
| `recommend` | 汇总 Stage 5、8--10 和可选缺陷证据，生成三类推荐、L2--L6、报告和 summary | [`stability/recommendation.py`](../../src/ssscreen/stability/recommendation.py) |
| `group` | 兼容的一步式分组入口 | grouping、structure matching 和 filters |

## 维护规则

- 新增、删除或重命名命令时，同时更新本页、根 [`README.md`](../../README.md) 和 [`tests/test_cli.py`](../../tests/test_cli.py)。
- 参数默认值必须来自具名配置或明确的 Click option，不得在多个命令中复制魔法数字。
- CLI 文件契约变化时，同步更新算法/教程文档和 ZMD 的数据流说明。

## 最近同步

- 2026-09-11：新增 `dataset structures`，支持从本地 POSCAR/CIF 文件夹或单文件生成 Stage 1 DataFrame；
  GUI 数据源页可调用该命令作为本地结构初筛入口。
- 2026-09-07：恢复并保留真实 CLI 入口，新增独立 `ss-screen-gui`；GUI 集成不改变
  `ss-screen` 的科学命令行为。
- 2026-08-24：完善批量优先的 `gap-collect-vasp`；增加 `--method-metadata`，`--report` 可省略，missing任务保留结果行，报告增加逐任务错误和未知目录。
- 2026-08-24：`--version` 改为显示 `SS-SCREEN` ASCII 启动 Logo 和 `SS-Screen version 1.0`，并由 CLI 回归测试固定输出契约。
- 2026-08-03：新增顶层 `recommend`，支持 gap 方法覆盖、可选/强制缺陷、具名阈值、CSV/Markdown/JSON 输出。
- 2026-08-03：`dataset mp` 新增 `--provenance`；默认写出 `<output>.provenance.json`，离线数据库参数存在时先校验为真实文件。
- 2026-08-01：`competing-export`/`phase-diagram` 增加 `--mp-backend` 与 `--offline-db`；只有 API 后端提示密钥。
- 2026-07-31：扩展 `gap-export`/`gap-validate` 外部计算文件契约；校验存在拒绝行时输出审计文件并返回非零状态。
- 2026-07-31：新增四个 Stage 10 命令；访问 MP 的入口每次隐藏提示 API key，分阶段和一步式产物契约一致。
- 2026-07-31：新增四个 Stage 9 声子命令，支持分阶段大任务和一步式 MACE 运行。
- 2026-07-30：新增 `stability mixing-enthalpy`，输出逐 SQS 混合焓 CSV 和审计汇总 JSON。
- 2026-07-30：新增 `stability relax`，支持模型/设备/精度、端元、全晶胞、续跑和结果路径选项。
- 2026-07-22：根据当前 Click decorators 和 README 命令示例建立初始索引。
