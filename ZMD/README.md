# ss-screen 工作区导航

> ZMD 是本仓库的路径导航与知识索引层。正式代码、测试、项目文档和历史资料仍以真实目录中的文件为准，ZMD 不复制这些内容。

**工作区根路径：** `/vepfs-mlp2/project-battery/zuolong/ss-screen-learning-20260722`

**初始同步日期：** 2026-07-22

## 每次工作的必经入口

1. 阅读 [`AGENTS.md`](../AGENTS.md)。
2. 执行 `source .venv/bin/activate`，确认 Python 3.11 和 `ss-screen` 可用。
3. 回到本页，按任务类型进入对应分区。
4. 先阅读分区导航，再打开真实文件。
5. 修改真实文件后，同步更新对应 ZMD 页面和[版本与变更索引](07_版本与变更索引/README.md)。
6. 检查链接、测试、格式和 [`PROJECT_LOG.md`](../docs/PROJECT_LOG.md)。

## 导航结构

```text
ZMD/
├── README.md                         # 总入口：查找方法、分区地图、权威来源
├── 00_总览与使用规则/               # 工作区树、资产索引、阅读路径、同步规则
├── 01_项目入口与配置/               # 根目录入口、打包配置、许可证和协作规则
├── 02_正式源码/                     # src/ssscreen 的模块级导航
├── 03_测试与测试数据/               # tests/ 与微型夹具的覆盖关系
├── 04_项目文档与开发计划/           # docs/、plans/、路线图和技术审计
├── 05_历史科研资料/                 # references/ 中各研究家族的来源索引
├── 06_脚本与自动化/                 # scripts/ 与 GitHub Actions
├── 07_版本与变更索引/               # ZMD 同步历史和当前变更登记
└── 08_Web平台/                      # Web 控制层、前端、部署与测试导航
```

## 按任务快速查找

| 想做什么 | 先读哪里 | 真实内容位置 |
|---|---|---|
| 理解项目目标和运行方式 | [项目入口与配置](01_项目入口与配置/README.md) | [`README.md`](../README.md)、[`pyproject.toml`](../pyproject.toml) |
| 阅读或修改正式代码 | [正式源码](02_正式源码/README.md) | [`src/ssscreen/`](../src/ssscreen/) |
| 查数据加载与 condensation | [data 导航](02_正式源码/data.md) | [`src/ssscreen/data/`](../src/ssscreen/data/) |
| 查结构匹配与材料配对 | [pair 导航](02_正式源码/pair.md) | [`src/ssscreen/pair/`](../src/ssscreen/pair/) |
| 查 SQS 与 MLP 稳定性预筛 | [stability 导航](02_正式源码/stability.md) | [`src/ssscreen/stability/`](../src/ssscreen/stability/) |
| 查 CLI 命令 | [CLI 导航](02_正式源码/cli.md) | [`src/ssscreen/cli/app.py`](../src/ssscreen/cli/app.py) |
| 查测试或新增回归测试 | [测试与测试数据](03_测试与测试数据/README.md) | [`tests/`](../tests/) |
| 查计划、算法说明或审计 | [项目文档与开发计划](04_项目文档与开发计划/README.md) | [`docs/`](../docs/)、[`plans/`](../plans/) |
| 查旧 notebook 和科研来源 | [历史科研资料](05_历史科研资料/README.md) | [`references/`](../references/) |
| 查资料整理脚本或 CI | [脚本与自动化](06_脚本与自动化/README.md) | [`scripts/`](../scripts/)、[`.github/`](../.github/) |
| 修改后同步导航 | [ZMD 同步更新规则](00_总览与使用规则/ZMD同步更新规则.md) | [`ZMD/`](./) |
| 开发或运行 Web 控制层 | [Web 平台导航](08_Web平台/README.md) | [`web/`](../web/) |

## 项目主数据流

```text
MP / WBM 数据
  → 数据标准化与过滤
  → 组成模板筛选
  → robocrys 局部环境匹配
  → 版本化带隙任务与多格式结构导出
  → 外部高精度计算
  → 返回结果严格校验、回填与材料对枚举
  → 初步 SQS 合金结构生成
  → MACE 结构驰豫与能量/力/应力结果
  → 同能量基准端元参考与 SQS 混合焓
  → Phonopy 有限位移与 MACE 能量/力声子谱
  → Materials Project API/离线快照竞争相结构与同 MACE 能量基准凸包
  → Stage 11 按材料对/SQS 汇总带隙、混合焓、声子、凸包和可选缺陷证据
  → 可审计的 promising / uncertain / low-priority 推荐报告
```

对应实现依次位于 [`data/`](02_正式源码/data.md)、[`pair/`](02_正式源码/pair.md)、[`cli/`](02_正式源码/cli.md) 和 [`stability/`](02_正式源码/stability.md)。

## 权威来源顺序

发生信息冲突时按以下顺序判断：

1. 当前真实文件系统与正式实现；
2. [`AGENTS.md`](../AGENTS.md)；
3. [`docs/PROJECT_LOG.md`](../docs/PROJECT_LOG.md)；
4. [`docs/PROJECT_PLAN.md`](../docs/PROJECT_PLAN.md)；
5. ZMD 导航说明；
6. `references/` 中的历史资料。

ZMD 与真实文件不一致时，必须以真实文件为准，并在同一工作会话修正 ZMD。
