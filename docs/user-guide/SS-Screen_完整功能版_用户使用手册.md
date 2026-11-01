# 固溶体可调带隙材料筛选软件用户使用手册

**软件名称：** 固溶体可调带隙材料筛选软件  
**英文名称：** Solid-Solution Screening Software  
**软件简称：** SS-Screen  
**手册版本：** 完整功能版 V1.4  
**当前实现基线：** ss-screen 0.1.0  
**文档语言：** 中文  
**适用对象：** 材料科学、计算材料学和电子结构计算科研用户  
**编制日期：** 2026年8月3日

> **重要说明：** 本手册描述 SS-Screen 的未来完整产品形态。凡标为“完整版本预期接口”的命令，均是为后续开发确定的目标接口，当前 `ss-screen 0.1.0` 尚不能执行。当前已经实现的命令会明确标为“当前可用”。本手册不能直接用来证明当前版本已经具有所有规划功能。

## 文档状态图例

| 标识 | 含义 |
|---|---|
| **[当前可用]** | 已在 `ss-screen 0.1.0` 中实现，并有自动化测试或实际冒烟测试支撑。 |
| **[完整版本预期接口]** | 完整产品的目标命令和文件契约，当前代码尚未提供。 |
| **[外部计算]** | 由 VASP、ABACUS、AiiDA、机器学习势或声子软件执行，SS-Screen 负责导出任务和回收标准结果。 |

## 文档使用方法

- 第一次使用时，建议依次阅读“第一部分 软件概述”“第二部分 安装与配置”和“第三部分 完整科研工作流”。
- 已熟悉流程的用户可以直接查阅“第五部分 CLI与文件契约参考”。
- 任何筛选结果都应结合计算参数、失败记录和缺失数据解释，不能只查看最终排名。
- 文中的路径均为示例相对路径。软件不会随包分发完整 Materials Project、WBM 数据集、VASP 许可证或历史计算目录。

---

# 第一部分 软件概述

## 1. 软件简介

SS-Screen 是一个面向计算材料研究的分阶段命令行软件，用于从大型无机材料数据库中筛选可能形成固溶体、并可通过组分调控带隙的材料端元组合。软件把原本分散在数据处理脚本、Jupyter Notebook 和高性能计算工作流中的步骤整理为可记录、可检查、可恢复的文件流水线。

软件的主要输出不是“已经发现的新材料”，而是带有结构、电子性质、稳定性和缺陷证据的候选体系。科研人员可据此选择进一步开展高精度 DFT、实验合成或器件性质研究的对象。

## 1.1 核心科学问题

目标材料组通常需要同时满足以下条件：

1. 端元具有相同或高度相似的晶体结构原型；
2. 端元之间存在可解释的单一或少量元素替换关系；
3. 一个端元具有接近零的带隙，另一个端元具有较小的半导体带隙；
4. 合金化后有机会使带隙在目标区间内连续变化；
5. 候选体系在热力学、动力学和缺陷层面不存在明显的淘汰信号。

默认阈值只用于形成可复现的研究起点。不同化学体系、计算方法和实验目标需要重新校准阈值。

## 1.2 核心结构匹配思想

SS-Screen 的科学核心是局部环境匹配算法。算法先在组成模板中确定可能被合金化的可变元素位点，再把该元素重标记为占位符 `X`，随后比较 robocrystallographer 生成的局部配位环境描述。

例如，两个化合物虽然元素名称不同，但在将可变元素替换为 `X` 后，如果各位点的配位数、几何环境、连接方式和结构骨架一致，它们就可能被归入同一个同构原型组。

> **科研边界：** 局部环境匹配只能说明“结构上适合进一步研究”。它不能证明材料一定形成连续固溶体，也不能替代相图、混合焓、声子和实验验证。

## 1.3 软件能够解决的问题

- 从 MP/WBM 等数据源构建统一材料表；
- 依据元素数、能量高于凸包、数据库带隙、价态和排除元素进行初筛；
- 按组成模板与 robocrys 环境指纹建立同构材料组；
- 导出高精度带隙计算候选并回收 mBJ/HSE06 等结果；
- 枚举近零带隙端元与小带隙端元构成的候选材料对；
- 生成指定组分和超胞的 SQS 合金结构；
- 执行 MLP 驰豫、初步混合焓、MACE 有限位移声子谱和同 MLP 竞争相凸包；汇总现有证据生成可审计推荐；在完整版本中继续实现缺陷和工作流编排；
- 保存每个阶段的输入、输出、失败、参数和来源，支持复核与断点继续。

## 1.4 完整功能流程图

```text
MP / WBM 数据
  ↓
标准化数据集 → 价态与组成筛选 → robocrys 描述归档 → 同构结构组
  ↓
高精度带隙计算 → 带隙回填与端元配对 → SQS 合金结构
  ↓
MLP 驰豫 → 混合焓 → 声子稳定性 → 相图与竞争相
  ↓
缺陷形成能 → 综合证据分级 → 候选推荐报告
```

## 1.5 阶段与产物总览

| 阶段 | 状态 | 主要输入 | 主要输出 |
|---|---|---|---|
| 1. 数据标准化 | 当前可用 | MP 数据库或 WBM extxyz | `mp.df`、`wbm.df` |
| 2. 价态与组成初筛 | 当前可用 | 标准化 DataFrame | `valid_ids.json`、`composition_candidates.csv` |
| 3. 结构描述归档 | 当前可用 | 标准化 DataFrame 或结构文件 | `condensed/*.json`、manifest、index |
| 4. 同构结构匹配 | 当前可用 | 组成候选、condensed 归档 | `group_df.json` |
| 5. 高精度带隙交接 | 当前可用（计算在外部） | 结构组、原始结构 | `gap_tasks.csv`、`gap_results.normalized.csv` |
| 6. 端元配对与方法比较 | 当前可用 | 结构组、高精度带隙 | `final_pairs.csv`、比较报告 |
| 7. SQS 合金结构 | 当前可用 | 端元对、结构数据集 | 合金结构、`sqs_manifest.jsonl` |
| 8. MLP 结构驰豫 | 当前可用 | SQS 与端元结构 | 驰豫结构、能量、力、应力和状态 |
| 9. 混合焓 | 当前可用 | 同一能量基准的驰豫能量 | `mixing_enthalpy.csv`、`mixing_summary.json` |
| 10. 声子筛选 | 当前可用 | 驰豫结构、MACE模型 | 力常数、频带、DOS、`phonon_summary.csv` |
| 11. 相图与竞争相 | 当前可用 | Stage 7 候选、MP结构、同源MLP能量 | `phase_stability.csv`、`hull_entries.csv` |
| 12. 缺陷计算 | 预期接口 | 候选结构、元素化学势 | `defect_ranking.csv` |
| 13. 综合推荐 | 当前可用 | Stage 5、8--10 证据和可选缺陷表 | `recommendations.csv`、研究报告、可选 summary |
| 14. 工作流编排 | 预期接口 | `project.yaml` | 状态索引、运行日志、阶段产物 |

## 2. 适用范围和限制

## 2.1 适用场景

- 无机晶体中等价或近似等价位点上的置换型固溶体；
- 二元、三元及可明确识别可变元素位点的材料系列；
- 以带隙调控为主目标，并需要兼顾初步稳定性和缺陷证据的高通量研究；
- 需要比较 PBE、mBJ、VASP-HSE06、ABACUS-HSE06 等不同理论层级的研究。

## 2.2 不适用或需要谨慎的场景

- 强无序、非晶、分子晶体或局部环境难以用当前指纹表达的体系；
- 存在复杂磁序、强关联、激子或温度效应但未在计算中显式处理的材料；
- 多位点同时无序且替换关系无法唯一确定的体系；
- 需要直接预测可合成性、相分离动力学或工艺窗口的任务；
- 仅凭数据库带隙就下结论的任务。

## 2.3 结果解释原则

1. 数据库记录是初筛证据，不是最终性质；
2. 结构同构是形成固溶体的必要线索之一，不是充分条件；
3. MLP 能量是预筛信号，不自动等同于 DFT 热力学结论；
4. 未计算、失败和不兼容结果必须保留为缺失证据；
5. `promising` 只表示值得继续研究，不表示已经稳定合成或具有器件性能。

---

# 第二部分 安装与配置

## 3. 运行环境

## 3.1 基本环境

| 项目 | 建议配置 |
|---|---|
| 操作系统 | Linux、WSL2 或高性能计算集群登录节点 |
| Python | 3.10 或更高；本项目验证环境为 3.11 |
| 内存 | 核心筛选建议 16 GB 以上；大型 DataFrame 视数据规模增加 |
| 存储 | 核心代码很小；MP/WBM、结构归档和计算结果需单独规划 |
| 计算资源 | 核心筛选可在 CPU 上运行；DFT、MLP 和声子按后端使用集群/GPU |

## 3.2 当前 WSL 工作副本

当前学习工作区位于：

```bash
cd "$HOME/projects/ss-screen-learning-20260722"
source .venv/bin/activate
```

每次打开新的终端或执行新的非交互式命令，都需要重新激活环境。不要把依赖安装到 WSL 系统 Python。

验证环境：

```bash
python --version
python -c "import ssscreen; print(ssscreen.__version__)"
ss-screen --help
```

预期看到 Python 3.11、当前包版本和命令帮助。

## 4. 安装方式

## 4.1 核心功能

```bash
python -m pip install -e .
```

核心依赖用于数据表处理、结构对象和筛选命令，不自动安装所有计算后端。

## 4.2 可选功能

```bash
# Materials Project 在线接口
python -m pip install -e ".[mp]"

# WBM extxyz 读取
python -m pip install -e ".[wbm]"

# robocrys 结构描述
python -m pip install -e ".[condense]"

# icet SQS
python -m pip install -e ".[sqs]"

# MACE MLP 驰豫；先按集群 CUDA 版本安装兼容的 Torch
python -m pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
python -m pip install -e ".[mlp]"
```

当前已经提供独立的 `mlp` 和 `phonon` 可选依赖。高精度带隙计算固定为外部任务，不提供 `dft`/AiiDA 运行 extra；缺陷后端仍属于后续独立决策范围。只做核心筛选的用户不需要安装 MACE、AiiDA、VASP 插件、phonopy 或缺陷工具链。

## 4.3 安装验证

```bash
python -m pip check
python -m pytest -q
ruff check .
```

在当前基线上，完整测试应通过。来自 `spglib` 的弃用警告不等于测试失败，但应在依赖升级时重新检查。

## 5. Materials Project 配置

## 5.1 离线模式

离线模式使用本地 `mp_offline` 数据库，不需要在每次筛选时访问网络。数据库路径通过 `--offline-db` 提供，或由本地工具的标准配置解析。

`mp_offline` 是独立本地包，不随 `ss-screen` 核心依赖安装；数据库仍保留在项目仓库之外：

```bash
python -m pip install /path/to/mp-offline
```

```bash
ss-screen dataset mp \
  --backend offline \
  --offline-db /path/to/mp-offline.sqlite \
  --output 01_dataset/mp.df \
  --provenance 01_dataset/mp.df.provenance.json
```

离线查询显式排除 deprecated 记录，并只读取 Stage 1 所需字段。默认 provenance
路径为 `<output>.provenance.json`；其中记录查询阈值、数据库绝对路径、文件大小、
SHA-256、样本文档构建元数据、包版本和快照范围警告。完整 SQLite 文件始终保留在
仓库之外。

## 5.2 在线模式

```bash
export MP_API_KEY="由用户在本地安全配置的密钥"
ss-screen dataset mp --backend api --output 01_dataset/mp.df
```

不得把 API 密钥写入：

- Git 仓库；
- `project.yaml`；
- 命令历史示例；
- Notebook 输出；
- manifest、CSV 或报错截图。

## 6. 高精度带隙计算边界

SS-Screen 只负责导出版本化任务和结构，并接收、校验和分析用户在外部平台得到的带隙结果。VASP、ABACUS、AiiDA、调度器、许可证、赝势和集群认证不属于本软件运行时。

外部平台必须保留任务 ID、结构哈希和稳定的方法标识，并按结果模板返回 CSV/JSON。这样可以比较不同泛函和计算器，同时避免核心筛选绑定某套集群或工作流插件。SS-Screen 不保存计算平台密码、SSH 私钥、许可证文件或 POTCAR。

## 7. 研究项目目录

> **[完整版本预期接口——当前代码尚未提供]** 完整版本提供项目初始化命令：

```bash
ss-screen project init \
  --name demo-solid-solution-screen \
  --output my-screening-project
```

建议目录：

```text
my-screening-project/
├── project.yaml
├── 01_dataset/
├── 02_composition/
├── 03_condensed/
├── 04_groups/
├── 05_bands/
├── 06_pairs/
├── 07_sqs/
├── 08_relaxation/
├── 09_thermodynamics/
├── 10_phonons/
├── 11_phase_diagram/
├── 12_defects/
├── 13_report/
└── logs/
```

目录编号表示推荐顺序，不表示所有阶段都必须执行。用户可以只运行核心筛选，也可以从已有的标准化数据、结构组或外部带隙结果继续。

---

# 第三部分 完整科研工作流

## 8. 阶段1：构建标准化数据集

**状态：** [当前可用]

### 8.1 目的

把不同来源的材料记录转换为统一的 pandas DataFrame。后续命令至少需要材料ID、组成、元素数、数据库带隙、能量高于凸包和 `pymatgen.Structure` 结构对象。

### 8.2 Materials Project 数据

离线数据库：

```bash
cd my-screening-project

ss-screen dataset mp \
  --backend offline \
  --offline-db /path/to/mp-offline.sqlite \
  --max-e-hull 0.01 \
  --output 01_dataset/mp.df \
  --provenance 01_dataset/mp.df.provenance.json
```

在线接口：

```bash
ss-screen dataset mp \
  --backend api \
  --max-e-hull 0.01 \
  --output 01_dataset/mp.df
```

关键参数：

| 参数 | 作用 | 当前默认值 |
|---|---|---|
| `--backend` | `offline` 或 `api` 数据源 | `offline` |
| `--offline-db` | 本地 SQLite 数据库 | 可选 |
| `--max-e-hull` | 请求阶段允许的最大凸包能量，单位 eV/atom | `0.01` |
| `--output` | 标准化 pickle DataFrame | 必填 |
| `--provenance` | 数据来源、查询条件、数据库 SHA 和版本信息 JSON | `<output>.provenance.json` |

### 8.3 WBM 数据

```bash
ss-screen dataset wbm \
  --xyz /data/wbm-dataset.xyz \
  --summary /data/wbm-summary.csv \
  --output 01_dataset/wbm.df
```

`--summary` 可省略；如果提供，软件会尽可能保留 WBM 来源字段和元数据。

### 8.4 输出检查

```bash
python - <<'PY'
import pandas as pd

df = pd.read_pickle("01_dataset/mp.df")
print(df.shape)
print(df.columns.tolist())
print(df.index[:5].tolist())
print(df.attrs["ssscreen_mp_dataset_provenance"])
PY
```

检查重点：

- 材料ID唯一；
- `structure` 列可以反序列化；
- 组成和元素数非空；
- 带隙、凸包能量单位一致；
- MP 与 WBM 的来源字段没有混淆。

### 8.5 常见失败

- 在线模式认证失败：检查标准 MP 配置，不要把密钥写进命令文件；
- WBM extxyz 无法读取：确认 ASE 可用、文件没有被截断；
- DataFrame 过大：分数据源保存，不要在此阶段把结构转换成文本 CSV；
- 路径错误：所有输出目录应事先创建，或由未来项目初始化命令创建。

## 9. 阶段2：价态过滤和组成模板初筛

**状态：** [当前可用]

### 9.1 可选价态过滤

```bash
ss-screen valence-filter \
  --df-mp 01_dataset/mp.df \
  --df-wbm 01_dataset/wbm.df \
  --output 02_composition/valid_ids.json
```

该命令使用键价分析判断结构是否能获得合理氧化态。输出是可通过的材料ID列表。它适合排除部分金属、混合价或无法可靠赋价的记录，但不应被解释为严格的化学稳定性判据。

只使用一个数据源时，可以仅提供 `--df-mp` 或 `--df-wbm`。

### 9.2 组成模板筛选

二元体系示例：

```bash
ss-screen composition-screen \
  --df 01_dataset/mp.df \
  --df 01_dataset/wbm.df \
  --valence-ids 02_composition/valid_ids.json \
  --nelems 2 \
  --max-bandgap 1.0 \
  --max-e-hull 0.0 \
  --min-group-size 2 \
  --min-x-elements 2 \
  --output 02_composition/composition_candidates.csv \
  --summary 02_composition/composition_summary.json
```

参数说明：

| 参数 | 解释 |
|---|---|
| `--df` | 可重复提供多个标准化 DataFrame。 |
| `--nelems` | 约化组成中的元素数；当前典型值为2或3。 |
| `--max-bandgap` | 数据库/PBE带隙初筛上限。 |
| `--max-e-hull` | 允许的最大凸包能量。 |
| `--min-group-size` | 一个组成模板至少包含的材料数。 |
| `--min-x-elements` | 可变位点至少出现的不同元素数。 |
| `--excluded-elements` | 在默认排除列表上追加元素。 |

### 9.3 输出解释

`composition_candidates.csv` 是结构匹配前的宽松候选表。它表示材料在组成模板层面可能属于同一个置换系列，还没有证明局部结构相同。

`composition_summary.json` 应记录：

- 输入记录数；
- 各过滤步骤保留/淘汰数量；
- 组成模板数；
- 候选材料数；
- 使用的阈值和排除元素。

如果结果为零，先检查 `--max-e-hull` 是否过严、`--valence-ids` 是否来自相同数据集，以及目标体系是否应使用 `--nelems 3`。

## 10. 阶段3：生成 robocrys 结构描述归档

**状态：** [当前可用]

### 10.1 从标准化 DataFrame 生成

```bash
ss-screen condense \
  --df 01_dataset/mp.df \
  --output-dir 03_condensed/mp/ \
  --manifest 03_condensed/mp_manifest.jsonl \
  --index 03_condensed/mp_index.csv
```

WBM 数据可以输出到另一个目录：

```bash
ss-screen condense \
  --df 01_dataset/wbm.df \
  --output-dir 03_condensed/wbm/ \
  --manifest 03_condensed/wbm_manifest.jsonl \
  --index 03_condensed/wbm_index.csv
```

### 10.2 从结构文件生成

```bash
ss-screen condense \
  --input /path/to/structures/ \
  --output-dir 03_condensed/custom/ \
  --manifest 03_condensed/custom_manifest.jsonl \
  --index 03_condensed/custom_index.csv
```

默认情况下，已存在的 `{material_id}.json` 会被跳过，便于断点续算。只有确认源结构或凝聚参数已经变化时才使用 `--overwrite`。

### 10.3 归档校验

```bash
ss-screen condense-index \
  --condensed-dir 03_condensed/mp/ \
  --output 03_condensed/mp_index_rebuilt.csv

ss-screen condense-validate \
  --condensed-dir 03_condensed/mp/ \
  --output 03_condensed/mp_validation.csv
```

检查原则：

- 每个材料一个 JSON 文件；
- manifest 中的失败不能被静默忽略；
- 索引中的材料ID、化学式和文件路径一致；
- 校验失败的材料在结构匹配前被列出，而不是导致整个任务崩溃。

> **建议：** `--stop-on-error` 只用于调试第一个错误。批量生产运行应保留失败记录并继续处理其他材料。

## 11. 阶段4：局部环境匹配和结构分组

**状态：** [当前可用]

### 11.1 推荐的显式阶段命令

```bash
ss-screen structure-match \
  --candidates 02_composition/composition_candidates.csv \
  --condensed-dir 03_condensed/mp/ \
  --condensed-dir 03_condensed/wbm/ \
  --min-x-elements 2 \
  --output 04_groups/group_df.json \
  --summary 04_groups/structure_match_summary.json
```

该命令读取组成候选，并在 robocrys 描述中执行占位符 `X` 的局部环境比较。输出是结构组 JSON，而不是最终端元对。

### 11.2 兼容的一步式命令

```bash
ss-screen group \
  --df-mp 01_dataset/mp.df \
  --df-wbm 01_dataset/wbm.df \
  --valence-ids 02_composition/valid_ids.json \
  --nelems 2 \
  --condensed-dirs 03_condensed/mp/ \
  --condensed-dirs 03_condensed/wbm/ \
  --output 04_groups/group_df.json
```

`group` 保留用于兼容历史流程。新项目优先使用 `composition-screen` 和 `structure-match` 两步式接口，因为中间淘汰情况更容易检查。

### 11.3 结构组检查

每个结构组至少应能够追溯：

- 组ID；
- 组成模板；
- 可变元素位点；
- 成员材料ID和化学式；
- 原始数据库/PBE带隙；
- 局部环境描述或指纹；
- 来源数据集；
- 缺失/无效 condensed 描述统计。

人工抽查时，应选择几个组对比原始晶体结构，确认算法没有因字符串差异、位点顺序或异常描述把明显不同的原型放在一起。

## 12. 阶段5：高精度带隙计算

**状态：** [当前可用] 候选导出、外部结果模板、严格校验和结果回填均已提供；实际高精度计算由用户在外部完成。

### 12.1 导出候选结构

```bash
ss-screen gap-export \
  --groups 04_groups/group_df.json \
  --dataset 01_dataset/mp.df \
  --method vasp-hse06-pbe54-nosoc-v1 \
  --max-natoms 30 \
  --structure-dir 05_bands/structures/ \
  --structure-format json \
  --structure-format cif \
  --structure-format poscar \
  --results-template 05_bands/gap_results_template.csv \
  --method-metadata-template 05_bands/method_metadata.json \
  --output 05_bands/gap_tasks.csv
```

`--max-natoms` 是成本控制门槛。导出的结构与原子数判断使用同一个 primitive/calculation structure，避免任务表和实际结构不一致。
每条任务包含确定性 `task_id` 和 `structure_sha256`；相同 schema 版本、材料、方法和结构重复导出时任务 ID 不变。

### 12.2 外部计算模式

**状态：** [外部计算]

用户根据 `gap_tasks.csv` 和结构目录在 VASP、ABACUS、AiiDA 或其他平台创建任务。所有材料应尽量使用一致的：

- 结构弛豫策略；
- 泛函和赝势；
- 截断能、k点密度和收敛标准；
- 自旋轨道耦合策略；
- 带隙提取方法；
- 软件版本。

回收结果至少包含：

| 字段 | 含义 |
|---|---|
| `material_id` | 与候选表一致的材料ID。 |
| `formula` | 化学式。 |
| `method` | 如 `vasp-hse06`、`abacus-hse06`、`mbj`。 |
| `band_gap` | 带隙，单位 eV；失败行可为空。 |
| `is_direct` | 是否直接带隙；未知时为空。 |
| `transition` | 带边跃迁信息，可为空。 |
| `status` | `success`、`failed` 或 `skipped`。 |

结果还应保留 `schema_version`、`task_id`、`structure_sha256` 和 `settings_sha256`。方法元数据 JSON 记录计算软件、版本、泛函、SOC、赝势族、几何策略、k 点策略和其他输入摘要；不同设置必须使用不同的稳定方法标识。

若外部平台使用 AiiDA，用户不需要向 SS-Screen 提供 AiiDA profile、PostgreSQL/RabbitMQ、SSH、Computer/Code 标签、调度器凭据或赝势路径。外部收集脚本只需原样保留任务 ID 和结构哈希，填写标准结果字段；可追加 `aiida_process_uuid`、远端任务号或可追溯 URI，校验器会保留这些附加列。任何凭据都不得写入返回文件。

### 12.3 校验和规范化结果

```bash
ss-screen gap-validate \
  --tasks 05_bands/gap_tasks.csv \
  --gaps 05_bands/user_gap_results.csv \
  --method-metadata 05_bands/method_metadata.json \
  --output 05_bands/gap_results.normalized.csv \
  --rejected 05_bands/gap_results.rejected.csv \
  --report 05_bands/gap_validation.json
```

校验会先检查任务表自身的 schema、确定性任务 ID 和结构哈希，再核对返回任务、材料、化学式、方法、结构哈希、方法设置、状态、重复和带隙数值。失败或跳过行的带隙可以为空，但状态必须明确；未知 directness 保持为空。审计报告分别列出未返回任务和已返回但未获接受的任务。存在拒绝行时命令返回非零状态，只有规范化结果进入下一阶段。没有历史任务表时仍可读取旧七列 CSV/JSON，但不具备同等级的结构身份保证。

## 13. 阶段6：回填带隙并枚举端元对

**状态：** [当前可用]

### 13.1 生成最终端元对

```bash
ss-screen pair \
  --groups 04_groups/group_df.json \
  --gap-results 05_bands/gap_results.normalized.csv \
  --method vasp-hse06-pbe54-nosoc-v1 \
  --low-gap 0.15 \
  --direct-min 0.15 \
  --direct-max 1.5 \
  --pair-any-below 0.3 \
  --pair-any-above 0.2 \
  --pair-both-below 0.8 \
  --summary 06_pairs/gap_feedback_summary.json \
  --output 06_pairs/final_pairs.csv
```

当前默认参数用于复现项目现有研究逻辑，不是所有体系的通用物理常数。运行前应把阈值及理由写入研究记录。

### 13.2 参数含义

| 参数 | 用途 |
|---|---|
| `--low-gap` | 近零带隙成员的参考上限。 |
| `--direct-min`、`--direct-max` | 小带隙候选的参考区间。 |
| `--pair-any-below` | 一对端元中至少一个带隙应低于该值。 |
| `--pair-any-above` | 一对端元中至少一个带隙应高于该值。 |
| `--pair-both-below` | 两个端元都需低于的上限。 |
| `--method` | 多方法结果中选择一个理论层级。 |

`is_direct` 在当前流程中默认作为信息字段，而不是强制硬过滤条件。科研人员可以在最终表中追加分析，但不应把字段名称误解为所有结果都经过直接带隙筛选。

### 13.3 比较多个理论方法

```bash
ss-screen gap-compare \
  --groups 04_groups/group_df.json \
  --gap-results 05_bands/gap_results.normalized.csv \
  --output-dir 06_pairs/method_comparison/ \
  --summary 06_pairs/gap_method_comparison.json
```

比较报告应展示：

- 每种方法的材料覆盖率；
- 各方法得到的端元对数量；
- 共同端元对和方法特有端元对；
- 带隙偏移；
- 直接/间接性质变化；
- 因计算失败造成的差异。

如果不同方法覆盖的材料集合不同，不能只比较最终端元对数量，还必须同时报告覆盖率。

## 14. 阶段7：生成 SQS 合金结构

**状态：** [当前可用]

### 14.1 生成单一组分

```bash
ss-screen stability sqs-generate \
  --pairs 06_pairs/final_pairs.csv \
  --dataset 01_dataset/mp.df \
  --target-fraction 0.5 \
  --supercell 2,2,2 \
  --backend icet \
  --cutoff 4.0 \
  --sqs-steps 10000 \
  --seed 0 \
  --output-dir 07_sqs/structures/ \
  --manifest 07_sqs/sqs_manifest.jsonl
```

`target-fraction` 表示端元B在替换位点上的目标比例，取值范围为0到1。建议至少计算若干中间组分，而不仅是 `x=0.5`。

### 14.2 后端选择

- `random`：依赖较轻，适合演示、测试和快速生成随机置换结构；
- `icet`：通过簇空间和 Monte Carlo 搜索更接近随机相关函数的 SQS，适合正式预筛。

使用 `icet` 时，`--cutoff` 可以重复提供以定义更高阶簇截断；所有 cutoff、步数、种子和超胞必须写入 manifest。

### 14.3 输出检查

`sqs_manifest.jsonl` 应至少记录：

- pair ID 和两个端元ID；
- 目标组分；
- 元素替换映射；
- 超胞；
- 生成器、cutoff、步数和随机种子；
- 结构路径；
- 成功/失败状态；
- 已知限制。

检查生成结构的化学计量、替换位点和原子数。小超胞无法精确表示某些分数时，应把实际组分和目标组分同时记录。

## 15. 阶段8：使用机器学习势驰豫

> **[当前可用]** 当前实现提供 MACE 后端、完整能量/力/应力结果、质量检查和断点续算。

### 15.1 目的

使用 MACE 等机器学习势对端元、SQS 和后续竞争相进行一致设置的快速驰豫，为混合焓和稳定性预筛提供能量与结构。该阶段不能替代最终 DFT 验证。

### 15.2 命令

```bash
ss-screen stability relax \
  --manifest 07_sqs/sqs_manifest.jsonl \
  --include-endmembers \
  --backend mace \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --fmax 0.03 \
  --max-steps 500 \
  --output-dir 08_relaxation/ \
  --results 08_relaxation/relaxation_results.jsonl
```

### 15.3 结果契约

每条结果记录：

| 字段 | 内容 |
|---|---|
| `structure_id` | 端元、SQS或竞争相的稳定ID。 |
| `input_structure` | 输入结构路径和哈希。 |
| `output_structure` | 驰豫结构路径和哈希。 |
| `backend` | 后端、模型名称、模型哈希、版本、设备和数据精度。 |
| `energy_total_eV` | 总能，单位 eV。 |
| `energy_per_atom_eV` | 每原子能量，单位 eV/atom。 |
| `forces_eV_per_angstrom` | 每个原子的完整三维力数组。 |
| `max_force_eV_per_angstrom` | 最终最大原子受力，单位 eV/Å。 |
| `stress_eV_per_angstrom3`、`stress_GPa` | 笛卡尔 `3×3` 应力张量及约定。 |
| `steps` | 实际优化步数。 |
| `status` | `success`、`not_converged`、`failed`。 |
| `error` | 失败摘要，不含凭据和远程敏感路径。 |

每个任务还会写入 `records/<structure_id>.json`，弛豫结构写入 `structures/<structure_id>.json`。输入结构哈希、模型哈希和全部设置共同组成运行指纹；一致结果自动续跑，不一致时必须显式使用 `--overwrite`。

### 15.4 质量控制

- 端元和合金必须使用相同的模型、模型版本和能量基准；
- 如果一个结构没有收敛，不能把最后一步能量当成正式成功结果；
- 检查体积突变、原子过近、结构坍塌和异常高力；
- 保存原始结构，禁止用输出覆盖输入。

## 16. 阶段9：计算混合焓

> **[当前可用]** 当前实现从 Stage 7 JSONL 中匹配 SQS 与两个端元，严格检查能量基准，并保留全部成功和失败记录。

### 16.1 定义

对组分 `x` 的合金，初步混合焓按每原子能量计算：

```text
ΔH_mix(x) = E_alloy(x) - [(1-x)E_A + xE_B]
```

其中 `E_A`、`E_B` 和 `E_alloy` 必须使用相同的后端名称与版本、模型文件哈希、数据精度和完整驰豫设置。计算设备可以不同，因为设备不定义势能参考系。

### 16.2 命令

```bash
ss-screen stability mixing-enthalpy \
  --pairs 06_pairs/final_pairs.csv \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --output 09_thermodynamics/mixing_enthalpy.csv \
  --summary 09_thermodynamics/mixing_summary.json
```

### 16.3 输出解释

`mixing_enthalpy.csv` 每个 SQS 保留一行，主要字段包括：

| 字段 | 含义 |
|---|---|
| `pair_index`、`sqs_structure_id` | 端元对和 SQS 的可追踪标识。 |
| `target_fraction_b`、`actual_fraction_b` | 目标组分与实际实现的 B 端元比例。 |
| `fraction_basis` | 组分来源：`actual`、`site_counts` 或 `target_fallback`。 |
| `energy_sqs_per_atom_eV` | SQS 每原子势能。 |
| `energy_endmember_a_per_atom_eV`、`energy_endmember_b_per_atom_eV` | 两个端元的每原子参考势能。 |
| `reference_energy_per_atom_eV` | 按实际组分线性插值得到的端元参考能。 |
| `mixing_enthalpy_eV_per_atom`、`mixing_enthalpy_meV_per_atom` | 两种单位的初步混合焓。 |
| `energy_reference_sha256` | 共同能量基准的摘要，可用于审计。 |
| `status`、`usable_for_screening`、`warnings`、`error` | 计算是否可用于筛选，以及失败或降级原因。 |

程序优先使用 `actual_fraction_b`，其次由替换位点数计算；只有旧记录缺失二者时才回退到目标组分，并写入警告。缺少端元、未收敛或质量检查不合格、能量基准不兼容、端元记录歧义等情况不会被静默丢弃，而会作为失败状态写入 CSV 和汇总 JSON。

- 较负的混合焓通常是有利混合信号；
- 小的正混合焓不自动表示无法形成固溶体，温度和构型熵可能改变结论；
- 大的正混合焓是相分离风险信号；
- 单个 `x=0.5` 点不能描述完整自由能曲线；
- 当前数值是 MLP 势能给出的 0 K 初步估计，不含 `PV` 项、构型熵或振动自由能；
- MLP 结果应作为预筛，重要体系需要一致设置的 DFT 复核。

## 17. 阶段10：声子和动力学稳定性筛选

> **[当前可用]** 当前实现使用 Phonopy 有限位移和 MACE 固定结构能量/力，输出谐波力常数、q 网格、频带、DOS、图和可审计状态。

### 17.1 一步式 MACE 声子谱

声子计算对输入结构残余力敏感。建议先把 Stage 7 的 `--fmax` 收紧到约 `0.001–0.005 eV/Å`；默认超过 `0.01 eV/Å` 的结构不会生成位移任务。

```bash
ss-screen stability phonon-run \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float64 \
  --displacement 0.01 \
  --mesh 20,20,20 \
  --output-dir 10_phonons/
```

未指定 `--supercell` 时，程序按各晶格矢量至少约 10 Å 自动选择对角超胞，并受 `--max-supercell-atoms` 保护。显式设置示例为 `--supercell 2,1,1`。

### 17.2 分阶段与断点续算

大体系可以拆成任务生成、MACE 力计算和结果收集：

```bash
ss-screen stability phonon-export \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --supercell 2,2,2 \
  --displacement 0.01 \
  --output-dir 10_phonons/inputs/ \
  --manifest 10_phonons/phonon_jobs.jsonl

ss-screen stability phonon-forces \
  --manifest 10_phonons/phonon_jobs.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --device cuda:0 --dtype float64 \
  --output-dir 10_phonons/forces/ \
  --results 10_phonons/phonon_force_results.jsonl

ss-screen stability phonon-collect \
  --manifest 10_phonons/phonon_jobs.jsonl \
  --force-results 10_phonons/phonon_force_results.jsonl \
  --mesh 20,20,20 \
  --output-dir 10_phonons/results/ \
  --summary 10_phonons/phonon_summary.csv \
  --report 10_phonons/phonon_summary.json
```

每个位移任务单独保存输入哈希、MACE 模型哈希、能量、完整力、应力、运行时间和状态。相同指纹自动续跑；模型或设置变化需要显式 `--overwrite`。收集阶段要求参考超胞和全部位移结构的力均成功且模型来源一致。

### 17.3 结果与判据

- `structure_id`、pair ID 和组分；
- 超胞、位移幅度、对称容差、Phonopy版本和 MACE 模型哈希；
- 每个位移的 MACE 总能、完整力、应力和力计算覆盖率；
- q 网格和频带最低频率，单位 THz；
- 低于配置阈值的显著虚频模数量和 q 点数量；
- 力常数对称化前后最大漂移、参考力扣除和 NAC 状态；
- `stable`、`unstable`、`uncertain`、`failed` 状态；
- 数值噪声、超胞不足或未收敛警告。

逐结构目录还包含 `force_constants.hdf5`、`phonopy_params.yaml`、`band.yaml`、`phonon_band.csv`、`mesh.npz`、`phonon_dos.csv`、`phonon_band_dos.png` 和 `phonon_band_dos.pdf`。

> **解释注意：** 稳定性分类使用配置化 Gamma-centered q 网格，而不是只看高对称路径图。接近零的小虚频可能来自数值噪声、有限超胞或声学支处理。当前没有 Born 有效电荷和介电张量，因此 `nac_applied=false`；极性材料不包含 LO–TO 非解析修正。谐波 MACE 结果只能表示“在所用模型、超胞和网格上未检测到显著虚频”，不能证明有限温混溶或热力学稳定。

## 18. 阶段11：相图和竞争相分析

> **[当前可用]** 当前版本可使用 Materials Project API 或显式 `mp_offline` SQLite 快照获取竞争相结构，再以与候选一致的 MACE checkpoint 和弛豫设置重算全部能量。

### 18.1 目的

把候选合金与同一化学体系及全部子体系中的元素相、二元/三元竞争相进行比较，判断候选相相对于竞争相组合的能量位置。在线 API 或离线快照只用于获取结构；MP DFT 能量只用于条目筛选溯源，不进入最终 MLP 凸包。

### 18.2 命令

```bash
ss-screen stability phase-diagram \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 --dtype float32 \
  --mp-max-e-hull 0.1 \
  --output-dir 11_phase_diagram/
```

默认 `--mp-backend api` 每次运行都会隐藏提示 `Materials Project API key`。密钥只在当前请求进程中使用，不写入命令参数、manifest、报告或配置文件。

无网络环境使用显式离线快照，不提示密钥：

```bash
ss-screen stability phase-diagram \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --mp-backend offline \
  --offline-db /path/to/mp-offline/data/default.db \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 --dtype float32 \
  --mp-max-e-hull 0.1 \
  --output-dir 11_phase_diagram_offline/
```

离线库没有在线 thermo-entry 的 `thermo_type` 过滤接口。软件会保存数据库 SHA-256、快照范围和警告；`competing_set_complete=true` 仅表示相对于该快照没有缺失任务，不能证明最新 MP 数据中没有新增竞争相。API 与离线结果必须放入不同输出目录，不自动回退或混合。

大规模计算可以拆成：

```bash
ss-screen stability competing-export \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --mp-backend offline \
  --offline-db /path/to/mp-offline/data/default.db \
  --output-dir 11_phase_diagram/inputs/ \
  --manifest 11_phase_diagram/competing_phases.jsonl \
  --report 11_phase_diagram/competing_export_summary.json

ss-screen stability competing-relax \
  --manifest 11_phase_diagram/competing_phases.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --device cuda:0 --dtype float32 \
  --output-dir 11_phase_diagram/relaxation/ \
  --results 11_phase_diagram/competing_relaxation_results.jsonl

ss-screen stability convex-hull \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --competing-manifest 11_phase_diagram/competing_phases.jsonl \
  --competing-results 11_phase_diagram/competing_relaxation_results.jsonl \
  --output 11_phase_diagram/phase_stability.csv \
  --entries-output 11_phase_diagram/hull_entries.csv \
  --summary 11_phase_diagram/phase_stability_summary.json
```

### 18.3 一致性要求

- 候选相与竞争相必须具有相同的后端版本、模型 SHA-256、dtype 和完整弛豫/QC 设置；计算设备可以不同；
- 竞争相 MACE 弛豫失败时禁止回退到 MP DFT 能量；
- 记录数据库条目、查询日期、材料ID、结构哈希和被跳过的相；
- 网络失败不能被解释为“无竞争相”；
- 离线快照的 SHA-256 和范围警告必须保留到最终凸包结果；
- API 与离线快照不得在同一 manifest 中混合；
- 缺少关键竞争相时，状态应为 `uncertain`。

### 18.4 输出解释

`energy_relative_to_competing_hull_eV_per_atom` 保留正负号；负值表示候选相降低现有竞争相凸包。`energy_above_hull_eV_per_atom` 按常规定义截断为非负值。结果还包含最优分解相及分数、`stable`/`metastable_within_cutoff`/`unstable` 信号和竞争集完整性。缺相默认状态为 `incomplete_competing_set` 且不提供可信凸包值；`--allow-incomplete` 只能生成明确标为 uncertain 的诊断结果。

主要产物为 `competing_phases.jsonl`、`competing_relaxation_results.jsonl`、`phase_stability.csv`、`hull_entries.csv` 和 `phase_stability_summary.json`。低凸包能是有利信号，但实际可合成性仍受温度、动力学、无序熵和实验条件影响。

## 19. 阶段12：缺陷生成和空位形成能排序

> **[完整版本预期接口——当前代码尚未提供]**

### 19.1 生成缺陷任务

```bash
ss-screen defects generate \
  --recommendable-structures 11_phase_diagram/phase_stability.csv \
  --defect-types vacancy \
  --charge-states auto \
  --output-dir 12_defects/structures/ \
  --manifest 12_defects/defect_jobs.jsonl
```

### 19.2 启动和收集

```bash
ss-screen defects launch \
  --manifest 12_defects/defect_jobs.jsonl \
  --backend aiida-vasp \
  --profile ss-screen \
  --output 12_defects/submitted_jobs.jsonl

ss-screen defects collect \
  --manifest 12_defects/submitted_jobs.jsonl \
  --output 12_defects/defect_results.jsonl

ss-screen defects rank \
  --results 12_defects/defect_results.jsonl \
  --chemical-potentials 12_defects/chemical_potentials.yaml \
  --output 12_defects/defect_ranking.csv
```

### 19.3 形成能信息

带电缺陷的一般形成能涉及缺陷/本征超胞能量差、元素化学势、费米能级、电荷态和有限尺寸修正。完整结果必须记录：

- 缺陷位点、元素和电荷态；
- 超胞、计算后端和参数；
- 本征参考任务；
- 元素化学势场景；
- 校正方法；
- 形成能随费米能级的关系；
- 收敛和结构重构状态。

如果项目只做中性空位初筛，必须在报告中明确这一限制，不能把它表述为完整缺陷热力学。

### 19.4 排序原则

- 阳离子空位和阴离子空位分开比较；
- 只在相同化学势和一致计算设置下排序；
- 低形成能可能意味着缺陷容易形成，也可能导致补偿或非化学计量；
- 缺陷排名应与带边位置、载流子类型和目标器件性质联合解释。

## 20. 阶段13：生成综合推荐报告（长期路线图 Stage 11）

> **[当前可用]** 推荐命令只做后续研究优先级判断，不代表材料已经稳定、可合成或达到器件性能要求。

```bash
ss-screen recommend \
  --pairs 06_pairs/final_pairs.csv \
  --gap-results 05_bands/gap_results.normalized.csv \
  --mixing-enthalpy 09_thermodynamics/mixing_enthalpy.csv \
  --phonons 10_phonons/phonon_summary.csv \
  --phase-stability 11_phase_diagram/phase_stability.csv \
  --output 13_report/recommendations.csv \
  --report 13_report/recommendation_report.md \
  --summary 13_report/recommendation_summary.json
```

缺陷结果默认可选。已有符合 Stage 11 消费契约的缺陷表时，可以增加 `--defects 12_defects/defect_ranking.csv`；需要把缺陷作为强制证据时再增加 `--require-defects`。当前软件可以消费缺陷证据，但尚未提供缺陷计算命令。

### 20.1 推荐等级

| 等级 | 含义 |
|---|---|
| `promising` | 关键证据完整，未出现明显淘汰信号，值得进入一致设置的高精度验证或实验。 |
| `uncertain` | 存在缺失、方法不一致、边界值或相互冲突的证据，需要补算。 |
| `low-priority` | 出现明确结构、带隙、混合、动力学、竞争相或缺陷风险。 |

默认混合焓阈值为 `25/50 meV/atom`，同 MLP 凸包阈值为 `0.025/0.1 eV/atom`，均可通过 CLI 显式覆盖。这些数值只是初筛起点，不是通用物理常数。明确负面信号优先产生 `low-priority`；没有硬负面但核心证据缺失、边界或不兼容时产生 `uncertain`；核心 L5 证据完整且没有配置判据下的风险时才产生 `promising`。未计算项不能自动当作“通过”。

证据等级与推荐等级相互独立：L2 为结构匹配端元对，L3 增加高精度端元带隙，L4 增加 SQS/MLP 混合焓，L5 增加声子和竞争相凸包，L6 再增加缺陷证据。一个证据完整但声子不稳定的体系可以是 L5，同时为 `low-priority`。

排序依次考虑推荐等级、证据等级、风险/缺失项数量、混合焓、凸包距离和稳定标识，不使用不透明的综合科学分数。direct/indirect 信息保留在结果中，但不作为硬筛选条件。完整算法和输入 schema 见 `docs/algorithm_recommendation.md`。

### 20.2 推荐表最小字段

- recommendation ID；
- pair ID、端元ID和化学式；
- 目标组分范围；
- 带隙方法、端元带隙和覆盖状态；
- SQS/MLP 状态和混合焓摘要；
- 声子状态；
- 相图状态；
- 关键缺陷摘要；
- 推荐等级；
- 正向证据、风险和缺失数据；
- 建议的下一步计算或实验。

## 21. 阶段14：工作流编排与断点续算

> **[完整版本预期接口——当前代码尚未提供]**

自动运行：

```bash
ss-screen workflow run \
  --config project.yaml \
  --from dataset \
  --to recommend
```

查看状态：

```bash
ss-screen workflow status \
  --config project.yaml \
  --output logs/workflow_status.json
```

编排器只调用已经稳定的阶段命令，不能把所有逻辑复制到一个隐藏实现中。每个阶段仍需保留独立产物，用户可以：

- 从任意阶段开始或停止；
- 检查淘汰统计；
- 替换外部计算结果；
- 只重跑失败项；
- 比较不同配置；
- 追溯最终推荐来自哪些输入和参数。

---

# 第四部分 结果解释与科研决策

## 22. 带隙筛选判据

当前端元配对逻辑寻找同一结构组内带隙跨越目标区间的成员。判断时需要同时保留：

- 数据库/PBE带隙；
- 高精度方法带隙；
- 直接或间接性质；
- 计算方法和覆盖状态；
- 原子数和计算成本门槛；
- 端元之间的元素替换关系。

带隙阈值应被理解为筛选参数。系统误差可能使整组材料的带隙一起偏移，但只要同构端元之间仍保持有意义的差异，组分调控仍可能覆盖目标区间。因此，方法间比较和组内相对趋势与绝对数值同样重要。

## 23. 证据等级

| 等级 | 典型证据 | 可以支持的结论 |
|---|---|---|
| L1 数据库初筛 | 组成、PBE带隙、凸包能量 | 值得进入结构检查。 |
| L2 结构匹配 | robocrys环境和可变位点 | 可能属于同构置换系列。 |
| L3 高精度电子结构 | mBJ/HSE06带隙与直接性 | 端元带隙关系更可信。 |
| L4 合金结构与MLP | SQS、驰豫、混合焓 | 初步判断合金结构和混合倾向。 |
| L5 动力学和相竞争 | 声子、相图、竞争相 | 排查明显动力学或分解风险。 |
| L6 缺陷 | 形成能、化学势和电荷态 | 评估缺陷倾向和补偿风险。 |
| L7 一致DFT/实验 | 高精度合金计算或实验 | 支持发表、合成或器件研究结论。 |

推荐报告应显示每个候选达到的最高证据等级，不能把 L2 候选和 L6 候选放在同一“通过”列表而不加区分。

## 24. 缺失数据处理

缺失数据分为：

1. `not_requested`：研究设计中没有要求；
2. `pending`：已提交但未完成；
3. `failed`：计算或解析失败；
4. `incompatible`：方法或参考能不兼容；
5. `not_applicable`：该证据不适用于此结构；
6. `missing_source`：输入条目或结构缺失。

不得使用 `0`、空字符串或“稳定”代替这些状态。推荐器对关键缺失数据默认给出 `uncertain`，并生成补算建议。

## 25. 淘汰和保留的审计

每个阶段都应产生 summary 或 manifest，回答：

- 输入多少条记录；
- 成功多少；
- 被阈值过滤多少；
- 因缺失数据跳过多少；
- 失败多少；
- 最终输出多少；
- 使用了哪些参数、软件版本和数据快照。

只保存最终 CSV 会丢失候选为什么消失的信息，不符合可复现研究要求。

## 26. 最终科研决策

收到 `recommendations.csv` 后，建议按以下顺序审阅：

1. 检查高优先级候选是否有关键缺失项；
2. 查看端元结构和实际替换位点；
3. 比较不同带隙方法的趋势；
4. 检查 SQS 组分和超胞是否足以代表目标组分；
5. 检查 MLP 能量基准是否一致；
6. 查看虚频、竞争相和缺陷是否互相矛盾；
7. 决定下一步是补算、完整 DFT 还是实验；
8. 将选择理由写入项目报告，而不是只记录排名数字。

---

# 第五部分 CLI与文件契约参考

## 27. 当前命令速查

| 命令 | 必需输入 | 主要输出 |
|---|---|---|
| `dataset mp` | MP后端配置 | 标准化 `mp.df`、provenance JSON |
| `dataset wbm` | WBM extxyz | 标准化 `wbm.df` |
| `valence-filter` | 一个或两个 `.df` | 材料ID JSON列表 |
| `composition-screen` | 可重复 `.df` | 候选CSV、summary JSON |
| `condense` | 结构文件或 `.df` | 每材料JSON、manifest、index |
| `condense-index` | condensed目录 | 索引CSV |
| `condense-validate` | condensed目录 | 校验CSV |
| `structure-match` | 候选CSV、condensed目录 | 结构组JSON、summary |
| `gap-export` | 结构组、数据集 | 任务CSV、多格式结构、结果/方法模板 |
| `gap-validate` | 任务、外部带隙、方法元数据 | 规范化结果、拒绝行、审计报告 |
| `pair` | 结构组、带隙结果 | 端元对CSV、覆盖summary |
| `gap-compare` | 结构组、多方法结果 | 方法端元对、比较JSON |
| `stability sqs-generate` | 端元对、数据集 | 合金结构、manifest |
| `stability relax` | SQS manifest、MACE模型 | 弛豫结构、完整能量/力/应力JSONL |
| `stability mixing-enthalpy` | 端元对、驰豫JSONL | 混合焓CSV、汇总JSON |
| `stability phonon-run` | 驰豫JSONL、MACE模型 | 力常数、频带/DOS、图和summary |
| `stability phonon-export` | 驰豫JSONL | 参考/位移结构、任务manifest |
| `stability phonon-forces` | 声子manifest、MACE模型 | 逐任务能量/力/应力JSONL |
| `stability phonon-collect` | 声子manifest、力JSONL | 力常数、频谱、稳定性summary |
| `stability competing-export` | Stage 7候选、MP密钥或离线数据库 | MP竞争相结构、manifest、查询报告 |
| `stability competing-relax` | 竞争相manifest、MACE模型 | 同源竞争相驰豫JSONL |
| `stability convex-hull` | 候选/竞争相驰豫结果 | `phase_stability.csv`、`hull_entries.csv`、summary |
| `stability phase-diagram` | Stage 7候选、MACE模型、MP密钥或离线数据库 | 一步式Stage 10全部产物 |
| `group` | 数据表、condensed目录 | 兼容结构组JSON |

获取实时参数说明：

```bash
ss-screen --help
ss-screen <command> --help
ss-screen dataset <mp|wbm> --help
ss-screen stability sqs-generate --help
ss-screen stability relax --help
ss-screen stability mixing-enthalpy --help
ss-screen stability phonon-run --help
ss-screen stability phase-diagram --help
ss-screen recommend --help
```

## 28. 完整版本预期命令速查

> **[完整版本预期接口——当前代码尚未提供]**

| 命令 | 作用 |
|---|---|
| `project init` | 创建标准项目目录和配置。 |
| `defects generate/launch/collect/rank` | 缺陷结构、任务和形成能排序。 |
| `workflow run/status` | 分阶段编排、恢复和状态汇总。 |

## 29. 通用文件格式

## 29.1 Pickle DataFrame (`.df`)

用于保存包含 `pymatgen.Structure` 对象的标准化数据。它不是跨语言长期归档格式，应同时保存数据来源、生成软件版本和字段说明。不要用不可信来源的 pickle 文件，因为反序列化可能执行代码。

## 29.2 CSV

用于候选表、带隙结果、端元对、混合焓、声子摘要、相图摘要和推荐表。要求：

- UTF-8 编码；
- 第一行列名；
- 单位在模式文档中固定；
- 缺失值使用空值并由状态字段解释；
- 材料ID和方法组合具有明确唯一性。

## 29.3 JSON

用于结构组、summary 和配置快照。summary 面向一次阶段运行，必须包含输入、输出、计数、参数和失败摘要。

## 29.4 JSONL

用于大量独立任务的 manifest。每行一个完整 JSON 对象，便于并发追加、逐条恢复和流式处理。任务记录应包含稳定ID、输入哈希、状态、输出路径和错误摘要。

## 29.5 晶体结构文件

当前导出可以使用 pymatgen JSON。完整版本可扩展 CIF、POSCAR、extxyz 等格式，但 manifest 中必须注明格式、结构哈希、primitive/conventional 选择和单位。

## 30. 退出码、日志和恢复

完整产品建议使用：

| 退出码 | 含义 |
|---|---|
| `0` | 命令成功，结构化输出完整写入。 |
| `2` | 命令参数或输入模式错误。 |
| `3` | 部分任务失败，但 manifest 已完整记录。 |
| `4` | 后端、凭据或远程服务不可用。 |
| `5` | 输出冲突、哈希不一致或恢复安全检查失败。 |

当前 Click 命令的具体退出行为以实际 `--help` 和运行结果为准。完整版本不应在退出码非零时把不完整输出标为权威结果。

恢复原则：

- 输出先写临时文件，成功后原子替换；
- 已成功且输入哈希相同的任务可以跳过；
- 输入或关键参数变化时必须创建新记录；
- manifest 不删除失败历史；
- `--overwrite` 必须由用户明确使用。

## 31. 可复现性清单

每次正式研究至少保存：

- Git 提交或软件版本；
- Python和依赖版本；
- MP/WBM 数据快照；
- 全部命令和 `project.yaml`；
- 输入文件哈希；
- 筛选阈值；
- condensed manifest和校验表；
- 高精度计算方法和任务来源；
- MLP模型名称、版本和设备；
- SQS超胞、cutoff、步数和种子；
- 声子、相图、缺陷参数；
- 全阶段失败与缺失状态；
- 最终推荐报告及生成时间。

---

# 第六部分 完整示例与附录

## 32. 完整示例

以下示例展示未来完整产品中的目标使用顺序。标为当前可用的命令可以在准备好输入后运行；其他命令是交互设计示例。

### 32.1 核心筛选

```bash
cd my-screening-project

ss-screen dataset mp --backend offline \
  --offline-db /data/mp-offline.sqlite \
  --output 01_dataset/mp.df \
  --provenance 01_dataset/mp.df.provenance.json

ss-screen composition-screen \
  --df 01_dataset/mp.df --nelems 2 \
  --output 02_composition/composition_candidates.csv \
  --summary 02_composition/composition_summary.json

ss-screen condense \
  --df 01_dataset/mp.df \
  --output-dir 03_condensed/mp/ \
  --manifest 03_condensed/mp_manifest.jsonl \
  --index 03_condensed/mp_index.csv

ss-screen structure-match \
  --candidates 02_composition/composition_candidates.csv \
  --condensed-dir 03_condensed/mp/ \
  --output 04_groups/group_df.json \
  --summary 04_groups/structure_match_summary.json

ss-screen gap-export \
  --groups 04_groups/group_df.json \
  --dataset 01_dataset/mp.df \
  --method vasp-hse06-pbe54-nosoc-v1 \
  --structure-dir 05_bands/structures/ \
  --structure-format json --structure-format cif --structure-format poscar \
  --results-template 05_bands/gap_results_template.csv \
  --method-metadata-template 05_bands/method_metadata.json \
  --output 05_bands/gap_tasks.csv
```

### 32.2 带隙回收和端元配对

```bash
# 用户在外部完成高精度计算，返回 user_gap_results.csv
ss-screen gap-validate \
  --tasks 05_bands/gap_tasks.csv \
  --gaps 05_bands/user_gap_results.csv \
  --method-metadata 05_bands/method_metadata.json \
  --output 05_bands/gap_results.normalized.csv \
  --rejected 05_bands/gap_results.rejected.csv \
  --report 05_bands/gap_validation.json

ss-screen pair \
  --groups 04_groups/group_df.json \
  --gap-results 05_bands/gap_results.normalized.csv \
  --method vasp-hse06-pbe54-nosoc-v1 \
  --summary 06_pairs/gap_feedback_summary.json \
  --output 06_pairs/final_pairs.csv

ss-screen stability sqs-generate \
  --pairs 06_pairs/final_pairs.csv \
  --dataset 01_dataset/mp.df \
  --backend icet \
  --target-fraction 0.5 \
  --supercell 2,2,2 \
  --output-dir 07_sqs/structures/ \
  --manifest 07_sqs/sqs_manifest.jsonl
```

### 32.3 MLP 稳定性预筛和后续推荐

```bash
ss-screen stability relax \
  --manifest 07_sqs/sqs_manifest.jsonl \
  --include-endmembers --backend mace \
  --model-path models/mace-mpa-0-medium.model \
  --device cuda:0 \
  --output-dir 08_relaxation/ \
  --results 08_relaxation/relaxation_results.jsonl
```

```bash
ss-screen stability mixing-enthalpy \
  --pairs 06_pairs/final_pairs.csv \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --output 09_thermodynamics/mixing_enthalpy.csv \
  --summary 09_thermodynamics/mixing_summary.json
```

```bash
ss-screen stability phonon-run \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --device cuda:0 --dtype float64 \
  --output-dir 10_phonons/
```

```bash
ss-screen stability phase-diagram \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --device cuda:0 --dtype float32 \
  --output-dir 11_phase_diagram/
```

> **[完整版本预期接口——当前代码尚未提供]** 以下缺陷命令仍是目标接口。

```bash
ss-screen defects generate \
  --recommendable-structures 11_phase_diagram/phase_stability.csv \
  --output-dir 12_defects/structures/ \
  --manifest 12_defects/defect_jobs.jsonl
```

> **[当前可用]** 没有缺陷结果时，可直接用 Stage 5 和 Stage 8--10 产物生成 L2--L5 推荐。

```bash
ss-screen recommend \
  --pairs 06_pairs/final_pairs.csv \
  --gap-results 05_bands/gap_results.normalized.csv \
  --mixing-enthalpy 09_thermodynamics/mixing_enthalpy.csv \
  --phonons 10_phonons/phonon_summary.csv \
  --phase-stability 11_phase_diagram/phase_stability.csv \
  --output 13_report/recommendations.csv \
  --report 13_report/recommendation_report.md \
  --summary 13_report/recommendation_summary.json
```

## 33. 常见问题排查

| 现象 | 可能原因 | 处理方法 |
|---|---|---|
| `ss-screen` 找不到 | 环境未激活或未 editable 安装 | 激活 `.venv`，执行 `python -m pip install -e .`。 |
| MP在线查询失败 | 密钥、网络、配额或超时问题 | 重新输入密钥并检查 `--api-timeout`；失败体系会保留在查询报告中。 |
| MP离线查询失败 | `mp_offline` 未安装、数据库路径错误或快照损坏 | 在项目环境安装本地包，显式传入 `--offline-db`，并检查报告中的数据库 SHA-256。 |
| WBM加载失败 | extxyz损坏或ASE缺失 | 检查文件和 `[wbm]` 依赖。 |
| valence结果异常少 | 键价分析不适合部分体系 | 对照不使用 `--valence-ids` 的结果并人工抽查。 |
| condensed大量失败 | robocrys依赖或结构异常 | 查看manifest错误；用少量结构调试。 |
| structure-match结果为零 | 候选阈值过严或描述缺失 | 检查summary、validation、`nelems` 和 X 元素数。 |
| gap校验失败 | 列名、状态、重复键或数值格式错误 | 按标准模式修正，不用0代替失败。 |
| pair数量异常少 | 高精度结果覆盖率低 | 查看coverage summary，再比较阈值。 |
| SQS组分不精确 | 超胞无法表达目标分数 | 增大超胞并记录实际组分。 |
| MLP能量不可比 | 模型或驰豫设置不同 | 用同一后端重算端元、合金和竞争相。 |
| 声子出现小虚频 | 数值噪声、超胞或收敛问题 | 做超胞、位移和力精度收敛测试。 |
| 推荐等级不可信 | 关键数据缺失或方法冲突 | 查看缺失字段和理由，不只看总分。 |

## 34. 参数管理建议

| 参数类别 | 设置原则 |
|---|---|
| 带隙阈值 | 根据目标器件、泛函误差和历史结果设定。 |
| `e_above_hull` | 初筛和最终稳定性判断使用不同严格度并记录理由。 |
| 原子数上限 | 作为计算成本参数，不是科学核心。 |
| SQS组分 | 至少覆盖目标区间中的多个点。 |
| SQS超胞 | 在组分可表达性、相关函数和成本之间平衡。 |
| MLP收敛 | 明确 `fmax`、最大步数和体积/晶格是否优化。 |
| 声子 | 对超胞、位移和力精度做收敛测试。 |
| 缺陷 | 记录超胞、电荷态、化学势和校正。 |
| 推荐阈值 | 版本化保存在 `project.yaml`，不隐藏在代码中。 |

## 35. 术语表

| 术语 | 说明 |
|---|---|
| 端元 | 固溶体组分轴两端的纯化合物。 |
| 固溶体 | 在保持基本晶体结构的同时，组分可在一定范围变化的相。 |
| 组成模板 | 把可变元素抽象为 `X` 后用于归类的组成表达。 |
| 局部环境 | 某原子周围的配位数、几何和连接关系。 |
| robocrys | 将晶体结构转换为可读结构描述和环境信息的工具。 |
| SQS | Special Quasirandom Structure，用有限超胞近似随机合金相关函数。 |
| MLP | Machine-Learned Potential，机器学习原子势。 |
| 混合焓 | 合金相对端元线性组合的能量差。 |
| 凸包能量 | 相对于稳定相组合的能量距离。 |
| 虚频 | 声子计算中的负频率表示，可能是动力学不稳定或数值问题。 |
| 缺陷形成能 | 在给定化学势、费米能级和电荷态下形成缺陷的能量代价。 |
| manifest | 逐任务记录输入、状态、输出、哈希和错误的机器可读清单。 |

## 36. 数据安全和许可证

- SS-Screen 当前以 MIT 许可证发布；实际权利人信息应在正式发布前核对；
- 第三方依赖保留各自许可证，不能把依赖源码作为 SS-Screen 自有代码申报；
- MP/WBM 数据的获取和使用遵守各自服务条款；
- VASP 等商业软件由用户自行获得合法授权；
- API密钥、集群凭据和未公开计算结果不得进入公开仓库；
- `references/` 是历史科研来源归档，不是运行时权威代码，也不应整体打包到用户项目。

## 37. 文档版本记录

| 日期 | 文档版本 | 说明 |
|---|---|---|
| 2026-08-03 | 完整功能版 V1.4 | Stage 11 综合推荐转为当前可用，增加 L2--L6 证据等级、三类判定、可选缺陷和可配置阈值说明。 |
| 2026-08-03 | 完整功能版 V1.3 | Stage 1 增加 MP 离线快照 provenance、deprecated 过滤和最小字段投影。 |
| 2026-08-01 | 完整功能版 V1.2 | Stage 10 增加 `mp_offline` 竞争相结构来源、快照 provenance 和离线完整性边界。 |
| 2026-07-31 | 完整功能版 V1.1 | 明确高精度带隙在外部计算；新增版本化任务、多格式结构、结果模板、方法元数据和严格回收校验。 |
| 2026-07-22 | 完整功能版 V1.0 | 首次建立未来完整产品的中文科研用户手册；当前实现基线为 `ss-screen 0.1.0`。 |

## 38. 技术支持前的自查信息

报告问题时请提供：

- `ss-screen --version`；
- `python --version`；
- 失败命令和退出码；
- 去除密钥、用户名和绝对私有路径后的错误摘要；
- 对应阶段的 summary 或 manifest；
- 输入模式和少量可公开复现夹具；
- 是否使用 MP 在线接口、哪一种外部带隙平台、MLP、声子或缺陷后端；
- 问题是否可以在 `ss-screen --help` 或微型测试数据上复现。

不要上传完整私有数据库、许可证文件、API密钥、SSH配置或未经授权的计算数据。
