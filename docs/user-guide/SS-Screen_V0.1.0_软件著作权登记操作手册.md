## 文档识别信息

**软件全称：** 新材料计算筛选软件  
**软件简称：** SS-Screen  
**软件版本：** V0.1.0  
**文档名称：** 新材料计算筛选软件 V0.1.0 操作手册  
**著作权人：** 申报主体名称（提交前替换）  
**编制日期：** 2026年8月5日

> 本手册是新材料计算筛选软件 V0.1.0 的操作说明。所有命令均来自 ss-screen 0.1.0 的真实命令行接口。手册只描述本版本已经实现的功能，不包含未实现命令，不把外部高精度计算程序表述为本软件内部功能。

# 第一章 软件概述

## 1.1 研发背景

材料带隙是决定其光学吸收、载流子输运和电子跃迁行为的关键物理量，与材料的光电、电子、能源转换和催化等性能密切相关。准确掌握材料的带隙，对于确定材料的适用波段、评估器件性能以及开展新材料设计具有重要指导作用。

传统带隙测量依赖样品制备和光谱测试，通常存在成本较高、周期较长以及难以批量开展等问题，难以满足大规模材料空间的高通量筛选需求。第一性原理计算方法，如基于密度泛函理论（DFT）的电子结构计算，可以从晶体结构和元素组成出发预测材料的能带结构及相关性质，不必以已有实验测量结果为前提，现已广泛用于能源、光电和催化材料的发现与优化。

窄带隙材料在红外探测领域具有重要应用价值。光子只有在能量达到或超过材料带隙时，才能有效激发电子由价带跃迁至导带并产生可探测的电子-空穴对。材料带隙越小，可响应的光子能量越低，对应的探测截止波长越长。带隙与理想截止波长之间可近似表示为：

> 截止波长近似关系：λc（μm）≈ 1.24 / Eg（eV）。

因此，用于光伏型红外探测器的吸收材料通常需要具有较窄且能够精确调控的带隙。例如，3～5 μm 中波红外探测对应的带隙大致处于 0.25～0.41 eV 范围，8～14 μm 长波红外探测则通常要求约 0.09～0.16 eV 的更窄带隙。实际器件的工作波段还会受到温度、材料组分、能带结构、载流子寿命和器件结构等因素影响。

然而，窄带隙并不意味着材料必然适合红外探测。带隙减小会增强热激发载流子效应，可能导致暗电流和噪声升高。候选材料还需要同时满足结构可实现、热力学和动力学稳定、缺陷可控以及带隙类型适宜等条件。因此，只依据数据库中的单一带隙数值进行筛选，难以获得可靠的材料候选。

固溶体或合金体系为带隙调控提供了一条重要途径。通过在结构相容的端元材料之间改变组分，可以在一定范围内连续调节能带结构，从而获得满足特定红外波段要求的目标带隙。但从大规模材料数据库中寻找结构相似、带隙互补且具有潜在稳定性的端元组合，需要同时处理晶体结构匹配、高精度带隙验证、合金结构构建和稳定性分析等多个环节。依靠人工逐项处理，不仅工作量大，而且容易产生参数、数据来源和计算条件不一致的问题。

基于上述需求，本软件面向窄带隙和带隙可调新材料的计算筛选，建立从材料数据库、结构相似性识别、端元配对、高精度带隙结果回收，到特殊准随机结构生成和稳定性预筛的标准化流程。软件通过保存输入来源、计算参数、模型版本和阶段结果，提高筛选过程的效率、可重复性和可审计性，为红外探测及其他窄带隙光电材料的进一步计算验证和实验研究提供候选依据。

## 1.2 软件简介

新材料计算筛选软件是一套面向计算材料研究的命令行软件。软件从 Materials Project、WBM 或用户准备的规范化结构数据中筛选结构相似的材料端元，生成高精度带隙计算任务，回收外部计算结果，枚举可能通过合金化调控带隙的材料对，并进一步生成 SQS 合金结构及稳定性预筛证据。

软件采用分阶段文件流水线。每个阶段都有明确的输入文件、输出文件、参数和失败状态，用户可以在阶段之间检查结果，也可以替换外部计算结果后继续执行。软件不会把缺失数据自动当作成功结果，也不会用不兼容的能量来源拼接热力学结论。

## 1.3 开发目的

本软件用于把分散在科研脚本和 Notebook 中的材料筛选过程整理为可复现、可检查和可恢复的标准操作流程。主要目标如下：

- 统一 MP、WBM 等来源的材料结构和基础性质字段；
- 通过组成模板和局部配位环境识别结构原型相似的材料；
- 将高成本带隙计算固定为可追踪的外部任务和结果契约；
- 依据高精度端元带隙枚举候选固溶体端元对；
- 生成随机置换或 icet 优化的 SQS 合金结构；
- 使用 MACE 势进行结构驰豫并保存能量、力、应力和质量状态；
- 计算初步混合焓、谐波声子和同能量基准凸包；
- 汇总证据并输出可审计的候选研究优先级。

## 1.4 适用对象

软件主要面向材料科学、计算材料学、电子结构计算和高通量筛选研究人员。用户应具备基本的命令行操作能力，并能理解晶体结构、带隙、SQS、混合焓、声子和凸包等概念。

| 用户类型 | 典型操作 |
|---|---|
| 数据准备人员 | 建立 MP/WBM 规范化数据表并检查 provenance |
| 材料筛选人员 | 执行组成筛选、结构匹配、带隙回填和端元配对 |
| 计算人员 | 接收 gap 任务，在外部平台计算并返回标准结果 |
| 稳定性分析人员 | 生成 SQS，运行 MACE、Phonopy 和竞争相凸包 |
| 项目负责人 | 审查失败、缺失证据、推荐等级和后续验证计划 |

## 1.5 主要功能

软件 V0.1.0 包含以下功能组：

| 功能组 | 主要命令 | 主要产物 |
|---|---|---|
| 数据标准化 | `dataset mp`、`dataset wbm` | Pickle DataFrame、provenance JSON |
| 组成初筛 | `valence-filter`、`composition-screen` | ID 列表、候选 CSV、汇总 JSON |
| 结构描述 | `condense`、`condense-index`、`condense-validate` | robocrys JSON、manifest、索引和校验表 |
| 结构匹配 | `structure-match`、`group` | 结构组 JSON、阶段汇总 |
| 带隙交接 | `gap-export`、`gap-validate` | 任务表、结构、模板、规范结果和审计报告 |
| 端元配对 | `pair`、`gap-compare` | 端元对 CSV、覆盖率和方法比较 |
| 合金结构 | `stability sqs-generate` | SQS 结构和 JSONL manifest |
| 结构驰豫 | `stability relax` | 驰豫结构和 E/F/stress 结果 |
| 稳定性证据 | `mixing-enthalpy`、`phonon-*`、`phase-diagram` | 混合焓、声子和凸包结果 |
| 综合推荐 | `recommend` | 推荐 CSV、Markdown 报告和 JSON 汇总 |

## 1.6 软件工作流程

完整数据流如下：

```text
MP / WBM 数据
  -> 标准化数据表
  -> 价态与组成模板筛选
  -> robocrys 结构描述归档
  -> 局部环境匹配与结构分组
  -> 外部高精度带隙任务与结果回收
  -> 端元配对
  -> SQS 合金结构
  -> MACE 驰豫
  -> 混合焓 / 声子 / 竞争相凸包
  -> 综合推荐报告
```

高精度带隙计算本身由用户在 VASP、ABACUS、AiiDA 或其他平台完成。SS-Screen 负责导出任务和结构、验证返回结果并把合格结果接回筛选流程。Materials Project 在线接口仅用于查询材料结构或竞争相；密钥不写入输出文件。

## 1.7 科学边界

软件输出是研究决策支持材料，不是材料已经稳定、可合成或达到器件指标的证明。需要特别注意：

- 结构环境相似是进一步研究的线索，不是形成连续固溶体的充分条件；
- 端元带隙覆盖目标区间不等于中间组分一定具有目标带隙；
- MACE 势能和声子用于快速预筛，重要结论需要一致设置的 DFT 复核；
- 单一 SQS 组分点不能描述完整混合自由能；
- 离线 MP 快照的完整性仅相对于该快照，不代表最新在线数据库；
- 未计算、失败和不兼容证据必须保留为缺失或风险。

# 第二章 运行环境与安装

## 2.1 硬件环境

| 项目 | 建议配置 | 说明 |
|---|---|---|
| 处理器 | x86_64 多核 CPU | 数据筛选和结构处理可在 CPU 上执行 |
| 内存 | 16 GB 或以上 | 全量 MP/WBM 表需要按数据规模增加内存 |
| 存储 | 20 GB 或以上可用空间 | 大型数据集、结构归档和计算结果保存在仓库外 |
| GPU | 支持 CUDA 的 NVIDIA GPU | 仅 MACE 大规模驰豫和声子力计算需要 |
| 网络 | 可选 | 在线 MP 查询需要；离线快照模式不需要 |

核心命令可以在普通工作站运行。真实 MACE、声子和大量竞争相计算可能耗时较长，应根据任务规模使用 GPU 工作站或计算集群。

## 2.2 软件环境

| 软件 | 版本或要求 | 用途 |
|---|---|---|
| Linux 或 WSL2 | 64 位 | 主要运行平台 |
| Python | 3.10 或更高 | 本版本验证环境为 Python 3.11 |
| ss-screen | 0.1.0 | 本手册对应的软件包 |
| pymatgen/pandas/numpy | 由项目依赖解析 | 晶体结构和数据表处理 |
| robocrys | 可选 | 生成结构环境描述 |
| ASE/icet | 可选 | 读取 WBM 和生成优化 SQS |
| MACE/Torch | 可选 | 机器学习势驰豫和力计算 |
| Phonopy/SeeK-path | 可选 | 谐波声子谱 |
| mp-api 或 mp_offline | 可选 | 在线或离线 Materials Project 数据 |

## 2.3 激活项目环境

进入软件仓库后激活项目虚拟环境。示例路径仅用于说明，实际路径由用户部署位置决定。

```bash
cd /path/to/ss-screen
source .venv/bin/activate
```

激活后检查 Python 和软件版本：

```bash
python --version
python -c "import ssscreen; print(ssscreen.__version__)"
ss-screen --version
```

本手册对应的预期版本输出为：

```text
Python 3.11.x
0.1.0
ss-screen, version 0.1.0
```

每次打开新终端都需要重新激活虚拟环境。禁止把项目依赖安装到系统 Python。

## 2.4 安装核心功能

在项目根目录执行 editable 安装：

```bash
python -m pip install -e .
```

核心功能包含数据表处理、结构匹配、带隙任务契约、端元配对和推荐逻辑。安装完成后执行：

```bash
python -m pip check
ss-screen --help
```

如果 `pip check` 未报告依赖冲突，并且帮助中出现 `composition-screen`、`gap-export`、`pair`、`stability` 和 `recommend`，说明核心入口安装成功。

## 2.5 安装可选功能

根据实际使用阶段安装可选依赖：

```bash
# Materials Project 在线接口
python -m pip install -e ".[mp]"

# WBM extxyz 读取
python -m pip install -e ".[wbm]"

# robocrys 结构描述
python -m pip install -e ".[condense]"

# icet SQS
python -m pip install -e ".[sqs]"
```

MACE 和声子运行依赖需要与本机 CUDA 驱动匹配。先安装正确的 Torch，再安装对应 extra：

```bash
python -m pip install torch==2.5.1+cu121 \
  --index-url https://download.pytorch.org/whl/cu121
python -m pip install -e ".[mlp,phonon]"
```

CPU 环境可以使用 CPU 版 Torch。正式计算前应在小结构上执行一次单点或短步数冒烟测试。

## 2.6 Materials Project 配置

Stage 1 在线数据查询可通过标准 `MP_API_KEY` 环境变量或 mp-api 配置读取凭据：

```bash
export MP_API_KEY="在当前终端设置，不写入仓库"
ss-screen dataset mp --backend api --output 01_dataset/mp.df
```

Stage 10 在线竞争相命令会在终端隐藏提示密钥。密钥只用于当前进程，不进入命令行参数、manifest 或报告。无网络环境使用显式离线数据库：

```bash
python -m pip install /path/to/mp-offline
ss-screen dataset mp \
  --backend offline \
  --offline-db /data/mp-offline/default.db \
  --output 01_dataset/mp.df
```

## 2.7 安装故障检查

| 现象 | 原因 | 处理 |
|---|---|---|
| `ss-screen: command not found` | 环境未激活或包未安装 | 激活 `.venv`，重新执行 editable 安装 |
| import 报错 | 依赖缺失或版本冲突 | 执行 `python -m pip check` 并按 extra 重装 |
| CUDA 不可用 | Torch 与驱动不匹配 | 安装适配集群驱动的 Torch 版本 |
| robocrys 导入失败 | condense extra 不完整 | 重新安装 `.[condense]` |
| Phonopy 命令失败 | phonon extra 缺失 | 安装 `.[mlp,phonon]` |
| MP 查询失败 | 密钥、网络或配额问题 | 检查标准配置，或改用离线快照 |

# 第三章 项目目录与通用操作

## 3.1 推荐项目目录

建议为每次筛选建立独立工作目录：

```text
screening-run/
├── 01_dataset/
├── 02_composition/
├── 03_condensed/
├── 04_groups/
├── 05_gap/
├── 06_pairs/
├── 07_sqs/
├── 08_relaxation/
├── 09_thermodynamics/
├── 10_phonons/
├── 11_phase_diagram/
├── 12_recommendation/
├── logs/
└── models/
```

目录编号对应阶段顺序。外部大数据和模型文件可以放在共享只读目录，通过命令参数引用，不应复制到软件源码仓库。

## 3.2 查看帮助

顶层帮助显示全部命令：

```bash
ss-screen --help
ss-screen dataset --help
ss-screen stability --help
```

查看具体命令参数：

```bash
ss-screen composition-screen --help
ss-screen gap-export --help
ss-screen stability phonon-run --help
ss-screen recommend --help
```

帮助中的 `[required]` 表示必填参数，`[default: ...]` 表示默认值。正式运行前应把实际命令和 `--help` 输出随项目日志保存。

## 3.3 路径规则

- 所有输入和输出路径都通过命令参数指定；
- 示例优先使用项目内相对路径；
- 不依赖当前用户的固定用户名或主目录；
- 大型数据库、模型 checkpoint 和计算结果不提交到 Git；
- 输出目录应按运行批次隔离，避免不同设置相互覆盖；
- 使用 `--overwrite` 前确认输入和关键参数确实发生变化。

## 3.4 状态、失败和恢复

各阶段通常使用 CSV、JSON 或 JSONL 记录状态。失败记录不会静默删除。用户应检查 `status`、`warnings`、`error`、`converged` 和 `usable_for_screening` 等字段。

| 状态类别 | 含义 | 后续动作 |
|---|---|---|
| success/written | 阶段产物成功生成 | 继续下一阶段并保留输入哈希 |
| skipped | 满足明确跳过条件 | 检查跳过原因和成本门槛 |
| not_converged | 运行完成但未收敛 | 调整设置后使用重试选项 |
| failed | 输入、后端或计算失败 | 修复错误后重跑失败项 |
| uncertain | 证据不完整或不兼容 | 补齐证据，不当作通过 |

## 3.5 数据安全

项目目录不得保存明文 API 密钥、SSH 私钥、数据库密码或商业软件许可证文件。外部结构和结果表进入软件前应确认使用授权。日志中应隐藏用户名、远程主机和敏感绝对路径。

# 第四章 数据集构建与组成筛选

## 4.1 Materials Project 离线数据

离线模式从用户指定的 `mp_offline` SQLite 快照建立规范化 DataFrame。命令会限制能量高于凸包阈值，排除 deprecated 记录，并写出 provenance sidecar。

```bash
ss-screen dataset mp \
  --backend offline \
  --offline-db /data/mp-offline/default.db \
  --max-e-hull 0.01 \
  --output 01_dataset/mp.df \
  --provenance 01_dataset/mp.df.provenance.json
```

| 参数 | 含义 |
|---|---|
| `--backend offline` | 明确使用离线数据库 |
| `--offline-db` | SQLite 文件路径 |
| `--max-e-hull` | 查询阶段最大凸包距离，单位 eV/atom |
| `--output` | 规范化 Pickle DataFrame |
| `--provenance` | 查询条件、数据库哈希和版本信息 |

运行后检查输出文件存在、DataFrame 索引唯一、`structure` 列非空，以及 provenance 中的数据库路径、大小、SHA-256 和快照范围警告。

## 4.2 Materials Project 在线数据

在线模式使用官方 mp-api：

```bash
ss-screen dataset mp \
  --backend api \
  --max-e-hull 0.01 \
  --output 01_dataset/mp-online.df \
  --provenance 01_dataset/mp-online.df.provenance.json
```

在线查询受网络、配额和数据库更新影响。报告中应保存查询时间、数据库版本和查询边界。在线与离线结果不要写入同一输出文件。

## 4.3 WBM 数据

WBM 入口消费已经准备好的 extxyz 文件和可选 summary：

```bash
ss-screen dataset wbm \
  --xyz /data/wbm/wbm-dataset.xyz \
  --summary /data/wbm/summary.tsv \
  --output 01_dataset/wbm.df
```

输入必须包含可解析结构。若筛选还需要数据库带隙、凸包能和步骤字段，应在数据构建阶段验证这些字段，不得把缺失值默认为零。

## 4.4 价态过滤

价态过滤使用键价分析检查结构是否可分配氧化态。该步骤可选：

```bash
ss-screen valence-filter \
  --df-mp 01_dataset/mp.df \
  --df-wbm 01_dataset/wbm.df \
  --output 02_composition/valid_ids.json
```

输出是材料 ID 的 JSON 列表。某些金属、混合价或特殊配位体系可能不适合键价模型，因此应比较使用和不使用该过滤的候选数量。

## 4.5 组成模板筛选

组成筛选可以重复提供 `--df` 合并多个规范化数据源：

```bash
ss-screen composition-screen \
  --df 01_dataset/mp.df \
  --df 01_dataset/wbm.df \
  --valence-ids 02_composition/valid_ids.json \
  --nelems 2 \
  --max-bandgap 1.0 \
  --max-e-hull 0.01 \
  --min-group-size 2 \
  --min-x-elements 2 \
  --output 02_composition/composition_candidates.csv \
  --summary 02_composition/composition_summary.json
```

`--nelems` 指定约化组成中的元素数。`--max-bandgap` 和 `--max-e-hull` 是初筛门槛，不是最终科学结论。`--min-x-elements` 要求同一模板至少出现多个可替换元素。

## 4.6 输出检查

| 文件 | 检查内容 |
|---|---|
| `mp.df` / `wbm.df` | ID 唯一、结构存在、字段类型正确 |
| provenance JSON | 来源、查询条件、版本、SHA 和警告完整 |
| `valid_ids.json` | JSON 列表可读取，ID 来自输入数据 |
| `composition_candidates.csv` | 模板、材料 ID、组成和来源列完整 |
| `composition_summary.json` | 输入数、过滤数、候选数和参数一致 |

候选数为零时，依次检查 `nelems`、凸包阈值、带隙阈值、排除元素、价态 ID 和最小组大小。不要一次同时放宽全部门槛，否则无法判断哪个条件造成变化。

# 第五章 结构描述归档

## 5.1 功能说明

`condense` 使用 robocrys 将 pymatgen 晶体结构转换为机器可比较的局部环境描述。软件按材料 ID 为每个结构写出独立 JSON，便于并行处理、失败重试和增量更新。

结构描述阶段读取结构，不改变原始数据表。输出 JSON 用于后续环境匹配，不应当覆盖原始 CIF、POSCAR 或 DataFrame。

## 5.2 从 DataFrame 生成描述

```bash
ss-screen condense \
  --df 01_dataset/mp.df \
  --structure-column structure \
  --output-dir 03_condensed/mp/ \
  --manifest 03_condensed/mp_manifest.jsonl \
  --index 03_condensed/mp_index.csv
```

默认使用 DataFrame 索引作为材料 ID。如果 ID 位于普通列中，可以增加 `--material-id-column`。调试时可用 `--limit` 限制处理行数。

```bash
ss-screen condense \
  --df 01_dataset/mp.df \
  --limit 20 \
  --output-dir 03_condensed/smoke/ \
  --manifest 03_condensed/smoke_manifest.jsonl \
  --index 03_condensed/smoke_index.csv
```

先用小批量确认 robocrys 依赖和结构字段正常，再运行全量任务。

## 5.3 从结构文件生成描述

`--input` 可以重复提供结构文件或目录：

```bash
ss-screen condense \
  --input structures/example-a.cif \
  --input structures/example-b.cif \
  --output-dir 03_condensed/user/ \
  --manifest 03_condensed/user_manifest.jsonl \
  --index 03_condensed/user_index.csv
```

材料 ID 由输入文件名推导。输入文件名应稳定、唯一，不要包含 API 密钥、用户名或临时任务号。

## 5.4 Manifest和索引

| 产物 | 作用 |
|---|---|
| `03_condensed/mp/{material_id}.json` | 单个材料的 robocrys 描述 |
| `mp_manifest.jsonl` | 每个任务的输入、状态、输出和错误 |
| `mp_index.csv` | 可检索的归档索引 |
| 原始 DataFrame | 继续提供结构和数据库字段 |

manifest 中的失败记录必须保留。批量任务中单个结构失败时，默认继续处理其他结构；使用 `--stop-on-error` 才会在第一个错误处停止。

## 5.5 建立现有归档索引

已有 JSON 目录可以重新建立索引：

```bash
ss-screen condense-index \
  --condensed-dir 03_condensed/mp/ \
  --output 03_condensed/mp_index.rebuilt.csv
```

重建索引不会重新执行结构凝练，也不会修改 JSON 内容。

## 5.6 校验归档

```bash
ss-screen condense-validate \
  --condensed-dir 03_condensed/mp/ \
  --output 03_condensed/mp_validation.csv
```

校验表记录必需 robocrys 键是否存在。正式进入结构匹配前，应统计成功、缺失和损坏文件数量，并抽查若干 JSON 的 `mineral`、`components`、`sites` 等结构描述字段。

## 5.7 断点续算

相同输出文件已经存在时，`condense` 会按当前契约跳过可复用产物。只有确认需要重建时才使用 `--overwrite`：

```bash
ss-screen condense \
  --df 01_dataset/mp.df \
  --output-dir 03_condensed/mp/ \
  --manifest 03_condensed/mp_manifest.rerun.jsonl \
  --index 03_condensed/mp_index.rerun.csv \
  --overwrite
```

覆盖运行前应保存旧 manifest，避免丢失失败历史和软件版本信息。

# 第六章 结构匹配与材料分组

## 6.1 匹配原理

软件先按照组成模板选择可能被替换的元素位点，将可变元素重标记为占位符 X，再比较 robocrys 局部环境。匹配关注配位数、几何类型和连接关系等结构表达，使化学元素不同但结构原型相近的材料归入同一组。

该算法不会仅凭化学式或空间群判断相同，也不会把相似结构直接声明为可形成固溶体。

## 6.2 显式结构匹配

推荐使用分阶段命令：

```bash
ss-screen structure-match \
  --candidates 02_composition/composition_candidates.csv \
  --condensed-dir 03_condensed/mp/ \
  --condensed-dir 03_condensed/wbm/ \
  --min-x-elements 2 \
  --output 04_groups/group_df.json \
  --summary 04_groups/structure_match_summary.json
```

`--condensed-dir` 可重复提供多个归档。输出结构组只引用材料 ID、组成、来源和环境信息，不复制完整大型数据集。

## 6.3 兼容分组入口

`group` 是兼容历史流程的一步式入口：

```bash
ss-screen group \
  --df-mp 01_dataset/mp.df \
  --df-wbm 01_dataset/wbm.df \
  --valence-ids 02_composition/valid_ids.json \
  --nelems 2 \
  --condensed-dirs 03_condensed/mp/ \
  --condensed-dirs 03_condensed/wbm/ \
  --max-bandgap 1.0 \
  --max-e-hull 0.01 \
  --output 04_groups/group_legacy.json
```

新项目优先采用 `composition-screen` 加 `structure-match`，因为两阶段有独立的候选表和 attrition 汇总，便于定位材料在哪一层被过滤。

## 6.4 结构组字段

| 字段 | 含义 |
|---|---|
| group index | 结构组稳定序号 |
| compositions | 组内材料组成 |
| mp_ids | 材料 ID 列表，名称沿用历史契约 |
| band_gaps | 数据库初筛带隙 |
| X 元素信息 | 组成模板中发生替换的元素 |
| 环境描述 | 占位符处理后的局部环境特征 |

`mp_ids` 字段可以同时包含不同来源的稳定材料 ID，不能仅凭字段名推断全部来自 Materials Project。

## 6.5 匹配结果检查

检查 `structure_match_summary.json` 中的输入候选数、缺失描述数、原始组数、最终组数和组内成员数。对每个最终组至少抽查：

- 组内材料是否具有相同组成模板；
- 可变元素是否位于预期晶格位点；
- 组内是否至少包含两个不同 X 元素；
- robocrys 描述是否来自当前归档；
- 数据库带隙与材料 ID 是否按相同顺序对齐。

## 6.6 零结果处理

结构组为零时按以下顺序检查：

1. 候选 CSV 是否有记录；
2. condensed 目录是否包含对应材料 ID 的 JSON；
3. `condense-validate` 是否报告结构描述缺失；
4. `--min-x-elements` 是否过高；
5. 数据来源的材料 ID 是否在导入时发生改变；
6. 二元/三元 `--nelems` 是否与候选一致。

# 第七章 高精度带隙任务交接

## 7.1 软件边界

SS-Screen 不在包内启动 VASP、ABACUS、AiiDA daemon 或其他高精度带隙后端。软件负责确定性任务 ID、结构哈希、多格式结构、结果模板、方法元数据模板和返回结果校验。

外部计算人员可以使用任意合法平台，但必须把任务身份、材料身份、方法和结果按模板返回。

## 7.2 导出任务

```bash
ss-screen gap-export \
  --groups 04_groups/group_df.json \
  --dataset 01_dataset/mp.df \
  --method vasp-hse06-pbe54-nosoc-v1 \
  --structure-dir 05_gap/structures/ \
  --structure-format json \
  --structure-format cif \
  --structure-format poscar \
  --results-template 05_gap/gap_results_template.csv \
  --method-metadata-template 05_gap/method_metadata.json \
  --max-natoms 30 \
  --output 05_gap/gap_tasks.csv
```

`--structure-format` 可重复使用。JSON 用于无损回读 pymatgen 结构，CIF 和 POSCAR 便于外部计算软件消费。`--max-natoms` 是计算成本门槛，被跳过的材料仍应在任务审计中可见。

## 7.3 任务表

| 字段类别 | 示例 | 作用 |
|---|---|---|
| 任务身份 | task_id、schema_version | 防止返回结果错配 |
| 材料身份 | material_id、formula | 与结构组和数据集关联 |
| 结构身份 | structure_sha256、natoms | 检查结构未被静默替换 |
| 方法身份 | method | 区分 HSE06、mBJ 或其他方法 |
| 文件路径 | JSON/CIF/POSCAR | 外部计算输入 |
| 状态 | exported/skipped | 保留成本门槛和失败原因 |

任务 ID 和结构 SHA-256 是结果接收的重要依据。外部平台重建 primitive cell、改变原子排序或替换结构时，必须明确记录，不能继续沿用原哈希冒充同一输入。

## 7.4 填写方法元数据

`method_metadata.json` 应填写计算程序、版本、理论方法、赝势、基组或截断能、k 点策略、自旋、SOC、结构处理和收敛条件。示意内容如下：

```json
{
  "method": "vasp-hse06-pbe54-nosoc-v1",
  "backend": "VASP",
  "backend_version": "user-recorded",
  "settings_sha256": "由外部平台按实际设置生成",
  "notes": "结构与 gap_tasks.csv 中的哈希保持对应"
}
```

示例值不能直接用于正式结果。用户必须按真实设置填写。

## 7.5 返回结果

计算人员在 `gap_results_template.csv` 中填写：

- `band_gap`：有限、非负的带隙数值，单位 eV；
- `is_direct`：明确的 true/false，未知时留空；
- `transition`：可选带边跃迁说明；
- `status`：success、failed、not_converged 或 skipped；
- 后端名称、版本和完成时间；
- 外部过程 ID 等可选 provenance。

失败任务不要把 `band_gap` 填成 0。零带隙是物理结果，失败是状态，两者含义不同。

## 7.6 校验返回结果

```bash
ss-screen gap-validate \
  --tasks 05_gap/gap_tasks.csv \
  --gaps 05_gap/user_gap_results.csv \
  --method-metadata 05_gap/method_metadata.json \
  --output 05_gap/gap_results.normalized.csv \
  --rejected 05_gap/gap_results.rejected.csv \
  --report 05_gap/gap_validation.json
```

校验器检查任务、材料、方法、结构、设置、状态、数值和重复记录。合格失败行保留在规范表中用于覆盖率统计；身份冲突或非法数值进入 rejected 表。

## 7.7 校验报告检查

| 检查项 | 合格条件 |
|---|---|
| exported task count | 与任务表实际导出数一致 |
| returned task count | 与外部返回行数一致 |
| accepted success | 数值和身份均通过 |
| accepted failure | 失败状态完整且未伪造数值 |
| rejected count | 每行都有明确拒绝原因 |
| missing count | 未返回任务列表可追踪 |
| method identity | 与方法元数据一致 |

存在 rejected 行时应先修复外部结果，不要跳过校验直接进入配对。

# 第八章 端元配对与方法比较

## 8.1 生成端元对

`pair` 将规范化高精度带隙映射回结构组，并按阈值枚举端元组合：

```bash
ss-screen pair \
  --groups 04_groups/group_df.json \
  --gap-results 05_gap/gap_results.normalized.csv \
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

阈值是可配置筛选参数。修改阈值时应新建输出目录或记录配置版本，避免不同规则的结果混合。

## 8.2 参数解释

| 参数 | 默认值 | 含义 |
|---|---:|---|
| `--low-gap` | 0.15 eV | 组级近零带隙门槛 |
| `--direct-min` | 0.15 eV | 组级小带隙范围下界 |
| `--direct-max` | 1.5 eV | 组级小带隙范围上界 |
| `--pair-any-below` | 0.3 eV | 材料对至少一个端元低于此值 |
| `--pair-any-above` | 0.2 eV | 材料对至少一个端元高于此值 |
| `--pair-both-below` | 0.8 eV | 两个端元均需低于此值 |

`direct` 信息保留在输出中，但当前实现不把 directness 作为材料对硬过滤条件。用户应根据研究目标在下游进一步分析。

## 8.3 输出字段

`final_pairs.csv` 主要包含 pair 序号、结构组序号、两个端元的材料 ID、组成、带隙、directness 和方法。`gap_feedback_summary.json` 保存任务覆盖、成功覆盖、方法和丢失成员统计。

## 8.4 旧格式兼容

历史七列 gap CSV 可以通过 `--gaps` 读取：

```bash
ss-screen pair \
  --groups 04_groups/group_df.json \
  --gaps 05_gap/legacy_gaps.csv \
  --output 06_pairs/legacy_pairs.csv
```

新研究优先使用 `gap-export` 和 `gap-validate` 的严格任务契约。旧格式缺少任务 ID、结构哈希和设置身份，审计能力较弱。

## 8.5 多方法比较

规范结果包含多个方法时执行：

```bash
ss-screen gap-compare \
  --groups 04_groups/group_df.json \
  --gap-results 05_gap/gap_results.normalized.csv \
  --output-dir 06_pairs/method_comparison/ \
  --summary 06_pairs/gap_method_comparison.json
```

比较报告应关注每个方法的材料覆盖、生成的材料对集合、共有材料对和方法特有材料对。不同理论方法的带隙不能在同一 pair 行中随意拼接。

## 8.6 配对质量检查

- 两个端元 ID 不得相同；
- 两个端元应来自同一结构组；
- gap 方法必须明确且一致；
- 带隙必须来自已接受的 success 记录；
- 输出行应具有稳定 pair index；
- 缺失高精度带隙的组成员应反映在 coverage summary；
- 阈值变化应形成独立结果版本。

# 第九章 SQS合金结构生成

## 9.1 功能说明

SQS 阶段根据端元对和目标组分生成有限超胞合金结构。`random` 后端用于快速演示和测试；`icet` 后端通过簇相关函数优化构型，更适合正式预筛。

## 9.2 随机置换后端

```bash
ss-screen stability sqs-generate \
  --pairs 06_pairs/final_pairs.csv \
  --dataset 01_dataset/mp.df \
  --target-fraction 0.5 \
  --supercell 2,2,2 \
  --backend random \
  --seed 7 \
  --output-dir 07_sqs/random_structures/ \
  --manifest 07_sqs/random_manifest.jsonl
```

随机种子必须保存，以便重复生成相同构型。随机结构适合验证文件链，不应自动视为收敛的无序合金代表。

## 9.3 icet后端

```bash
ss-screen stability sqs-generate \
  --pairs 06_pairs/final_pairs.csv \
  --dataset 01_dataset/mp.df \
  --target-fraction 0.5 \
  --supercell 2,2,2 \
  --backend icet \
  --cutoff 4.0 \
  --sqs-steps 10000 \
  --seed 7 \
  --output-dir 07_sqs/icet_structures/ \
  --manifest 07_sqs/icet_manifest.jsonl
```

`--cutoff` 可以重复提供以定义更高阶簇截断。正式计算应记录 cutoff、Monte Carlo 步数、种子、目标组分和超胞。

## 9.4 组分和超胞

`--target-fraction` 必须在 0 到 1 之间，表示端元 B 在替换位点上的目标比例。有限超胞不一定精确表达目标分数，因此 manifest 同时记录目标比例和实际比例。

| 检查项 | 内容 |
|---|---|
| target_fraction_b | 用户请求的 B 端比例 |
| actual_fraction_b | 结构实际实现的比例 |
| replacement counts | 替换位点总数和元素计数 |
| supercell | 三个方向的整数倍数 |
| backend | random 或 icet |
| seed/settings | 生成器可复现参数 |

## 9.5 Manifest检查

逐行检查 `sqs_manifest.jsonl` 的 pair index、两个端元 ID、元素替换映射、结构路径、结构哈希、目标/实际组分、生成后端和状态。状态不是 `written` 的任务不能直接交给驰豫阶段。

## 9.6 多组分建议

单一 `x=0.5` 只能提供一个中间组分。正式研究通常应在目标区间生成多个组分点，例如 0.25、0.50 和 0.75，并对超胞可表达性和 SQS 相关函数做收敛检查。每个组分使用独立 manifest 或稳定结构 ID。

# 第十章 MACE结构驰豫

## 10.1 功能说明

`stability relax` 使用本地 MACE checkpoint 对 SQS 及可选端元执行结构驰豫。软件通过 ASE 优化器更新原子位置和可选晶胞，并保存总能、每原子能、完整力、应力、收敛状态、结构质量和运行指纹。

模型二进制由用户合法取得并放在外部或 Git 忽略目录中。软件记录模型文件 SHA-256，不把模型文件嵌入结果。

## 10.2 运行命令

```bash
ss-screen stability relax \
  --manifest 07_sqs/icet_manifest.jsonl \
  --include-endmembers \
  --backend mace \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --fmax 0.03 \
  --max-steps 500 \
  --relax-cell \
  --output-dir 08_relaxation/ \
  --results 08_relaxation/relaxation_results.jsonl
```

`--include-endmembers` 会去重并驰豫材料对端元，为混合焓提供同模型参考能。若使用旧 manifest 且没有端元结构路径，可以增加 `--dataset` 作为回退。

## 10.3 主要参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--backend` | mace | 当前可用 MLP 后端 |
| `--device` | cpu | 可改为 cuda:0 等设备 |
| `--dtype` | float32 | 正式精度按模型和任务选择 |
| `--fmax` | 0.03 eV/Å | 最大残余力收敛阈值 |
| `--max-steps` | 500 | 最大优化步数 |
| `--relax-cell` | 启用 | 同时优化晶胞和原子位置 |
| `--positions-only` | 关闭 | 仅优化原子位置 |

端元、SQS 和后续竞争相用于能量比较时，必须使用相同模型 SHA、dtype、优化器、晶胞模式、fmax、最大步数和结构质量策略。

## 10.4 结果记录

| 字段 | 含义 |
|---|---|
| structure_id / role | 结构稳定 ID 及 endmember、sqs 等角色 |
| input/output structure | 输入输出路径和 SHA-256 |
| energy_total_eV | 结构总能 |
| energy_per_atom_eV | 每原子势能 |
| forces | 每个原子的三维力数组 |
| stress | eV/Å³ 和 GPa 应力张量 |
| steps | 实际优化步数 |
| status/converged | success、not_converged 或 failed |
| usable_for_thermodynamics | 是否可进入热力学预筛 |
| backend/settings | 模型、版本、SHA、设备、精度和设置 |

## 10.5 结构质量检查

软件检查体积变化和最小原子距离。用户还应查看：

- 最终最大力是否不高于 `fmax`；
- 晶格是否发生非物理坍塌或过度膨胀；
- 原子是否异常接近；
- 结构组成和替换位点是否保持；
- 总能、力和应力是否为有限数；
- 模型是否覆盖结构中的全部元素。

`success` 但 `usable_for_thermodynamics=false` 的记录不能进入混合焓或凸包。

## 10.6 断点续算

相同输入结构、模型和设置形成运行指纹。已有匹配成功记录时可以自动复用。常用恢复选项如下：

```bash
ss-screen stability relax \
  --manifest 07_sqs/icet_manifest.jsonl \
  --include-endmembers \
  --model-path models/mace-mpa-0-medium.model \
  --device cuda:0 \
  --retry-failed \
  --output-dir 08_relaxation/ \
  --results 08_relaxation/relaxation_results.jsonl
```

`--retry-failed` 只重试匹配的失败记录。关键设置变化时必须显式 `--overwrite`，同时建议使用新输出目录保留旧结果。

## 10.7 正式计算建议

先用 `--limit 1` 在一个结构上检查模型、设备和输出。用于声子计算的输入通常需要比混合焓更严格的残余力，可把 `fmax` 收紧到约 0.001--0.005 eV/Å 并检查收敛。

# 第十一章 混合焓计算

## 11.1 计算定义

对组分 x 的 SQS，每原子初步混合焓定义为：

```text
Delta H_mix(x) = E_SQS(x) - [(1-x) E_A + x E_B]
```

E_A、E_B 和 E_SQS 必须来自相同 MLP 能量基准和兼容驰豫设置。软件优先使用实际 SQS 组分，而不是仅使用目标组分。

## 11.2 运行命令

```bash
ss-screen stability mixing-enthalpy \
  --pairs 06_pairs/final_pairs.csv \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --output 09_thermodynamics/mixing_enthalpy.csv \
  --summary 09_thermodynamics/mixing_summary.json
```

命令会匹配每个 SQS 和两个端元。缺失端元、未收敛、质量不合格、设置不兼容或记录歧义都会写成失败行。

## 11.3 输出字段

| 字段 | 含义 |
|---|---|
| pair_index / sqs_structure_id | 材料对和 SQS 标识 |
| target_fraction_b | 请求的组分 |
| actual_fraction_b | 实际 SQS 组分 |
| fraction_basis | actual、site_counts 或 target_fallback |
| energy_sqs_per_atom_eV | SQS 每原子势能 |
| energy_endmember_a/b_per_atom_eV | 两个端元参考能 |
| reference_energy_per_atom_eV | 端元线性组合参考 |
| mixing_enthalpy_eV_per_atom | eV/atom 结果 |
| mixing_enthalpy_meV_per_atom | meV/atom 结果 |
| energy_reference_sha256 | 共同能量基准摘要 |
| status / warnings / error | 可用性、警告和失败原因 |

## 11.4 兼容性检查

软件比较后端名称、后端版本、模型 SHA-256、dtype 和完整驰豫设置。计算设备可以不同，因为设备不定义势能零点。使用不同 checkpoint、不同晶胞模式或不同收敛设置的能量不能直接相减。

## 11.5 结果解释

- 负混合焓通常是有利混合信号；
- 小的正混合焓可能被构型熵或温度效应改变；
- 大的正混合焓提示相分离风险；
- 单一组分不能描述完整自由能曲线；
- 当前结果是 MLP 0 K 势能信号，不含构型熵、振动自由能或有限温相图；
- 重要候选需要一致设置的 DFT 复核。

# 第十二章 声子谱计算

## 12.1 功能说明

声子模块使用 Phonopy 生成有限位移超胞，使用 MACE 计算固定结构能量、力和应力，再构建力常数、均匀 q 网格、自动高对称路径频带和态密度。动力学分类依据均匀 q 网格，而不是只看频带图。

## 12.2 一步式运行

```bash
ss-screen stability phonon-run \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float64 \
  --displacement 0.01 \
  --mesh 20,20,20 \
  --imaginary-tolerance 0.1 \
  --output-dir 10_phonons/
```

默认只处理 SQS。使用 `--include-endmembers` 可同时处理端元；使用 `--structure-id` 可选择特定结构。

## 12.3 超胞和输入质量

未指定 `--supercell` 时，软件根据晶格长度自动选择对角超胞，目标最小长度默认为 10 Å，并受 `--max-supercell-atoms 300` 限制。显式示例：

```bash
ss-screen stability phonon-run \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --supercell 2,2,2 \
  --max-supercell-atoms 400 \
  --model-path models/mace-mpa-0-medium.model \
  --device cuda:0 \
  --output-dir 10_phonons/supercell-222/
```

Stage 7 输入最大残余力默认不得超过 0.01 eV/Å。`--allow-loose-input` 只能用于明确的诊断，不应掩盖未充分弛豫。

## 12.4 分阶段任务导出

大任务先生成位移 manifest：

```bash
ss-screen stability phonon-export \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --supercell 2,2,2 \
  --displacement 0.01 \
  --max-input-force 0.01 \
  --output-dir 10_phonons/inputs/ \
  --manifest 10_phonons/phonon_jobs.jsonl
```

manifest 包含参考超胞和全部位移结构的稳定任务 ID、结构哈希、位移参数和输入来源。

## 12.5 计算能量和力

```bash
ss-screen stability phonon-forces \
  --manifest 10_phonons/phonon_jobs.jsonl \
  --backend mace \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float64 \
  --output-dir 10_phonons/forces/ \
  --results 10_phonons/phonon_force_results.jsonl
```

每个位移任务独立保存能量、力、应力、模型 SHA、运行时间和状态。`--retry-failed` 可重试失败任务。

## 12.6 收集声子结果

```bash
ss-screen stability phonon-collect \
  --manifest 10_phonons/phonon_jobs.jsonl \
  --force-results 10_phonons/phonon_force_results.jsonl \
  --mesh 20,20,20 \
  --band-points 101 \
  --imaginary-tolerance 0.1 \
  --subtract-reference-forces \
  --symmetrize-fc \
  --output-dir 10_phonons/results/ \
  --summary 10_phonons/phonon_summary.csv \
  --report 10_phonons/phonon_summary.json
```

## 12.7 声子产物

| 文件 | 内容 |
|---|---|
| `force_constants.hdf5` | 谐波力常数 |
| `phonopy_params.yaml` | Phonopy 参数和结构 |
| `band.yaml` / `phonon_band.csv` | 高对称路径频带 |
| `mesh.npz` | 均匀 q 网格数值 |
| `phonon_dos.csv` | 声子态密度 |
| `phonon_band_dos.png/pdf` | 频带与 DOS 图 |
| `phonon_summary.csv/json` | 稳定性状态和审计字段 |

## 12.8 动力学状态解释

`stable` 表示在指定 MACE 模型、超胞、位移、网格和虚频容差下未发现显著虚频。`unstable` 表示检测到超过容差的虚频。`uncertain` 或 `failed` 表示输入、力覆盖、模型兼容或后处理不足。

当前结果不含 Born 有效电荷和介电张量，`nac_applied=false`。极性材料没有 LO--TO 非解析修正，必须在最终结论中保留该限制。

## 12.9 收敛测试

正式研究至少比较两组超胞或位移幅度，并检查：

- 最低网格频率对超胞是否收敛；
- 参考力扣除前后结果是否稳定；
- 力常数对称化前后漂移；
- MACE float32/float64 对软模的影响；
- 显著虚频是否只出现在少量数值噪声 q 点；
- 重要候选是否需要 DFT 有限位移复核。

# 第十三章 竞争相与凸包分析

## 13.1 功能说明

竞争相模块从 Materials Project API 或显式离线快照发现同化学体系及全部子体系中的竞争相结构，再使用与候选一致的 MACE checkpoint 和驰豫设置重算能量。MP DFT 能量只用于发现和初筛条目，不进入最终 MLP 凸包。

## 13.2 在线一步式运行

```bash
ss-screen stability phase-diagram \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --mp-backend api \
  --mp-max-e-hull 0.1 \
  --thermo-type GGA_GGA+U_R2SCAN \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --fmax 0.03 \
  --output-dir 11_phase_diagram/api/
```

命令在终端隐藏提示 API key。密钥不进入输出。在线 thermo type 过滤只适用于 API 后端。

## 13.3 离线一步式运行

```bash
ss-screen stability phase-diagram \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --mp-backend offline \
  --offline-db /data/mp-offline/default.db \
  --mp-max-e-hull 0.1 \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --output-dir 11_phase_diagram/offline/
```

离线结果保存数据库 SHA-256、快照范围和警告。API 与离线快照不得写入同一 manifest，也不得在查询失败时自动互相回退。

## 13.4 导出竞争相

```bash
ss-screen stability competing-export \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --mp-backend offline \
  --offline-db /data/mp-offline/default.db \
  --mp-max-e-hull 0.1 \
  --max-phase-atoms 200 \
  --output-dir 11_phase_diagram/inputs/ \
  --manifest 11_phase_diagram/competing_phases.jsonl \
  --report 11_phase_diagram/competing_export_summary.json
```

manifest 记录 MP entry/material ID、化学体系、结构、结构哈希、来源版本和导出状态。超过原子数门槛的相以 skipped 保留。

## 13.5 驰豫竞争相

```bash
ss-screen stability competing-relax \
  --manifest 11_phase_diagram/competing_phases.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --fmax 0.03 \
  --max-steps 500 \
  --relax-cell \
  --output-dir 11_phase_diagram/relaxation/ \
  --results 11_phase_diagram/competing_relaxation_results.jsonl
```

竞争相失败时禁止回退到 MP DFT 能量，因为这会混用能量基准。

## 13.6 构建凸包

```bash
ss-screen stability convex-hull \
  --relax-results 08_relaxation/relaxation_results.jsonl \
  --competing-manifest 11_phase_diagram/competing_phases.jsonl \
  --competing-results 11_phase_diagram/competing_relaxation_results.jsonl \
  --screening-cutoff 0.1 \
  --numerical-tolerance 1e-6 \
  --output 11_phase_diagram/phase_stability.csv \
  --entries-output 11_phase_diagram/hull_entries.csv \
  --summary 11_phase_diagram/phase_stability_summary.json
```

默认要求竞争相集合完整。`--allow-incomplete` 只能生成明确标为 uncertain 的诊断，不能把缺相的凸包当作正式稳定性结果。

## 13.7 输出解释

| 字段 | 含义 |
|---|---|
| energy_relative_to_competing_hull | 候选相相对已有竞争相凸包的带符号能量 |
| energy_above_hull | 常规定义的非负凸包距离 |
| decomposition | 最优分解相及分数 |
| hull_signal | stable、metastable_within_cutoff 或 unstable |
| competing_set_complete | 相对于指定来源是否无缺失 |
| mp_source_backend/scope | API 或离线快照及范围 |
| model_sha256 | 共同 MLP 能量基准 |
| status/warnings | 可用状态和风险 |

负的 relative 能量表示候选会降低不含候选时的竞争相凸包；常规 `energy_above_hull` 会截断为非负值。低凸包能仍不等于实验可合成。

# 第十四章 综合推荐

## 14.1 功能说明

`recommend` 按材料对和 SQS 结构连接高精度带隙、混合焓、声子和凸包证据，保留缺失、失败、不兼容和来源警告，输出确定性研究优先级。软件不使用不透明综合科学分数。

## 14.2 运行命令

```bash
ss-screen recommend \
  --pairs 06_pairs/final_pairs.csv \
  --gap-results 05_gap/gap_results.normalized.csv \
  --mixing-enthalpy 09_thermodynamics/mixing_enthalpy.csv \
  --phonons 10_phonons/phonon_summary.csv \
  --phase-stability 11_phase_diagram/phase_stability.csv \
  --output 12_recommendation/recommendations.csv \
  --report 12_recommendation/recommendation_report.md \
  --summary 12_recommendation/recommendation_summary.json
```

已有符合契约的缺陷证据时可增加 `--defects`。当前软件只消费可选缺陷表，不负责生成缺陷计算。

## 14.3 推荐阈值

| 参数 | 默认值 | 作用 |
|---|---:|---|
| `--promising-max-mixing` | 25 meV/atom | promising 混合焓上限 |
| `--low-priority-mixing` | 50 meV/atom | 超过时形成低优先级信号 |
| `--promising-max-hull` | 0.025 eV/atom | promising 凸包距离上限 |
| `--low-priority-hull` | 0.1 eV/atom | 超过时形成低优先级信号 |
| `--gap-consistency-tolerance` | 1e-6 eV | pair 表与 gap 表端元值容差 |

这些阈值是筛选起点，不是通用物理常数。项目调整阈值时必须保存实际命令。

## 14.4 推荐分类

| 分类 | 含义 |
|---|---|
| promising | 核心证据完整，未发现配置阈值下的明显淘汰信号 |
| uncertain | 存在缺失、边界、方法冲突或来源风险，需要补算 |
| low-priority | 出现明确的混合、声子、凸包或其他负面信号 |

明确负面信号优先产生 low-priority；没有硬负面但证据缺失时产生 uncertain。未计算项不会自动当作通过。

## 14.5 证据等级

| 等级 | 已包含证据 |
|---|---|
| L2 | 结构匹配端元对 |
| L3 | 增加高精度端元带隙 |
| L4 | 增加 SQS/MLP 混合焓 |
| L5 | 增加声子和竞争相凸包 |
| L6 | 再增加可选缺陷证据 |

证据等级表示完整度，不等于推荐好坏。一个声子不稳定但证据完整的候选可以是 L5/low-priority。

## 14.6 输出文件

`recommendations.csv` 是逐候选机器可读表；`recommendation_report.md` 是人可读审计报告；summary JSON 保存输入、阈值、分类数量和运行摘要。逐行检查：

- recommendation ID、pair index 和 structure ID；
- 分类和证据等级；
- 正向证据、风险和缺失数据；
- 模型兼容状态和来源警告；
- 建议的下一步计算或实验；
- 所有输入文件是否来自同一项目批次。

# 第十五章 完整操作示例

## 15.1 示例边界

本章给出从数据表到推荐报告的标准顺序。示例路径均为相对路径，数据库、模型和外部带隙结果由用户合法准备。真实科研运行应使用经验证的数据和计算参数。

软件仓库中的 CPU 端到端测试夹具使用三条合成 rock-salt 记录验证文件契约，不调用网络、真实 MACE、Phonopy、MP 或 DFT。该夹具只证明软件流程可复现，不构成任何材料结论。

## 15.2 建立工作目录

```bash
mkdir -p screening-run/{01_dataset,02_composition,03_condensed}
mkdir -p screening-run/{04_groups,05_gap,06_pairs,07_sqs}
mkdir -p screening-run/{08_relaxation,09_thermodynamics,10_phonons}
mkdir -p screening-run/{11_phase_diagram,12_recommendation,logs,models}
cd screening-run
```

记录软件环境：

```bash
python --version
ss-screen --version
python -m pip freeze > logs/python-packages.txt
```

`pip freeze` 可能包含本地路径，向外共享日志前应做隐私检查。

## 15.3 构建数据与候选

使用离线 MP 快照：

```bash
ss-screen dataset mp \
  --backend offline \
  --offline-db /data/mp-offline/default.db \
  --max-e-hull 0.01 \
  --output 01_dataset/mp.df \
  --provenance 01_dataset/mp.df.provenance.json

ss-screen composition-screen \
  --df 01_dataset/mp.df \
  --nelems 2 \
  --max-e-hull 0.01 \
  --output 02_composition/candidates.csv \
  --summary 02_composition/summary.json
```

检查 `summary.json` 中候选数大于零，再继续结构描述。

## 15.4 建立结构组

```bash
ss-screen condense \
  --df 01_dataset/mp.df \
  --output-dir 03_condensed/mp/ \
  --manifest 03_condensed/manifest.jsonl \
  --index 03_condensed/index.csv

ss-screen condense-validate \
  --condensed-dir 03_condensed/mp/ \
  --output 03_condensed/validation.csv

ss-screen structure-match \
  --candidates 02_composition/candidates.csv \
  --condensed-dir 03_condensed/mp/ \
  --output 04_groups/groups.json \
  --summary 04_groups/summary.json
```

只有归档校验和结构匹配 summary 均无未解释的批量失败时，才导出高精度任务。

## 15.5 导出和回收带隙

```bash
ss-screen gap-export \
  --groups 04_groups/groups.json \
  --dataset 01_dataset/mp.df \
  --method external-gap-method-v1 \
  --structure-dir 05_gap/structures/ \
  --results-template 05_gap/results_template.csv \
  --method-metadata-template 05_gap/method_metadata.json \
  --output 05_gap/tasks.csv
```

用户在外部平台完成计算，将真实结果保存为 `05_gap/results_returned.csv`，再执行：

```bash
ss-screen gap-validate \
  --tasks 05_gap/tasks.csv \
  --gaps 05_gap/results_returned.csv \
  --method-metadata 05_gap/method_metadata.json \
  --output 05_gap/results_normalized.csv \
  --rejected 05_gap/results_rejected.csv \
  --report 05_gap/validation.json
```

当 rejected 表为空或所有拒绝原因已经处理后生成材料对：

```bash
ss-screen pair \
  --groups 04_groups/groups.json \
  --gap-results 05_gap/results_normalized.csv \
  --method external-gap-method-v1 \
  --summary 06_pairs/summary.json \
  --output 06_pairs/final_pairs.csv
```

## 15.6 生成和驰豫SQS

```bash
ss-screen stability sqs-generate \
  --pairs 06_pairs/final_pairs.csv \
  --dataset 01_dataset/mp.df \
  --backend icet \
  --target-fraction 0.5 \
  --supercell 2,2,2 \
  --cutoff 4.0 \
  --sqs-steps 10000 \
  --seed 7 \
  --output-dir 07_sqs/structures/ \
  --manifest 07_sqs/manifest.jsonl

ss-screen stability relax \
  --manifest 07_sqs/manifest.jsonl \
  --include-endmembers \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --fmax 0.03 \
  --max-steps 500 \
  --output-dir 08_relaxation/ \
  --results 08_relaxation/results.jsonl
```

运行前先用 `--limit 1` 做小样本检查。运行结束后统计 success、not_converged 和 failed，并确认端元与 SQS 模型 SHA 一致。

## 15.7 生成三类稳定性证据

混合焓：

```bash
ss-screen stability mixing-enthalpy \
  --pairs 06_pairs/final_pairs.csv \
  --relax-results 08_relaxation/results.jsonl \
  --output 09_thermodynamics/mixing_enthalpy.csv \
  --summary 09_thermodynamics/summary.json
```

声子：

```bash
ss-screen stability phonon-run \
  --relax-results 08_relaxation/results.jsonl \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float64 \
  --output-dir 10_phonons/
```

竞争相和凸包：

```bash
ss-screen stability phase-diagram \
  --relax-results 08_relaxation/results.jsonl \
  --mp-backend offline \
  --offline-db /data/mp-offline/default.db \
  --model-path models/mace-mpa-0-medium.model \
  --model-name MACE-MPA-0-medium \
  --device cuda:0 \
  --dtype float32 \
  --output-dir 11_phase_diagram/
```

三类证据相互独立地消费合格 Stage 7 结果。声子和凸包不构成混合焓的串行后置步骤。

## 15.8 生成推荐

```bash
ss-screen recommend \
  --pairs 06_pairs/final_pairs.csv \
  --gap-results 05_gap/results_normalized.csv \
  --mixing-enthalpy 09_thermodynamics/mixing_enthalpy.csv \
  --phonons 10_phonons/phonon_summary.csv \
  --phase-stability 11_phase_diagram/phase_stability.csv \
  --output 12_recommendation/recommendations.csv \
  --report 12_recommendation/report.md \
  --summary 12_recommendation/summary.json
```

最终审查不只查看分类，还要读取 risks、missing_data、source_warnings 和 next_steps。

## 15.9 阶段验收表

| 阶段 | 最小验收条件 |
|---|---|
| 数据集 | DataFrame 可读取，provenance 完整，ID 唯一 |
| 组成筛选 | 候选和 attrition 计数可解释 |
| 结构描述 | validation 完成，失败结构有原因 |
| 结构分组 | 每组模板和 X 位点合理 |
| gap 任务 | task ID、结构 SHA 和方法身份完整 |
| gap 回收 | rejected 已处理，coverage 可解释 |
| pair | 无自配对，带隙方法一致 |
| SQS | 实际组分、超胞、种子和结构 SHA 完整 |
| 驰豫 | 收敛、QC 和模型来源合格 |
| 混合焓 | 三个能量来自同一基准 |
| 声子 | 力任务完整，网格和 NAC 状态明确 |
| 凸包 | 竞争相来源和完整性明确 |
| 推荐 | 分类、等级、风险和缺失均可追踪 |

# 第十六章 结果解释与质量控制

## 16.1 结果层级

软件结果从低到高形成不同证据层：

1. 数据库性质和组成门槛；
2. 局部环境结构匹配；
3. 外部高精度端元带隙；
4. SQS 和 MLP 混合焓；
5. 谐波声子和同 MLP 竞争相凸包；
6. 用户可选提供的缺陷证据；
7. 一致设置的高精度 DFT 和实验验证。

上层证据不会消除下层数据来源限制。任何层级出现失败都应保持可见。

## 16.2 带隙结果

端元带隙范围只表明通过合金化覆盖目标区间的可能性。预测目标组分还需要带隙随组分模型、bowing 参数或显式中间组分计算。`direct` 字段用于信息记录，当前配对不会因 indirect 自动淘汰。

## 16.3 混合焓结果

混合焓是相对两个端元线性组合的信号，不包含其他竞争相。正值风险需要结合温度、构型熵和完整组分曲线判断。只有同一能量参考的端元和 SQS 可以比较。

## 16.4 声子结果

显著虚频是动力学风险信号，但小负频率可能来自数值噪声、有限超胞、力精度或声学支处理。需要对超胞、位移、模型精度和 q 网格做收敛检查。

## 16.5 凸包结果

凸包比较的是候选与竞争相组合。结果可靠性取决于竞争相覆盖和统一能量基准。离线快照旧、条目被原子数门槛跳过或竞争相未收敛时，应把结果标为 uncertain。

## 16.6 推荐结果

推荐分类用于决定下一步投入，不是发布材料发现结论。推荐排序依次考虑分类、证据等级、风险/缺失数量、混合焓、凸包距离和稳定性标识。用户应保存阈值并进行项目内校准。

## 16.7 模型和设置一致性

| 比较对象 | 必须一致 |
|---|---|
| SQS 与端元混合焓 | MLP 后端、版本、模型 SHA、dtype、完整驰豫设置 |
| 候选与竞争相凸包 | 上述全部设置及结构 QC 策略 |
| 声子位移任务 | 模型 SHA、dtype、参考/位移力设置 |
| 多 gap 方法 | 每个结果集内部方法与设置身份 |
| 重复项目运行 | 数据快照、代码版本、阈值和随机种子 |

设备可以不同，但应记录设备和运行版本以解释数值差异。

## 16.8 缺失数据原则

- 未返回不等于带隙为零；
- 未收敛不等于成功；
- 网络失败不等于不存在竞争相；
- 缺少虚频结果不等于动力学稳定；
- 缺少缺陷结果不等于无缺陷风险；
- 不兼容能量不能通过单位转换变得可比；
- `--allow-incomplete` 产生的是诊断，不是完整证据。

## 16.9 可复现性清单

每次正式运行至少保存：

- ss-screen 版本和 Git 提交；
- Python、依赖和操作系统信息；
- MP/WBM 数据来源、查询和快照哈希；
- 全部命令、阈值和输出目录；
- condensed manifest 和 validation；
- gap tasks、方法元数据、规范结果和拒绝报告；
- SQS 超胞、组分、cutoff、步数和种子；
- MACE 模型名称、SHA、dtype、fmax 和晶胞模式；
- 声子超胞、位移、网格、容差和 NAC 状态；
- 竞争相来源、覆盖和失败列表；
- 最终推荐表、报告和生成时间。

## 16.10 数据审计

项目交付前检查 CSV/JSON/JSONL 是否可以重新读取，结构文件哈希是否存在，失败记录是否保留，输出路径是否仍有效。不要只保存最终推荐 CSV 而删除上游证据。

# 第十七章 常见问题与维护

## 17.1 命令无法执行

确认虚拟环境和入口：

```bash
source .venv/bin/activate
python --version
python -c "import ssscreen; print(ssscreen.__version__)"
ss-screen --help
```

版本不是 0.1.0 时，不应继续使用本手册中的固定参数说明，应切换到对应版本手册。

## 17.2 数据集读取失败

检查文件是否存在、是否由可信 Python 环境生成、DataFrame 是否包含 `structure` 列。Pickle 只能从可信来源读取，因为反序列化可能执行代码。

## 17.3 组成候选过少

分别检查 `max-e-hull`、`max-bandgap`、排除元素、价态过滤、`nelems`、最小组大小和 X 元素数量。逐项变化并保存 summary，不要同时改变多个参数。

## 17.4 condensed失败

查看 manifest 的 error 字段，确认 robocrys extra、输入结构、占位和输出权限。先用 `--limit 1` 或单一 `--input` 重现。

## 17.5 结构匹配为零

确认候选 ID 与 JSON 文件名一致，运行 `condense-validate`，检查 `min-x-elements` 和二元/三元设置。缺少描述文件必须计入 summary。

## 17.6 gap校验拒绝

常见原因包括未知 task ID、材料 ID 不一致、方法不一致、结构哈希变化、重复行、非法负带隙、失败行却填写数值。根据 rejected 表逐行修复，不要删除拒绝报告。

## 17.7 pair数量异常

先查看 gap coverage，再检查方法选择和阈值。覆盖率低时不应通过放宽阈值掩盖缺失计算。

## 17.8 SQS组分不精确

有限超胞不能表达目标分数时增大超胞，或选择可表达的目标组分。始终以 `actual_fraction_b` 作为后续能量插值优先依据。

## 17.9 MACE未收敛

检查模型元素覆盖、初始结构、最大力、步数和设备错误。可增加最大步数、调整 fmax 或先只优化原子位置。参数变化后使用新运行指纹。

## 17.10 声子出现虚频

检查输入残余力、超胞、位移幅度、模型精度、参考力扣除和 q 网格。对重要软模使用更大超胞和 DFT 力复核。

## 17.11 凸包不完整

检查 competing export 报告、被跳过大结构、查询超时、竞争相驰豫失败和模型兼容状态。离线快照无法提供在线 thermo type 过滤，应保留范围警告。

## 17.12 推荐为uncertain

读取 missing_data、risks 和 source_warnings。补齐缺失的 gap、混合焓、声子或凸包结果后重新生成，不要手工修改 classification 列。

## 17.13 备份和归档

建议在每个阶段结束后备份 manifest、summary、配置、哈希和结果表。大型结构和计算输出使用项目外制品存储；Git 只跟踪代码、文档和微型测试夹具。

## 17.14 升级软件

升级前复制现有项目目录，记录旧版本和依赖。先执行测试和一个小型 artifact-chain，再处理旧 schema。不同版本产物不得在没有兼容性验证时直接混用。

# 附录A 命令速查

## A.1 顶层命令

| 命令 | 作用 |
|---|---|
| `ss-screen dataset mp` | 构建 Materials Project 数据表 |
| `ss-screen dataset wbm` | 读取 WBM extxyz |
| `ss-screen valence-filter` | 可选价态过滤 |
| `ss-screen composition-screen` | 组成模板候选筛选 |
| `ss-screen condense` | 生成 robocrys 描述 |
| `ss-screen condense-index` | 建立描述归档索引 |
| `ss-screen condense-validate` | 校验描述归档 |
| `ss-screen structure-match` | 局部环境匹配 |
| `ss-screen group` | 历史兼容分组入口 |
| `ss-screen gap-export` | 导出外部带隙任务 |
| `ss-screen gap-validate` | 校验和规范外部带隙 |
| `ss-screen pair` | 枚举端元对 |
| `ss-screen gap-compare` | 比较多个 gap 方法 |
| `ss-screen recommend` | 汇总和分类候选 |

## A.2 stability命令

| 命令 | 作用 |
|---|---|
| `stability sqs-generate` | 生成随机或 icet SQS |
| `stability relax` | MACE 驰豫和 E/F/stress |
| `stability mixing-enthalpy` | 计算每组分混合焓 |
| `stability phonon-export` | 生成有限位移任务 |
| `stability phonon-forces` | 计算位移能量和力 |
| `stability phonon-collect` | 构建力常数、频带和 DOS |
| `stability phonon-run` | 一步式声子流程 |
| `stability competing-export` | 导出 MP 竞争相 |
| `stability competing-relax` | 驰豫竞争相 |
| `stability convex-hull` | 构建同 MLP 凸包 |
| `stability phase-diagram` | 一步式竞争相与凸包 |

## A.3 获取实时帮助

```bash
ss-screen --help
ss-screen COMMAND --help
ss-screen dataset COMMAND --help
ss-screen stability COMMAND --help
```

命令实现和默认参数以当前安装版本的实时帮助为准。

# 附录B 文件格式与字段

## B.1 Pickle DataFrame

用于保存 pymatgen Structure 及材料属性。主要字段包括材料 ID 索引、formula、composition、reduced_composition、nelems、band_gap、e_hull、structure 和 source。Pickle 不是跨语言长期归档格式。

## B.2 CSV

CSV 用于候选、任务、规范 gap、端元对、混合焓、声子、凸包和推荐表。要求 UTF-8 编码、首行列名、缺失值为空并由状态字段解释、数值单位固定。

## B.3 JSON

JSON 用于结构组、provenance、阶段 summary 和方法元数据。阶段 summary 应记录输入输出路径、计数、参数、软件版本和失败摘要。

## B.4 JSONL

JSONL 每行一个完整任务对象，适合大量独立结构并支持增量恢复。manifest 中至少保存稳定 ID、输入哈希、设置、状态、输出路径和错误。

## B.5 晶体结构

外部带隙任务支持 pymatgen JSON、CIF 和 POSCAR。manifest 必须注明结构格式、原子数、primitive 处理和 SHA-256。SQS 和驰豫结构主要保存为 pymatgen JSON。

## B.6 状态和单位

| 数量 | 单位 |
|---|---|
| band_gap | eV |
| energy_total | eV |
| energy_per_atom / energy_above_hull | eV/atom |
| mixing_enthalpy | eV/atom 和 meV/atom |
| force | eV/Å |
| stress | eV/Å³ 和 GPa |
| displacement | Å |
| phonon frequency | THz |

## B.7 敏感信息

输出不得含 API 密钥、SSH 密钥、数据库密码、商业软件许可证内容或未脱敏凭据。外部过程 UUID、材料 ID、模型 SHA 和数据快照 SHA 可以作为 provenance 保存。

# 附录C 文档版本记录

## C.1 文档对应关系

| 项目 | 内容 |
|---|---|
| 软件全称 | 新材料计算筛选软件 |
| 软件简称 | SS-Screen |
| 软件版本 | V0.1.0 |
| Python 包 | ss-screen 0.1.0 |
| 文档类型 | 软件操作手册 / 文档鉴别材料 |
| 文档日期 | 2026年8月5日 |

## C.2 版本记录

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026年8月5日 | V0.1.0 | 增加窄带隙与光伏型红外探测的研发背景 |
| 2026年8月4日 | V0.1.0 | 根据当前真实 CLI 编制软件著作权登记版操作手册 |

## C.3 提交前核对

正式提交前必须把封面的著作权人替换为与申请表完全一致的自然人、法人或非法人组织名称，并重新生成 DOCX/PDF。源程序鉴别材料应使用相同软件全称和版本号，独立连续编号。

提交前按以下清单逐项复核：

1. 申请表、操作手册和源程序的软件全称完全一致；
2. 申请表、操作手册和源程序的版本号均为 V0.1.0；
3. 封面著作权人名称与身份证明或主体登记证明一致；
4. 文档中不再存在未替换的著作权人占位文字；
5. PDF 为 A4 纵向，文字、表格和代码块清晰可辨；
6. 封面不编号，目录页从逻辑页码 1 开始连续编号；
7. 正文每页页眉包含软件全称和 V0.1.0；
8. 每页右上角页码连续，不存在缺页或重复页；
9. 文档目录与正文章节顺序一致；
10. 所有命令、参数和输出名称均属于当前 V0.1.0 已实现功能；
11. 手册不包含 API 密钥、账号密码、内网地址或个人隐私信息；
12. 本地绝对路径、临时目录和测试凭据未出现在提交文档中；
13. 源程序与手册反映同一个已固化的软件版本；
14. 源程序和文档鉴别材料分别连续编号，不混用页码；
15. 根据最终总页数决定提交全部文档或前、各 30 页；
16. 上传前从头到尾打开最终 PDF，确认无乱码、遮挡、截断或空白页；
17. 保留最终 PDF、可编辑 DOCX、Markdown 源文和生成脚本作为归档；
18. 记录提交日期、文件校验值和对应的源代码版本。
