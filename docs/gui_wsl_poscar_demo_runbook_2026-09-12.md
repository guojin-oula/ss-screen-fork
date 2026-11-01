# SS-Screen GUI + WSL + POSCAR 现场演示步骤

日期：2026-09-12

目的：用于自己实际运行、给同事介绍当前进度，并说明下一步需要同事提供哪些真实计算材料。

## 1. 演示结论先讲清楚

当前已经能做到：

- Windows 上启动 GUI。
- GUI 通过 `wsl.exe` 调用 WSL 中的 `ss-screen` CLI。
- 选中本地 POSCAR 文件夹后，能导入 `CaS/POSCAR`、`CaSe/POSCAR`、`CaTe/POSCAR`。
- POSCAR 输入可以继续跑到组成筛选、结构描述、结构分组、gap 任务导出、端元配对、SQS 生成。
- PyTorch/CUDA/MACE/phonopy 环境已经装好并通过 import/help/smoke 测试。

需要避免误讲：

- 当前 gap、relaxation、phonon、phase stability 的后段结果是流程联调用的 fixture，不是真实科研结论。
- 软件本身不运行 VASP；它负责导出任务、收集和规范化 VASP 结果。
- 真实 MACE relax/phonon/phase 还需要模型 checkpoint 和真实前序结果。

## 2. 启动前检查

### 2.1 Windows 路径

仓库路径：

```text
D:\WorkSpace\OtherProjects\ss-screen
```

输入 POSCAR 文件夹：

```text
D:\WorkSpace\OtherProjects\ss-screen\data\CaS_CaSe_CaTe_POSCAR
```

当前已验证的输出目录：

```text
D:\WorkSpace\OtherProjects\ss-screen\work\poscar-gui-cli-20260911
```

### 2.2 WSL 路径

在 WSL 中对应路径是：

```bash
/mnt/d/WorkSpace/OtherProjects/ss-screen
```

检查轻量 CLI 环境：

```bash
cd /mnt/d/WorkSpace/OtherProjects/ss-screen
source .venv/bin/activate
python --version
ss-screen --version
```

预期：

```text
Python 3.11.16
SS-Screen version 1.0
```

检查 MLP 环境：

```bash
cd /mnt/d/WorkSpace/OtherProjects/ss-screen
source .venv-mlp/bin/activate
python - <<'PY'
import torch
print(torch.__version__)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "no cuda")
from mace.calculators import MACECalculator
print("MACECalculator import ok")
PY
```

预期：`torch.cuda.is_available()` 为 `True`，GPU 为 RTX 4060。

注意：当前 AGENTS.md 中历史记录的 `/home/zuolong/projects/ss-screen-learning-20260722` 在本机 WSL 中不存在；实际演示使用 `/mnt/d/WorkSpace/OtherProjects/ss-screen`。

## 3. GUI 现场演示推荐顺序

### 3.1 启动 GUI

在 PyCharm 中运行：

```text
src\ssscreen\gui\app.py
```

或在 Windows 终端中运行：

```powershell
cd D:\WorkSpace\OtherProjects\ss-screen
C:\SoftWare\Python\python.exe src\ssscreen\gui\app.py
```

建议先用 PyCharm 演示，因为同事更容易看到当前开发状态和代码入口。

### 3.2 右侧运行后端选择

在 GUI 右侧属性区选择：

```text
WSL .venv
```

解释口径：

```text
GUI 在 Windows 上显示，后端命令在 WSL 的项目虚拟环境里执行。
```

什么时候选 `WSL .venv-mlp`：

```text
后续真实运行 MACE、torch、phonopy 相关命令时再选。
```

当前 POSCAR 导入、组成筛选、condense、结构匹配、gap 导出、pair、SQS 演示用 `WSL .venv` 即可。

如果任务日志里出现：

```text
bash: line 1: .venv/bin/activate: No such file or directory
```

说明 GUI 当前工程目录被设成了 `src\ssscreen\gui` 之类的子目录，而不是仓库根目录。修复后的
`app.py` 会自动向上识别仓库根目录；重新启动 GUI 后重试即可。临时手动处理方式是在右侧
`WSL 工程路径` 填写：

```text
/mnt/d/WorkSpace/OtherProjects/ss-screen
```

### 3.3 Stage 01：本地 POSCAR 导入

左侧选择：

```text
01 数据源 / Materials Project / WBM
```

中间页签选择：

```text
Local POSCAR / 本地结构
```

填写：

| 字段 | 选择或填写 |
|---|---|
| 结构文件夹 | `data/CaS_CaSe_CaTe_POSCAR` |
| metadata | 留空 |
| 默认 band gap | `0.0` |
| 默认 e_hull | `0.0` |
| source | `local-poscar-demo` |
| output | `01_dataset/local_structures.df` |
| provenance | `01_dataset/local_structures.provenance.json` |

点击：

```text
导入本地结构
```

预期：日志中命令 exit code 为 0，并生成 3 行本地结构数据。

给同事解释：

```text
这一步对应 Word 手册里的第一步数据收集。以前主要是 MP/WBM，现在增加了本地 POSCAR 文件夹入口，
用于接收同事已经准备好的结构文件。
```

### 3.4 Stage 02：组成模板筛选

左侧选择：

```text
02 组成筛选
```

建议填写：

| 字段 | 选择或填写 |
|---|---|
| dataset df | `01_dataset/local_structures.df` |
| nelems | `2` |
| max bandgap | `1.0` |
| max e_hull | `0.01` |
| min group size | `2` |
| min X elements | `2` |
| output | `02_composition/composition_candidates.csv` |
| summary | `02_composition/composition_summary.json` |

如果界面中已有 `01_dataset/mp.df` 或 `01_dataset/wbm.df`，而当前没有这些文件，演示时先移除，只保留：

```text
01_dataset/local_structures.df
```

当前 GUI 已改为只自动加入真实存在的 `01_dataset/*.df`。如果你刚跑完本地 POSCAR 导入，进入组成筛选页后
点一次刷新参数，命令预览中应只看到：

```text
--df 01_dataset/local_structures.df
```

点击运行组成筛选。

预期：3 条候选，1 个模板。

### 3.5 Stage 03：结构描述归档

左侧选择：

```text
03 结构描述
```

在从 DataFrame 生成结构描述的区域填写：

| 字段 | 选择或填写 |
|---|---|
| DataFrame | `01_dataset/local_structures.df` |
| structure column | `structure` |
| output dir | `03_condensed/local` |
| manifest | `03_condensed/local_manifest.jsonl` |
| index | `03_condensed/local_index.csv` |
| limit | 留空 |

点击运行。

预期：CaS、CaSe、CaTe 三个结构描述生成成功。

然后在归档校验区域填写：

| 字段 | 选择或填写 |
|---|---|
| condensed dir | `03_condensed/local` |
| output | `03_condensed/local_validation.csv` |

点击校验。

预期：valid = 3，invalid = 0。

可能看到 OpenBabel Python bindings 警告；当前是非致命警告，不影响演示。

### 3.6 Stage 04：结构匹配

左侧选择：

```text
04 结构匹配
```

填写：

| 字段 | 选择或填写 |
|---|---|
| candidates | `02_composition/composition_candidates.csv` |
| condensed dir | `03_condensed/local` |
| output | `04_groups/groups.json` |
| summary | `04_groups/structure_match_summary.json` |

点击运行。

预期：生成 1 个结构组，包含 CaS、CaSe、CaTe。

### 3.7 Stage 05：高精度 gap 任务导出

左侧选择：

```text
05 高精度带隙
```

填写：

| 字段 | 选择或填写 |
|---|---|
| groups | `04_groups/groups.json` |
| dataset | `01_dataset/local_structures.df` |
| method | `poscar-demo-vasp-v1` |
| structure dir | `05_gap/structures` |
| structure format | 同时选择 `json` 和 `poscar` |
| results template | `05_gap/results_template.csv` |
| output tasks | `05_gap/tasks.csv` |

点击导出。

预期：

- 生成 `05_gap/tasks.csv`
- 生成 `05_gap/results_template.csv`
- 生成 `05_gap/structures/*.vasp`

这里是现场演示最适合停下来的真实交接点。

给同事解释：

```text
软件已经把需要做高精度带隙计算的任务和结构导出来了。
下一步同事用 VASP 计算，把 vasprun.xml 或整理好的结果按 task_id 回填给软件。
```

### 3.8 Stage 06：端元配对

如果没有同事提供真实 VASP 结果，不建议把 Stage 06 当成真实结果演示。

可以只展示历史测试目录中的 fixture 结果：

```text
work\poscar-gui-cli-20260911\06_final_pairs.csv
```

解释：

```text
这一步已经通过模拟 gap 结果验证了程序流程，但真实筛选结论要等 VASP gap 回填后再重新运行。
```

### 3.9 Stage 07 以后：稳定性链路

可以展示已有产物，但不要说成真实计算：

| 文件 | 当前用途 |
|---|---|
| `work\poscar-gui-cli-20260911\07_sqs_manifest.jsonl` | SQS 生成流程已验证 |
| `work\poscar-gui-cli-20260911\09_mixing_enthalpy.csv` | 使用模拟 relaxation 结果验证混合焓接口 |
| `work\poscar-gui-cli-20260911\10_phonon_summary_fixture.csv` | fixture 声子稳定性输入 |
| `work\poscar-gui-cli-20260911\11_phase_stability_fixture.csv` | fixture 凸包稳定性输入 |
| `work\poscar-gui-cli-20260911\12_recommendations.csv` | 综合推荐流程已串通 |

真实运行这些阶段前需要：

- MACE 模型 checkpoint，例如 `models/mace-mpa-0-medium.model`
- 真实 gap 结果
- 真实 relaxation 结果或允许软件调用 MACE relax
- phonopy/MACE 的真实力计算输入
- MP API 或 `mp_offline` 数据库

## 4. CLI 等价命令

如果 GUI 演示出问题，可以用 CLI 演示同一条链路。

### 4.1 POSCAR 导入

```bash
cd /mnt/d/WorkSpace/OtherProjects/ss-screen
source .venv/bin/activate

ss-screen dataset structures \
  --input-dir data/CaS_CaSe_CaTe_POSCAR \
  --band-gap-default 0.0 \
  --e-hull-default 0.0 \
  --source local-poscar-demo \
  --output work/demo-live-20260912/01_local_structures.df \
  --provenance work/demo-live-20260912/01_local_structures.provenance.json
```

### 4.2 组成筛选

```bash
ss-screen composition-screen \
  --df work/demo-live-20260912/01_local_structures.df \
  --nelems 2 \
  --max-bandgap 1.0 \
  --max-e-hull 0.01 \
  --min-group-size 2 \
  --min-x-elements 2 \
  --output work/demo-live-20260912/02_composition_candidates.csv \
  --summary work/demo-live-20260912/02_composition_summary.json
```

### 4.3 结构描述

```bash
ss-screen condense \
  --df work/demo-live-20260912/01_local_structures.df \
  --output-dir work/demo-live-20260912/03_condensed \
  --manifest work/demo-live-20260912/03_condensed_manifest.jsonl \
  --index work/demo-live-20260912/03_condensed_index.csv \
  --overwrite

ss-screen condense-validate \
  --condensed-dir work/demo-live-20260912/03_condensed \
  --output work/demo-live-20260912/03_condensed_validation.csv
```

### 4.4 结构匹配

```bash
ss-screen structure-match \
  --candidates work/demo-live-20260912/02_composition_candidates.csv \
  --condensed-dir work/demo-live-20260912/03_condensed \
  --output work/demo-live-20260912/04_groups.json \
  --summary work/demo-live-20260912/04_structure_summary.json
```

### 4.5 gap 任务导出

```bash
ss-screen gap-export \
  --groups work/demo-live-20260912/04_groups.json \
  --dataset work/demo-live-20260912/01_local_structures.df \
  --method poscar-demo-vasp-v1 \
  --structure-dir work/demo-live-20260912/05_gap_structures \
  --structure-format json \
  --structure-format poscar \
  --results-template work/demo-live-20260912/05_gap_results_template.csv \
  --output work/demo-live-20260912/05_gap_tasks.csv
```

## 5. 给同事的材料清单

### 5.1 请同事优先提供

1. VASP 带隙计算结果

   推荐按 `task_id` 建目录，每个目录放：

   ```text
   vasprun.xml
   ```

   或：

   ```text
   vasprun.xml.gz
   ```

2. VASP 计算方法说明

   需要说明：

   ```text
   HSE / mBJ / PBE
   是否 SOC
   INCAR 关键参数
   KPOINTS 设置
   POTCAR 版本或赝势选择
   ```

3. POSCAR 对应的基础元数据

   如果有，建议提供 CSV：

   ```text
   material_id,band_gap,e_hull,source
   CaS,0.0,0.0,local-poscar
   CaSe,0.0,0.0,local-poscar
   CaTe,0.0,0.0,local-poscar
   ```

4. MACE 模型 checkpoint

   例如：

   ```text
   models/mace-mpa-0-medium.model
   ```

   需要同时说明模型来源、版本、适用元素范围。

5. `mp_offline` 包和数据库，或 MP API Key

   用于后续竞争相和凸包分析。

### 5.2 暂时不必向同事要

- 让 SS-Screen 直接运行 VASP 的脚本。
- AiiDA daemon 配置。
- notebook 运行环境。

当前软件边界是 CLI/GUI 串联流程，不把 VASP 或 AiiDA 执行本身塞进演示。

## 6. 建议的汇报话术

可以按下面顺序讲：

1. 目前 GUI 已经不是空界面，按钮能调真实 CLI。
2. Windows GUI 可以调用 WSL 后端，解决了 Windows 上科学依赖不好装的问题。
3. 本地 POSCAR 文件夹已经接入 Stage 01，可以递归读取一个文件夹里的多个结构。
4. 用 CaS/CaSe/CaTe 跑通了从 POSCAR 到 gap 任务导出的前中段流程。
5. 后段 MACE/phonopy/PyTorch 环境已经准备好，但真实计算还缺 MACE 模型和真实 VASP gap 结果。
6. 下一步最关键是让同事按 `05_gap/tasks.csv` 和 `05_gap/structures/*.vasp` 做 VASP，并把结果回填。

不要说：

```text
已经筛选出真实 promising 材料。
```

建议说：

```text
已经把真实输入、GUI 联动和流程文件契约跑通；当前结果用于验证软件流程，真实材料结论需要同事的 VASP/MACE 数据补齐后重新跑。
```

## 7. 现场演示建议

推荐现场只做三件事：

1. 启动 GUI，展示左侧树状流程和右侧 WSL 后端选择。
2. 选择 `data\CaS_CaSe_CaTe_POSCAR`，运行本地 POSCAR 导入。
3. 展示已经生成的 `work\poscar-gui-cli-20260911\05_gap_tasks.csv` 和 `05_gap_structures\*.vasp`，说明这是交给 VASP 的任务包。

如果时间充足，再展示：

- `06_final_pairs.csv`
- `07_sqs_manifest.jsonl`
- `12_recommendation_report.md`

展示这些后段文件时必须说明它们是 fixture 联调结果。
