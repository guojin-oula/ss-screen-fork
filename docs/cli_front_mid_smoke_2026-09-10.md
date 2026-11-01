# SS-Screen CLI 前中段流程验证交接单

日期：2026-09-10

目的：先在 WSL 中确认后台 CLI 主流程可以启动并串联，再梳理真实运行还需要同事提供的输入数据、模型和外部计算结果。

## 1. 当前结论

CLI 前中段主链路已经可以在 WSL 中跑通。此次使用微型合成数据集验证流程连通性，不代表真实科研筛选结果。

已验证通过的阶段：

| Word 流程 | CLI 阶段 | 本次状态 |
|---|---|---|
| 运行环境与安装 | Python 环境、`ss-screen` 命令 | 已跑通 |
| 第一步：软件数据收集 | 测试 DataFrame 输入 | 已用合成数据替代跑通 |
| 第二步：结构描述归档 | `condense` / `condense-index` / `condense-validate` | 已跑通 |
| 第三步：结构匹配与材料分组 | `structure-match` | 已跑通 |
| 第四步：高精度带隙任务交接 | `gap-export` | 已跑通任务导出 |
| 第五步：端元配对与方法比较 | `gap-validate` / `pair` | 已跑通 |
| 第六步：SQS 合金结构生成 | `stability sqs-generate` | 已跑通 |
| 第七步：MACE 结构驰豫 | `stability relax` | 命令存在，真实运行缺 MACE/Torch/模型 |
| 第八步：混合焓计算 | `stability mixing-enthalpy` | 已用模拟驰豫结果跑通 |
| 第九步：声子谱计算 | `stability phonon-*` | 命令存在，真实运行缺 phonopy/MACE/Torch/模型 |
| 第十步：竞争相与凸包分析 | `stability phase-diagram` | 命令存在，真实运行缺 MP 数据源和真实能量结果 |
| 第十一步：综合推荐 | `stability recommend` | 未在本轮跑；需前面真实制品后再验证 |

## 2. WSL 环境状态

仓库路径：

```bash
/mnt/d/WorkSpace/OtherProjects/ss-screen
```

启动环境：

```bash
cd /mnt/d/WorkSpace/OtherProjects/ss-screen
source .venv/bin/activate
python --version
ss-screen --version
```

当前已确认：

- Python：3.11.16
- `ss-screen`：可运行
- 已安装并可导入：`mp-api`、`ase`、`robocrys`、`matminer`、`icet`
- 未安装或未配置：`mace`、`torch`、`phonopy`、`mp_offline`
- `pytest tests/test_e2e_pipeline.py -q` 已通过
- `uv pip check --python .venv/bin/python` 已通过

注意：当前 `.venv` 在 Windows 挂载盘 `/mnt/d` 下，首次安装依赖较慢。后续如果长期在 WSL 跑，建议把项目复制到 WSL 原生目录，例如 `/home/sipesc/projects/ss-screen`。

## 3. 本次验证产物

测试输出目录：

```text
D:\WorkSpace\OtherProjects\ss-screen\work\cli-front-mid-20260910
```

对应 WSL 路径：

```text
/mnt/d/WorkSpace/OtherProjects/ss-screen/work/cli-front-mid-20260910
```

主要产物：

| 文件 | 含义 | 本次结果 |
|---|---|---|
| `01_dataset.df` | 测试数据集 | 3 个材料：CaS、CaSe、CaTe |
| `02_composition_candidates.csv` | 组成模板筛选候选 | 3 行 |
| `02_composition_summary.json` | 组成筛选摘要 | 1 个模板 |
| `03_condensed_generated/` | 实测生成的结构描述 | 1 个结构描述 |
| `03_condensed_index.csv` | 结构描述索引 | 1 行 |
| `03_condensed_validation.csv` | 结构描述校验 | 1 行有效 |
| `04_groups.json` | 结构匹配分组 | 1 组 |
| `04_structure_summary.json` | 分组摘要 | 3 个成员，无缺失描述 |
| `05_gap_tasks.csv` | 高精度带隙任务清单 | 3 个任务 |
| `05_gap_results_template.csv` | 带隙结果回填模板 | 已生成 |
| `05_gap_results_normalized.csv` | 带隙结果规范化输出 | 3 行 accepted |
| `06_final_pairs.csv` | 端元配对结果 | 2 对 |
| `07_sqs_manifest.jsonl` | SQS 结构 manifest | 2 条 |
| `08_relaxation_results_fixture.jsonl` | 模拟 MACE 驰豫结果 | 用于继续验证混合焓接口 |
| `09_mixing_enthalpy.csv` | 混合焓结果 | 2 行 |
| `09_mixing_summary.json` | 混合焓摘要 | 2 成功、0 失败 |

## 4. 本次操作流水

### 4.1 准备环境

```bash
cd /mnt/d/WorkSpace/OtherProjects/ss-screen
source .venv/bin/activate
python --version
ss-screen --version
```

### 4.2 生成测试数据

本次手工生成了 3 个 rocksalt 测试材料的规范化 DataFrame：

- `mp-cas`：CaS
- `mp-case`：CaSe
- `mp-cate`：CaTe

输出：

```text
work/cli-front-mid-20260910/01_dataset.df
```

### 4.3 组成模板筛选

```bash
ss-screen composition-screen \
  --df work/cli-front-mid-20260910/01_dataset.df \
  --nelems 2 \
  --max-bandgap 1.0 \
  --max-e-hull 0.01 \
  --output work/cli-front-mid-20260910/02_composition_candidates.csv \
  --summary work/cli-front-mid-20260910/02_composition_summary.json
```

结果：3 条候选，1 个模板。

### 4.4 结构描述归档

```bash
ss-screen condense \
  --df work/cli-front-mid-20260910/01_dataset.df \
  --limit 1 \
  --output-dir work/cli-front-mid-20260910/03_condensed_generated \
  --manifest work/cli-front-mid-20260910/03_condensed_manifest.jsonl \
  --index work/cli-front-mid-20260910/03_condensed_index.csv \
  --overwrite

ss-screen condense-index \
  --condensed-dir work/cli-front-mid-20260910/03_condensed_generated \
  --output work/cli-front-mid-20260910/03_condensed_index_rebuilt.csv

ss-screen condense-validate \
  --condensed-dir work/cli-front-mid-20260910/03_condensed_generated \
  --output work/cli-front-mid-20260910/03_condensed_validation.csv
```

结果：写出 1 个结构描述，校验有效。

备注：`condense` 阶段出现 OpenBabel Python bindings 警告，目前是非致命警告。

### 4.5 结构匹配与材料分组

```bash
ss-screen structure-match \
  --candidates work/cli-front-mid-20260910/02_composition_candidates.csv \
  --condensed-dir tests/data/e2e/condensed \
  --output work/cli-front-mid-20260910/04_groups.json \
  --summary work/cli-front-mid-20260910/04_structure_summary.json
```

结果：生成 1 个结构组，包含 3 个成员。

### 4.6 高精度带隙任务导出

```bash
ss-screen gap-export \
  --groups work/cli-front-mid-20260910/04_groups.json \
  --dataset work/cli-front-mid-20260910/01_dataset.df \
  --method fixture-hse-v1 \
  --structure-dir work/cli-front-mid-20260910/05_gap_structures \
  --structure-format json \
  --results-template work/cli-front-mid-20260910/05_gap_results_template.csv \
  --output work/cli-front-mid-20260910/05_gap_tasks.csv
```

结果：导出 3 个 gap 任务。

### 4.7 带隙结果回填与校验

本次手工填写模拟返回结果：

```text
work/cli-front-mid-20260910/05_gap_results_returned.csv
```

然后运行：

```bash
ss-screen gap-validate \
  --gaps work/cli-front-mid-20260910/05_gap_results_returned.csv \
  --tasks work/cli-front-mid-20260910/05_gap_tasks.csv \
  --output work/cli-front-mid-20260910/05_gap_results_normalized.csv \
  --rejected work/cli-front-mid-20260910/05_gap_results_rejected.csv \
  --report work/cli-front-mid-20260910/05_gap_validation.json
```

结果：3 条 accepted，0 条 rejected。

### 4.8 端元配对

```bash
ss-screen pair \
  --groups work/cli-front-mid-20260910/04_groups.json \
  --gap-results work/cli-front-mid-20260910/05_gap_results_normalized.csv \
  --method fixture-hse-v1 \
  --summary work/cli-front-mid-20260910/06_pair_summary.json \
  --output work/cli-front-mid-20260910/06_final_pairs.csv
```

结果：生成 2 对端元：

- CaS - CaSe
- CaS - CaTe

### 4.9 SQS 合金结构生成

```bash
ss-screen stability sqs-generate \
  --pairs work/cli-front-mid-20260910/06_final_pairs.csv \
  --dataset work/cli-front-mid-20260910/01_dataset.df \
  --supercell 2,1,1 \
  --backend random \
  --seed 7 \
  --output-dir work/cli-front-mid-20260910/07_sqs \
  --manifest work/cli-front-mid-20260910/07_sqs_manifest.jsonl
```

结果：写出 2 条 SQS manifest 记录。

### 4.10 混合焓计算

真实 MACE 驰豫尚未配置，因此本次使用模拟驰豫结果文件：

```text
work/cli-front-mid-20260910/08_relaxation_results_fixture.jsonl
```

然后运行：

```bash
ss-screen stability mixing-enthalpy \
  --pairs work/cli-front-mid-20260910/06_final_pairs.csv \
  --relax-results work/cli-front-mid-20260910/08_relaxation_results_fixture.jsonl \
  --output work/cli-front-mid-20260910/09_mixing_enthalpy.csv \
  --summary work/cli-front-mid-20260910/09_mixing_summary.json
```

结果：2 条混合焓计算成功。

## 5. 需要同事提供或确认的内容

### 5.1 真实 MP 数据源

二选一即可：

- Materials Project API Key，并确认允许联网查询。
- `mp_offline` 离线数据库，包括数据库文件、安装方式、版本或 SHA-256。

用途：

- Stage 1 MP 数据收集
- Stage 10 竞争相与凸包分析

### 5.2 真实 WBM 数据源

需要：

- WBM 结构主文件，例如 `.xyz` / `.extxyz`
- summary 或 metadata 文件
- 字段说明，至少包括材料 ID、组成、结构、band gap、energy above hull 或对应可转换字段
- 数据来源版本和生成记录

用途：

- Stage 1 WBM 数据收集
- 后续 MP/WBM 或 WBM/WBM 筛选

### 5.3 高精度带隙结果

需要同事确认交接方式：

- 直接按 `05_gap_results_template.csv` 填写返回
- 或提供 VASP 结果目录，每个任务目录下包含 `vasprun.xml` 或 `vasprun.xml.gz`
- 同时提供计算方法说明，例如 HSE、mBJ、PBE+修正等

用途：

- Stage 4 高精度带隙结果回收
- Stage 5 端元配对

### 5.4 MACE 驰豫环境

需要：

- MACE 模型文件，例如 `mace-mpa-0-medium.model`
- 模型 SHA-256 或版本说明
- `mace-torch` 推荐版本
- `torch` / CUDA 版本要求
- 明确先用 CPU 还是 GPU

用途：

- Stage 7 MACE 结构驰豫
- Stage 8 混合焓真实能量输入
- Stage 9 声子谱力计算
- Stage 10 凸包竞争相统一能量

### 5.5 phonopy 声子谱环境

需要：

- phonopy 推荐版本
- 超胞设置、位移距离、mesh 设置
- 是否统一使用 MACE 作为 force backend

用途：

- Stage 9 声子谱计算和动力学稳定性判断

### 5.6 OpenBabel 可选依赖

当前 `robocrys` 运行时提示缺少 OpenBabel Python bindings。它不是当前无机晶体测试的硬阻塞，但建议同事确认：

- 是否必须安装 OpenBabel
- 若必须，给出 WSL/Ubuntu 下推荐安装方式

用途：

- 改善 `robocrys` 结构描述中的分子/局部环境命名能力

## 6. 当前真实阻塞点

当前 CLI 本身不是阻塞点。阻塞在真实科研数据和重计算依赖：

- 没有真实 MP/WBM 数据源时，只能跑教学或合成数据。
- 没有高精度 gap 返回结果时，只能导出任务，不能完成真实端元配对证据闭环。
- 没有 MACE/Torch/模型时，不能做真实结构驰豫、真实混合焓、声子力和统一能量凸包。
- 没有 phonopy 时，不能做真实声子谱。

## 7. 下一步建议

建议先让同事按第 5 节提供最小真实材料包：

1. 一个 10 到 100 条材料的小型 MP 或 WBM 数据样例。
2. 对应的 condensed 结构描述，或者允许本地 `condense` 重新生成。
3. 一份高精度 gap 返回 CSV 或 VASP 测试结果目录。
4. 一个可用的 MACE 模型文件和 CPU/GPU 运行说明。

拿到这些后，可以先跑一轮“小真实数据”端到端流程，再把 GUI 每个节点绑定到对应 CLI 命令和产物路径。

## 8. 2026-09-11 POSCAR 输入与 GUI/WSL 联动复测

### 8.1 本轮新增能力

本轮把用户提供的本地 POSCAR 文件夹纳入 Stage 01 数据源：

```text
D:\WorkSpace\OtherProjects\ss-screen\data\CaS_CaSe_CaTe_POSCAR
```

目录中包含：

```text
CaS/POSCAR
CaSe/POSCAR
CaTe/POSCAR
```

新增 CLI：

```bash
ss-screen dataset structures \
  --input-dir data/CaS_CaSe_CaTe_POSCAR \
  --band-gap-default 0.0 \
  --e-hull-default 0.0 \
  --source local-poscar \
  --output work/poscar-gui-cli-20260911/01_local_structures.df \
  --provenance work/poscar-gui-cli-20260911/01_local_structures.provenance.json
```

说明：

- 该命令递归扫描 POSCAR/CIF/vasp/json 文件。
- 对 `POSCAR`/`CONTCAR`，默认使用父目录名作为 `material_id`，例如 `CaS/POSCAR` → `CaS`。
- POSCAR 文件本身只有结构，没有真实 band gap 和 e_hull；本轮用默认值跑通流程。
- 真实筛选时应提供 metadata CSV/TSV，至少包含 `material_id`、`band_gap`、`e_hull`，可选 `source`。

### 8.2 GUI 与 WSL 后端连接

GUI 已改为可选择运行后端：

- Windows Python / 当前解释器
- WSL Python / `.venv`
- WSL Python / `.venv-mlp`

WSL 模式下 GUI 实际执行形式：

```bash
wsl.exe bash -lc 'cd /mnt/d/WorkSpace/OtherProjects/ss-screen && source .venv/bin/activate && PYTHONUNBUFFERED=1 ss-screen ...'
```

已做 headless Qt smoke：

```text
GUI → QProcess → wsl.exe → source .venv/bin/activate → ss-screen --version
```

结果：exit code = 0，GUI 日志中收到 `SS-Screen version 1.0`。

另做了更贴近真实入口的 GUI/WSL 文件夹导入 smoke：

```text
GUI → QProcess → WSL → ss-screen dataset structures --input-dir data/CaS_CaSe_CaTe_POSCAR
```

结果：exit code = 0，生成：

```text
work/gui-wsl-link-20260911/01_local_structures.df
```

### 8.3 POSCAR 文件夹实际流程测试

本轮输出目录：

```text
D:\WorkSpace\OtherProjects\ss-screen\work\poscar-gui-cli-20260911
```

对应 WSL 路径：

```text
/mnt/d/WorkSpace/OtherProjects/ss-screen/work/poscar-gui-cli-20260911
```

已跑通：

| 阶段 | 命令 / 产物 | 结果 |
|---|---|---|
| 本地结构数据导入 | `dataset structures` → `01_local_structures.df` | 3 行：CaS、CaSe、CaTe |
| 组成模板筛选 | `composition-screen` → `02_composition_candidates.csv` | 3 条候选，1 个模板 |
| 结构描述归档 | `condense` → `03_condensed/` | 3 写出、0 跳过、0 失败 |
| 结构描述校验 | `condense-validate` → `03_condensed_validation.csv` | 3 有效、0 无效 |
| 结构匹配 | `structure-match` → `04_groups.json` | 1 个结构组，无缺失描述 |
| 高精度 gap 任务导出 | `gap-export` → `05_gap_tasks.csv` | 3 个任务，导出 JSON/POSCAR 结构 |
| gap 结果校验 | `gap-validate` → `05_gap_results_normalized.csv` | 3 accepted、0 rejected |
| 端元配对 | `pair` → `06_final_pairs.csv` | 2 对 |
| SQS 生成 | `stability sqs-generate` → `07_sqs_manifest.jsonl` | 2 条 manifest |
| 混合焓 | `stability mixing-enthalpy` → `09_mixing_enthalpy.csv` | 2 成功、0 失败 |
| 综合推荐 | `recommend` → `12_recommendations.csv` | 1 promising、1 low-priority |

端元配对结果：

| comp_a | comp_b | gap_a | gap_b | direct_a | direct_b | method |
|---|---|---:|---:|---|---|---|
| CaS | CaSe | 0.00 | 0.45 | true | true | `poscar-fixture-hse-v1` |
| CaS | CaTe | 0.00 | 0.65 | true | false | `poscar-fixture-hse-v1` |

推荐结果：

| comp_a | comp_b | classification | evidence_level |
|---|---|---|---|
| CaS | CaSe | promising | L5 |
| CaS | CaTe | low-priority | L5 |

注意：gap、relaxation、phonon 和 phase-stability 是本轮手工 fixture 证据，用于验证文件契约和流程联通，不代表真实材料结论。

### 8.4 PyTorch / MACE / phonopy 状态

WSL `.venv-mlp` 当前状态：

| 项 | 状态 |
|---|---|
| Python | 3.11.16 |
| torch | 2.5.1+cu121 |
| CUDA | 可用 |
| GPU | NVIDIA GeForce RTX 4060 |
| mace-torch | 0.3.14 |
| phonopy | 4.5.0 |
| numpy | 1.26.4 |
| `MACECalculator` 导入 | 成功 |
| `stability relax --help` | 成功 |
| `stability phonon-run --help` | 成功 |
| `stability phase-diagram --help` | 成功 |

未做真实 MACE/phonopy 计算，原因是：

- `models/mace-mpa-0-medium.model` 仍缺失；
- 当前没有同事确认的真实 checkpoint、模型 SHA 和运行设置。

### 8.5 本轮新增测试与验证

已通过：

```bash
python -m py_compile \
  src/ssscreen/data/structures.py \
  src/ssscreen/cli/app.py \
  src/ssscreen/gui/app.py \
  src/ssscreen/gui/metadata.py

python -m pytest \
  tests/test_data_structures.py \
  tests/test_cli.py::test_dataset_structures_command_invokes_loader \
  tests/test_e2e_pipeline.py \
  tests/test_stability_relax.py \
  tests/test_stability_phonon.py \
  -q
```

结果：

```text
18 passed
```

另跑：

```bash
ruff check \
  src/ssscreen/data/structures.py \
  src/ssscreen/cli/app.py \
  src/ssscreen/gui/app.py \
  src/ssscreen/gui/metadata.py \
  tests/test_data_structures.py \
  tests/test_cli.py
```

结果：

```text
All checks passed
```

### 8.6 现阶段仍需要同事提供

1. 真实 gap 结果：最好是按 `gap-export` 生成的 `tasks.csv` 目录结构返回 VASP `vasprun.xml` 或 `vasprun.xml.gz`。
2. 本地结构 metadata：如果继续用 POSCAR 文件夹作为 Stage 01 数据源，需要每个结构的 `material_id, band_gap, e_hull, source`。
3. MACE checkpoint：例如 `mace-mpa-0-medium.model`，以及模型 SHA、模型名称、推荐 dtype、device、fmax、max steps。
4. `mp_offline` 包和 SQLite 数据库：用于离线 Materials Project 数据和 Stage 10 竞争相查询。
5. OpenBabel Python bindings 安装方案：当前 robocrys 可运行，但会提示缺少 OpenBabel；该项暂不阻塞无机结构测试。
