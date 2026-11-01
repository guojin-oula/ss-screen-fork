# SS-Screen 当前能力、测试方法与同事交接清单

日期：2026-09-12

## 1. 当前能达到的水平

### 1.1 GUI

- GUI 可以在 Windows 上运行。
- `src/ssscreen/gui/app.py` 可以直接在 PyCharm 中启动。
- GUI 不是静态界面，按钮会调用真实 `ss-screen` CLI。
- GUI 已支持运行后端选择：
  - Windows Python
  - WSL `.venv`
  - WSL `.venv-mlp`

### 1.2 GUI 与 WSL 后端联动

当前已验证：

```text
Windows GUI
  -> QProcess
  -> wsl.exe
  -> source .venv/bin/activate
  -> ss-screen ...
```

GUI 可以在 Windows 显示，实际计算命令在 WSL 中运行。

### 1.3 本地 POSCAR 文件夹作为 Stage 01 输入

当前输入目录：

```text
D:\WorkSpace\OtherProjects\ss-screen\data\CaS_CaSe_CaTe_POSCAR
```

目录结构：

```text
CaS/POSCAR
CaSe/POSCAR
CaTe/POSCAR
```

已新增并测试 CLI：

```bash
ss-screen dataset structures \
  --input-dir data/CaS_CaSe_CaTe_POSCAR \
  --output local_structures.df
```

该命令会递归读取 POSCAR/CIF/vasp/json 结构文件，并生成标准 Stage 01 DataFrame。

### 1.4 POSCAR 流程已跑通范围

使用 `data/CaS_CaSe_CaTe_POSCAR` 已经跑通：

| 阶段 | 状态 |
|---|---|
| POSCAR 导入 | 3 条结构 |
| 组成模板筛选 | 3 条候选，1 个模板 |
| 结构描述归档 | 3 个成功 |
| 结构描述校验 | 3 个有效 |
| 结构匹配 | 1 个结构组 |
| gap 任务导出 | 3 个任务 |
| gap 结果校验 | 3 accepted |
| 端元配对 | 2 对 |
| SQS 生成 | 2 条 manifest |
| 混合焓 | 2 条成功 |
| 综合推荐 | 1 个 promising，1 个 low-priority |

本轮输出目录：

```text
D:\WorkSpace\OtherProjects\ss-screen\work\poscar-gui-cli-20260911
```

### 1.5 PyTorch / MACE / phonopy 环境

WSL `.venv-mlp` 当前状态：

| 项 | 状态 |
|---|---|
| Python | 3.11.16 |
| torch | 2.5.1+cu121 |
| CUDA | 可用 |
| GPU | NVIDIA GeForce RTX 4060 |
| mace-torch | 0.3.14 |
| phonopy | 4.5.0 |
| MACECalculator 导入 | 成功 |

## 2. 已测试的方法

### 2.1 CLI 直接测试

已运行过的主要命令：

```bash
ss-screen dataset structures
ss-screen composition-screen
ss-screen condense
ss-screen condense-validate
ss-screen structure-match
ss-screen gap-export
ss-screen gap-validate
ss-screen pair
ss-screen stability sqs-generate
ss-screen stability mixing-enthalpy
ss-screen recommend
```

### 2.2 GUI 调 WSL 测试

测试链路：

```text
GUI -> QProcess -> wsl.exe -> source .venv/bin/activate -> ss-screen --version
```

结果：

```text
exit code = 0
GUI 日志显示 SS-Screen version 1.0
```

### 2.3 GUI 调 WSL 导入 POSCAR 文件夹

测试链路：

```text
GUI -> WSL -> ss-screen dataset structures --input-dir data/CaS_CaSe_CaTe_POSCAR
```

结果：

```text
exit code = 0
生成 3 行 DataFrame
```

### 2.4 PyTorch / CUDA 测试

测试内容：

```python
import torch
torch.cuda.is_available()
```

结果：

```text
True
```

并验证 CUDA tensor smoke：

```text
torch_cuda_smoke True 4.0
```

### 2.5 自动测试

运行：

```bash
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

### 2.6 静态检查

运行：

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

## 3. 当前还不是真实科研结果的部分

以下部分目前用于流程联调，不代表真实科研结论：

- gap 结果是 fixture 模拟结果，不是同事真实 VASP 结果。
- mixing enthalpy 使用的是模拟 relaxation 记录。
- phonon 和 phase stability 使用的是 fixture 证据。
- 真实 MACE 还没跑，因为缺模型 checkpoint。
- 真实 `mp_offline` 还没跑，因为缺包和数据库。
- POSCAR 文件本身不包含 band gap 和 e_hull；没有 metadata 时只能使用默认值跑通流程。

## 4. 需要同事提供的内容

### 4.1 VASP 计算结果

最好按 `gap_tasks.csv` 的 `task_id` 建目录，每个目录下提供：

```text
vasprun.xml
```

或：

```text
vasprun.xml.gz
```

同时说明计算方法：

- HSE
- mBJ
- PBE
- 是否 SOC
- 其他关键 INCAR/KPOINTS/POTCAR 设置

### 4.2 POSCAR 对应 metadata

如果继续把 POSCAR 文件夹作为 Stage 01 数据源，需要提供类似：

```csv
material_id,band_gap,e_hull,source
CaS,0.0,0.0,mp-or-wbm
CaSe,0.45,0.0,mp-or-wbm
CaTe,0.65,0.0,mp-or-wbm
```

至少需要字段：

- `material_id`
- `band_gap`
- `e_hull`
- `source`

### 4.3 MACE 模型

需要模型文件，例如：

```text
models/mace-mpa-0-medium.model
```

同时需要：

- 模型名称
- SHA-256
- 推荐 `dtype`
- 推荐 `device`
- 推荐 `fmax`
- 推荐 `max_steps`

### 4.4 mp_offline

需要：

- `mp_offline` Python 包或源码路径
- SQLite 数据库文件
- 数据库版本或 SHA-256
- 数据库来源说明

### 4.5 WBM 数据

如果要跑 WBM 输入，需要：

- `.xyz` / `.extxyz`
- summary CSV/TSV
- 字段说明
- 数据来源版本

### 4.6 OpenBabel

当前不是硬阻塞。

`robocrys` 会提示缺少 OpenBabel Python bindings。如果同事要求结构描述更完整，需要提供 WSL/Ubuntu 下 OpenBabel Python bindings 的安装方案。

## 5. 当前结论

软件链路和 GUI-WSL 联动已经打通。

当前主要缺真实数据和真实计算产物：

- 真实 VASP gap 结果
- POSCAR 对应真实 `band_gap/e_hull` metadata
- MACE 模型 checkpoint
- `mp_offline` 包和数据库
- 可选 OpenBabel 安装方案

拿到这些后，可以继续做真实 gap 收集、真实 MACE 单结构冒烟、真实 phonopy 力计算和离线 MP 竞争相流程。
