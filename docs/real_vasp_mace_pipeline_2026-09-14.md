# SS-Screen 真实 VASP + MACE 流程验证记录

日期：2026-09-14

本文件记录使用同事提供的 PBE VASP 带隙结果和 MACE 模型文件后，当前 SS-Screen 从本地结构到推荐报告的真实流程验证状态。

## 1. 输入材料

### 1.1 VASP 带隙结果

目录：

```text
data/CaS_CaSe_CaTe_PBE_final_bandgap_calculations
```

包含：

```text
CaS/vasprun.xml
CaSe/vasprun.xml
CaTe/vasprun.xml
calculation_manifest.json
README.txt
```

README 说明：

- PBE-relaxed structures
- `ENCUT=550 eV`
- `ISPIN=1`
- no SOC
- `SIGMA=0.03 eV`
- CaS/CaSe：`16x16x16` Gamma mesh
- CaTe：`32x32x32` Gamma mesh

### 1.2 MACE 模型

文件：

```text
data/mace-mpa-0-medium.model
```

本轮运行中记录的模型 SHA-256：

```text
75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638
```

### 1.3 最终采用的结构输入

最初尝试使用：

```text
data/CaS_CaSe_CaTe_POSCAR
```

该输入可以跑到 MACE relaxation，但 relaxation 质量控制发现体积缩放约为 1/4，导致 `usable_for_thermodynamics=False`，混合焓不可用。

因此正式验证改用 VASP 目录中的 PBE relaxed `CONTCAR`：

```text
data/CaS_CaSe_CaTe_PBE_final_bandgap_calculations/CaS/CONTCAR
data/CaS_CaSe_CaTe_PBE_final_bandgap_calculations/CaSe/CONTCAR
data/CaS_CaSe_CaTe_PBE_final_bandgap_calculations/CaTe/CONTCAR
```

## 2. 运行目录

最终有效运行目录：

```text
work/real-pbe-mace-20260914-run4
```

中间尝试目录：

```text
work/real-pbe-mace-20260914-run3
```

`run3` 使用初始 POSCAR，MACE relaxation 成功但热力学质量控制失败，因此不作为最终后段依据。

## 3. 已跑通阶段

| 阶段 | 命令/功能 | 状态 |
|---|---|---|
| Stage 01 | `dataset structures` 导入 PBE relaxed CONTCAR | 成功，3 条结构 |
| Stage 02 | `composition-screen` | 成功，3 条候选，1 个模板 |
| Stage 03 | `condense` / `condense-validate` | 成功，3 个结构描述，valid=3 |
| Stage 04 | `structure-match` | 成功，1 个结构组 |
| Stage 05 | `gap-export` | 成功，3 个 gap task |
| Stage 05a | `gap-collect-vasp` 解析 `vasprun.xml` | 成功，success=3 |
| Stage 05b | `gap-validate` 校验 vasprun 口径 | 成功，accepted=3 rejected=0 |
| Stage 05c | `gap-validate` 校验 manifest 口径 | 成功，accepted=3 rejected=0 |
| Stage 06 | `pair` | 成功，1 对：CaSe-CaTe |
| Stage 07 | `stability sqs-generate` | 成功，1 个 x=0.5 SQS |
| Stage 08 | `stability relax` 使用 MACE | 成功，SQS + 2 个端元均 usable |
| Stage 09 | `stability mixing-enthalpy` | 成功，1 条混合焓 |
| Stage 10 | `stability phonon-run` 使用 MACE/phonopy | 成功运行，判定 unstable |
| Stage 11 | `stability phase-diagram --mp-backend api` | 成功，MP API 竞争相 25 个，凸包判定 unstable |
| Stage 12 | `recommend` | 成功生成含真实 API hull 证据的推荐报告，结果 low-priority |

## 4. 带隙结果

### 4.1 程序直接解析 `vasprun.xml`

输出：

```text
work/real-pbe-mace-20260914-run4/05_gap/gap_results_vasprun_normalized.csv
```

| material | band gap (eV) | direct |
|---|---:|---|
| CaS | 1.3491 | True |
| CaSe | 0.7877 | True |
| CaTe | 0.0064 | False |

### 4.2 同事 manifest 口径

输出：

```text
work/real-pbe-mace-20260914-run4/05_gap/gap_results_manifest_normalized.csv
```

| material | band gap (eV) | direct | 备注 |
|---|---:|---|---|
| CaS | 1.3491 | True | 直接带隙 |
| CaSe | 0.7877 | True | 直接带隙 |
| CaTe | 0.0 | False | manifest 中 `signed_gap_eV=-0.0143`，按无正带隙处理 |

后续 pairing 和推荐采用 manifest 口径，因为它保留了同事对 CaTe 能带重叠的判定。

## 5. Pair 与 SQS

Pair 输出：

```text
work/real-pbe-mace-20260914-run4/06_pair/final_pairs_manifest.csv
```

得到 1 对：

| pair | gap_a | gap_b | direct_a | direct_b |
|---|---:|---:|---|---|
| CaSe-CaTe | 0.7877 | 0.0 | True | False |

SQS 输出：

```text
work/real-pbe-mace-20260914-run4/07_sqs/sqs_manifest.jsonl
```

本轮使用：

```text
supercell = 2,1,1
target_fraction_b = 0.5
backend = random
seed = 7
```

## 6. MACE Relaxation

命令环境：

```text
.venv-mlp
torch 2.5.1+cu121
CUDA available
MACE 0.3.14
```

关键参数：

```text
model-path = data/mace-mpa-0-medium.model
device = cuda:0
dtype = float32
fmax = 0.03
max_steps = 200
include_endmembers = true
```

输出：

```text
work/real-pbe-mace-20260914-run4/08_relax/relaxation_results.jsonl
```

结果：

| structure | status | usable | volume ratio | max force |
|---|---|---|---:|---:|
| SQS CaSe-CaTe | success | True | 1.1116 | 0.0123 eV/A |
| CaSe endmember | success | True | 0.9881 | 2.33e-7 eV/A |
| CaTe endmember | success | True | 0.9959 | 9.42e-8 eV/A |

## 7. Mixing Enthalpy

输出：

```text
work/real-pbe-mace-20260914-run4/09_mixing/mixing_enthalpy.csv
```

结果：

| pair | x(B) | mixing enthalpy | signal |
|---|---:|---:|---|
| CaSe-CaTe | 0.5 | 26.9009 meV/atom | endothermic |

默认推荐阈值中，promising 上限为 `25 meV/atom`。因此该结果属于 borderline 风险，而不是直接 promising。

## 8. Phonon

输出：

```text
work/real-pbe-mace-20260914-run4/10_phonon/phonon_summary.csv
```

本轮为快速真实验证，使用：

```text
supercell = 1,1,1
mesh = 6,6,6
band_points = 21
allow_loose_input = true
```

结果：

| structure | status | dynamical_status | min frequency |
|---|---|---|---:|
| SQS CaSe-CaTe | success | unstable | -1.3776 THz |

同时记录：

```text
significant_imaginary_mode_count = 92
imaginary_qpoint_count = 40
```

这说明当前 SQS/phonon 判据下存在明显动力学不稳定信号。该结论应优先用更大超胞、更严格声子设置或 DFT 进一步复核。

## 9. Phase Diagram / Convex Hull

此前离线模式失败原因：

```text
data/mp_offline.sqlite does not exist
```

2026-09-14 已单独检查当前项目中涉及 MP API 的位置：

- `src/ssscreen/data/mp.py`：Stage 01 `ss-screen dataset mp --backend api` 使用官方 `mp-api` 的 `MPRester()`，凭据来自标准 `MP_API_KEY` 环境变量或 mp-api 配置。
- `src/ssscreen/stability/competing.py`：Stage 10/11 竞争相和凸包在 `--mp-backend api` 时使用 `MPRester` 查询 Materials Project；Key 只在请求期间临时进入当前进程环境，结束后恢复。
- `src/ssscreen/cli/app.py`：`competing-export` 与 `phase-diagram` 在 API 后端会隐藏提示输入 Materials Project API Key，不把 Key 放进命令行参数。
- `src/ssscreen/gui/app.py`：右侧 Properties 的 `MP API Key` 只注入当前 GUI 启动的子进程环境；WSL 模式下临时 `export MP_API_KEY=...` 后执行命令，不写入项目文件或阶段输出。

`data/API Key.txt` 的检查结果：

- 文件存在，内容非空；文档中不记录、不展示具体 Key。
- 当前 `.venv` 中 `mp_api.client.MPRester` 可导入。
- 使用该 Key 做过最小 live 查询验证：`CaSe` summary 查询返回 2 条 Materials Project 文档，其中包含 `mp-1008223` 和 `mp-1415`。

Key 检查结论：

- 这个 MP API Key 可以用于当前项目的在线 MP 后端。
- 离线 `mp_offline` SQLite 数据库仍然缺失；如果需要完全离线、可复现的竞争相来源，仍需同事提供数据库。
- 已基于当前 `work/real-pbe-mace-20260914-run4/08_relax/relaxation_results.jsonl` 补跑 `stability phase-diagram --mp-backend api`，生成真实 convex hull 证据。

第一次 API 后端尝试使用默认超时，MP 查询 `Ca-Se-Te` 体系时发生 read timeout，输出保留在：

```text
work/real-pbe-mace-20260914-run4/11_phase_api
```

随后使用更长超时并指定单一 thermo 类型重跑成功：

```text
--mp-backend api
--thermo-type GGA_GGA+U
--api-timeout 180
--model-path data/mace-mpa-0-medium.model
--model-name mace-mpa-0-medium
--device cuda:0
--dtype float32
--fmax 0.03
--max-steps 200
--allow-incomplete
```

输出目录：

```text
work/real-pbe-mace-20260914-run4/11_phase_api_retry
```

结果：

| item | value |
|---|---:|
| candidate_count | 1 |
| fetched_entry_count | 25 |
| unique_entry_count | 25 |
| competing_manifest_count | 25 |
| competing_usable_count | 25 |
| competing_failed_count | 0 |
| competing_set_complete | True |
| MP database version | 2026.04.13 |
| hull distance | 0.3497941494 eV/atom |
| hull_signal | unstable |

候选相：

```text
structure_id = sqs-pair-00000-x-0.500000-fb17e0bb32c5
composition = Ca2TeSe
chemical_system = Ca-Se-Te
energy_above_hull_eV_per_atom = 0.3497941494
decomposition = 0.5 CaSe(mp-1415) + 0.5 CaTe(mp-1519)
```

## 10. Recommendation

输出：

```text
work/real-pbe-mace-20260914-run4/12_recommend/recommendations.csv
work/real-pbe-mace-20260914-run4/12_recommend/recommendation_report.md
work/real-pbe-mace-20260914-run4/12_recommend/recommendation_summary.json
```

补跑真实 MP API convex hull 后的推荐输出：

```text
work/real-pbe-mace-20260914-run4/12_recommend_api/recommendations.csv
work/real-pbe-mace-20260914-run4/12_recommend_api/recommendation_report.md
work/real-pbe-mace-20260914-run4/12_recommend_api/recommendation_summary.json
```

结果：

| pair | classification | evidence level | rationale |
|---|---|---|---|
| CaSe-CaTe | low-priority | L5 | phonon unstable; hull unstable |

推荐器记录：

- 正向证据：`gap:endpoints_verified:pbe-vasp-final-v1`
- 风险：`mixing:borderline`、`phonon:unstable`、`phonon:nac_not_applied`、`phase:above_low_priority_threshold`
- 缺失：`defects:not_requested`

## 11. 当前软件能力结论

现在已经能达到：

- 使用真实 VASP `vasprun.xml` 收集并校验外部带隙结果。
- 使用同事 manifest 口径生成并校验 gap CSV。
- 从 PBE relaxed `CONTCAR` 输入重新跑通前中段筛选。
- 使用同事提供的 MACE 模型在 GPU 上完成 SQS 与端元 relaxation。
- 基于真实 MACE relaxation 结果计算混合焓。
- 使用 MACE/phonopy 跑出真实声子谱筛查结果和图像文件。
- 使用 MP API 获取竞争相，并用同一 MACE 模型完成同能量基准 convex hull 计算。
- 生成 Stage 11 推荐报告。

当前仍不能完整真实运行：

- 缺陷计算与缺陷证据。

## 12. 给同事的下一步材料需求

优先级最高：

1. 如需离线和可复现运行，提供 `mp_offline` SQLite 数据库；当前 `data/API Key.txt` 已可用于在线 MP API 后端。
2. 对 CaSe-CaTe 的 phonon 虚频信号做复核：建议更大超胞、更严格 phonon 设置，必要时 DFT phonon 或更高精度验证。
3. 对 CaSe-CaTe 的 API convex hull 不稳定信号做复核：可用固定 `mp_offline` 快照或 DFT 竞争相能量进行更严格复验。
4. 如果同事有更多 composition / SQS / VASP 结果，按相同 manifest 方式提供，软件可以继续批量校验。

## 13. 科学边界

本轮结果是软件流程和材料筛查证据，不是最终材料结论。

尤其要注意：

- CaTe 的带隙口径存在 `vasprun.xml` 解析小正 gap 与 manifest signed gap 的差异，本轮推荐采用 manifest 口径。
- CaSe-CaTe 的混合焓略高于 promising 阈值。
- 声子谱出现明显虚频，因此当前推荐器给出 low-priority。
- MP API convex hull 已补跑成功，但候选 SQS 高于竞争相凸包约 `0.3498 eV/atom`，因此热力学稳定性证据同样不支持 promising。
