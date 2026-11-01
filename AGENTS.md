# AGENTS.md — `ss-screen` 项目的 AI 助手工作规则

本文件为所有在本仓库中工作的 AI 助手提供跨会话、稳定且权威的操作规则。开始任何工作前，必须先完整阅读本文件。

## 0. 激活 WSL 项目环境（强制）

当前工作副本位于：

```text
/home/zuolong/projects/ss-screen-learning-20260722
```

本项目使用项目目录内的独立 Python 环境。每次开始工作时，必须先进入仓库并激活环境：

```bash
cd /home/zuolong/projects/ss-screen-learning-20260722
source .venv/bin/activate
```

- Python、`pip`、`pytest`、`ruff`、`black`、`ss-screen` 以及所有项目脚本，都必须在已激活的项目环境中运行。
- 禁止使用 WSL 系统 Python，禁止把项目依赖安装到全局环境。
- 开始 Python 工作前，必须确认 `python --version` 显示 Python 3.11，并确认 `python -c "import ssscreen; print(ssscreen.__version__)"` 可以成功执行。
- Shell 环境激活状态不会跨独立的非交互式工具调用保留。此类情况下，每次调用都必须重新激活环境，或者显式使用 `.venv/bin/` 下的对应程序。
- 如果 `.venv` 缺失或损坏，必须停止工作并报告问题，不得静默切换到其他 Python 环境。

## 1. 仓库范围与只读边界（硬性规则）

**只允许在以下目录内创建、修改或删除文件：**

```text
/home/zuolong/projects/ss-screen-learning-20260722/
```

除非用户明确授权，否则该工作副本之外的所有路径均视为**只读**。下方提到的历史上游路径仅作为参考资料。

下列路径均相对于本文件所在的 `ss-screen/` 目录；只读的同级目录位于 `../`。

| 路径 | 状态 | 用途 |
|---|---|---|
| `./` | ✅ **可读写** | 当前正在构建的正式软件包 |
| `../pair-screening/` | 🔒 只读 | `envmatch` 与分组算法的来源 |
| `../mp-condense/` | 🔒 只读 | robocrys condensation worker 的来源 |
| `../wbm-dataset/` | 🔒 只读 | WBM 数据预处理逻辑的来源 |
| `../screen-mbj/`、`../screen-promising/`、`../screen-antiperovskite/` | 🔒 只读 | DFT 启动逻辑参考 |
| `../rocksalt/`、`../zincblend/`、`../Chalcopyrite /` | 🔒 只读 | 原型结构研究 notebook |
| `../simple-defects/` | 🔒 只读 | 缺陷排序逻辑参考 |
| `../old-screen-202411/` | 🔒 只读 | 历史基线快照 |
| `../*.aiida`、`../*.tar.gz` 和大型数据 | 🔒 只读 | 严禁修改 |

对于只读目录：可以阅读和研究，但禁止在 `ss-screen/` 之外写入、编辑、重命名、移动或删除任何内容。

经过筛选的历史 notebook 和源代码可以复制到仓库内，优先放入 `references/`，以便记录科研来源。复制时应尽量保留原始内容，并记录来源路径、快照日期、版本或校验和。复制前必须删除秘密信息以及嵌入或相邻的生成数据、大型数据，并确认许可证允许再分发。

完整数据集、`.aiida` 转储、压缩包、计算输出及其他大型数据必须留在仓库外，禁止复制或提交。归档副本只作为历史参考；`src/` 下经过测试的代码才是权威实现。如果问题逻辑上属于只读上游目录，应在 `ss-screen/` 内实现修复，并在 `docs/PROJECT_LOG.md` 的“上游问题”中记录。

## 2. 项目使命

本项目要构建一个正式、经过测试且文档完整的 Python 软件包与命令行工具：**`ss-screen`**。

它用于筛选能够形成带隙可调固溶体（合金）的材料组合，并把 `HC/` 科研工作区中的 notebook 和辅助模块迁移为版本化软件包。

完整设计位于 `docs/PROJECT_PLAN.md`。规划任何工作前都必须重新阅读该文件；它是项目范围和里程碑的权威来源。

## 3. 跨会话连续性（强制）

本项目会跨多个工作会话持续开发，因此：

- 每次开始工作时，必须按以下顺序阅读：
  1. `AGENTS.md`（本文件）；
  2. `ZMD/README.md`（工作区路径导航和阅读入口）；
  3. `docs/PROJECT_LOG.md`（已完成工作、下一步和阻塞项）；
  4. `docs/PROJECT_PLAN.md`（总体设计与里程碑状态）。
- 每次结束工作或交接前，必须使用第 5 节模板，在 `docs/PROJECT_LOG.md` 顶部追加一条带日期的记录。
- 修改任何真实文件前，必须在 ZMD 中找到对应分区、真实路径、关联测试和文档，再阅读目标文件。
- 新增、修改、删除、移动或重命名真实文件后，必须在同一工作会话更新对应 ZMD 页面，并在 `ZMD/07_版本与变更索引/README.md` 登记同步记录。
- 如果 ZMD 与当前文件系统不一致，以当前真实文件系统为准；不得恢复用户已经删除的内容，必须修正失效导航并检查相对链接。

项目日志是“当前进展位置”的唯一权威来源。不得假设对话历史或模型记忆会跨会话保留。

## 4. 工作约定

- 使用 Python 3.10 或更高版本、`src/` 目录布局、类型提示、`ruff` 和 `black`。
- 禁止硬编码路径。所有文件位置必须来自 CLI 参数或配置文件。
- 禁止在代码中保存秘密信息。Materials Project API 密钥必须通过 `MP_API_KEY` 环境变量或标准配置提供，严禁提交。
- 禁止使用无名称的魔法数字。数值阈值必须定义为具名参数，参见 `config.py`。
- 移植算法时必须注明来源，例如：`# 移植自 pair-screening/screening-binary.ipynb cell 15`。
- 经批准的历史 notebook 和源代码快照存放在 `references/`，并记录来源信息；不得引入秘密、生成输出、依赖环境、压缩包或完整数据集。
- 移植到 `pair/` 和 `data/` 的核心功能必须有测试。`workflow/` 和 `defects/` 等 DFT/缺陷模块应在可行范围内提供冒烟测试。
- 只有用户明确要求时才创建 Git 提交。保持工作树中没有大型数据。历史 notebook/源码快照可以在 `references/` 中跟踪，数据集必须保留在外部；只有微型测试夹具可以提交到 `tests/data/`。
- 禁止提交多 GB 的 `.aiida` 转储、`*.tar.gz` 或完整数据集。

## 5. `PROJECT_LOG.md` 记录模板

新记录必须添加在文件顶部，保持内容客观、简洁。

```markdown
## YYYY-MM-DD — <简短标题>

**本次工作目标：** <一行说明>

**已完成：**
- <具体完成内容及文件路径>

**决策 / 计划变更：**
- <相对于 PROJECT_PLAN.md 的任何变化及原因>

**下一步：** <紧接着需要完成的工作>

**阻塞项 / 上游问题：** <只读上游目录中发现但未修改的问题>
```

## 6. 禁止事项

- 未经用户明确要求，不得运行 notebook、DFT 作业或 AiiDA daemon。
- 不得把依赖安装到系统环境。依赖必须安装到已激活的项目 `.venv` 中；优先使用 editable 安装方式，例如 `python -m pip install -e .`。
- 未事先读取的 `ss-screen/` 文件不得删除或覆盖。
- 不得猜测包名、技能名或 API；移植前必须在只读来源中核实。
- 如果先前会话摘要与 `PROJECT_LOG.md` 或 `PROJECT_PLAN.md` 冲突，必须以项目文档为准并记录冲突。
