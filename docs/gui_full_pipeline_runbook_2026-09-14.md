# GUI 全流程演示操作单

日期：2026-09-14

目标：用 Windows 上的 PyCharm 启动 GUI，通过 WSL 后端跑通 CaS/CaSe/CaTe 小真实流程。默认参数已经调整为当前可用数据、MACE 模型和 MP API 后端。

## 1. 演示前准备

### 1.1 启动 GUI

在 PyCharm 中运行：

```text
D:\WorkSpace\OtherProjects\ss-screen\src\ssscreen\gui\app.py
```

GUI 打开后，确认当前工程是：

```text
D:\WorkSpace\OtherProjects\ss-screen
```

如果不是，点击顶部“打开工程”，选择该目录。

### 1.2 右侧 Properties 设置

前中段步骤使用：

```text
运行后端：WSL Python / .venv
WSL 工程路径：留空
```

从 MACE relaxation 开始切换为：

```text
运行后端：WSL Python / .venv-mlp
WSL 工程路径：留空
```

MP API Key：

```text
从 data/API Key.txt 复制到右侧 MP API Key 输入框
```

Key 只注入当前任务进程，不写入命令、日志或项目文件。

### 1.3 可选清理

如果想做一次干净演示，可以先删除工程根目录下旧的阶段输出目录：

```text
01_dataset
02_composition
03_condensed
04_groups
05_gap
06_pair
07_sqs
08_relax
09_mixing
10_phonon
11_phase
12_recommend
```

这些目录已在 `.gitignore` 中忽略。

## 2. 默认输入和已调整内容

GUI 默认本地结构输入已改为：

```text
data/CaS_CaSe_CaTe_PBE_relaxed_CONTCAR
```

该目录只包含从同事 VASP 结果中提取的 PBE relaxed `CONTCAR` 结构，避免直接递归扫描完整 VASP 结果目录时同时读到 `POSCAR` 和 `CONTCAR` 造成重复材料 ID。

VASP gap 收集默认读取已经整理好的 task-id 目录：

```text
work/real-pbe-mace-20260914-run4/05_gap/vasp_by_task_id
```

新默认导出的 3 个 `task_id` 已检查，和该目录中的 VASP 结果一一匹配。

MACE 默认模型：

```text
data/mace-mpa-0-medium.model
```

Stage 11 默认使用：

```text
--mp-backend api
```

## 3. GUI 点击顺序

### Step 01: 本地结构导入

左侧选择：

```text
01 数据源 -> Local POSCAR / 本地结构
```

保持默认值：

```text
结构文件夹：data/CaS_CaSe_CaTe_PBE_relaxed_CONTCAR
默认 band gap：0.0
默认 e_hull：0.0
数据源标签：pbe-vasp-relaxed
输出：01_dataset/local_structures.df
来源记录：01_dataset/local_structures.provenance.json
```

点击：

```text
导入本地结构
```

预期结果：生成 3 条结构记录。

### Step 02: 组成模板筛选

左侧选择：

```text
02 组成模板筛选
```

点击“检查输入”或“刷新参数”，确认 DataFrame 为：

```text
01_dataset/local_structures.df
```

保持默认筛选规则：

```text
元素数量：2
最大初筛带隙：1.0
最大凸包距离：0.01
模板最少材料数：2
模板最少可替换元素数：2
```

点击：

```text
开始组成模板筛选
```

预期结果：

```text
02_composition/composition_candidates.csv
02_composition/composition_summary.json
```

### Step 03: 结构描述归档

左侧选择：

```text
03 结构描述归档 -> 生成结构描述
```

保持默认值：

```text
DataFrame：01_dataset/local_structures.df
结构描述目录：03_condensed/local
Manifest：03_condensed/local_manifest.jsonl
Index：03_condensed/local_index.csv
```

点击：

```text
开始全量生成
```

完成后切换到同页的“归档状态 / Archive”页，保持默认：

```text
归档目录：03_condensed/local
校验输出：03_condensed/local_validation.csv
```

点击：

```text
校验归档
```

预期结果：`valid=3`。

### Step 04: 结构匹配与材料分组

左侧选择：

```text
04 结构匹配与材料分组 -> 执行结构匹配
```

保持默认值：

```text
组成候选表：02_composition/composition_candidates.csv
结构描述归档：03_condensed/local
最少可替换元素数：2
Structure Groups：04_groups/groups.json
阶段汇总：04_groups/structure_match_summary.json
```

点击：

```text
开始结构匹配
```

预期结果：生成 1 个结构组。

### Step 05: 导出 gap 任务

左侧选择：

```text
05 带隙交接 -> 导出高精度带隙任务
```

保持默认值：

```text
--groups：04_groups/groups.json
--dataset：01_dataset/local_structures.df
--method：pbe-vasp-final-v1
--structure-dir：05_gap/structures
--results-template：05_gap/results_template.csv
--method-metadata-template：05_gap/method_metadata.json
--output：05_gap/tasks.csv
```

点击：

```text
运行任务
```

预期结果：生成 3 个 gap task。

### Step 06: 收集 VASP gap

左侧选择：

```text
05 带隙交接 -> 收集 VASP 带隙结果
```

保持默认值：

```text
--tasks：05_gap/tasks.csv
--results-dir：work/real-pbe-mace-20260914-run4/05_gap/vasp_by_task_id
--method-metadata：05_gap/method_metadata.json
--output：05_gap/results_returned.csv
--report：05_gap/collection-report.json
```

点击：

```text
运行任务
```

预期结果：`success=3`。

### Step 07: 校验 gap 结果

左侧选择：

```text
05 带隙交接 -> 校验外部带隙结果
```

保持默认值：

```text
--gaps：05_gap/results_returned.csv
--tasks：05_gap/tasks.csv
--method-metadata：05_gap/method_metadata.json
--output：05_gap/results_normalized.csv
--rejected：05_gap/results_rejected.csv
--report：05_gap/validation.json
```

点击：

```text
运行任务
```

预期结果：`accepted=3 rejected=0`。

### Step 08: 生成端元对

左侧选择：

```text
06 端元配对 -> 生成端元对
```

保持默认值：

```text
--groups：04_groups/groups.json
--gap-results：05_gap/results_normalized.csv
--summary：06_pair/pair_summary.json
--output：06_pair/final_pairs.csv
```

点击：

```text
运行任务
```

预期结果：生成 1 对 CaSe-CaTe。

### Step 09: 生成 SQS

左侧选择：

```text
07 SQS 合金 -> 生成 SQS
```

保持默认值：

```text
--pairs：06_pair/final_pairs.csv
--dataset：01_dataset/local_structures.df
--target-fraction：0.5
--supercell：2,1,1
--backend：random
--seed：7
--output-dir：07_sqs/structures
--manifest：07_sqs/sqs_manifest.jsonl
```

点击：

```text
运行任务
```

## 4. 切换到 MLP/GPU 后端

从下一步开始，右侧 Properties 改为：

```text
运行后端：WSL Python / .venv-mlp
```

MP API Key 可以保持已填写状态。

### Step 10: MACE 结构驰豫

左侧选择：

```text
08 MACE 驰豫 -> MACE 结构驰豫
```

保持默认值：

```text
--manifest：07_sqs/sqs_manifest.jsonl
--include-endmembers：勾选
--model-path：data/mace-mpa-0-medium.model
--model-name：mace-mpa-0-medium
--device：cuda:0
--dtype：float32
--fmax：0.03
--max-steps：200
--relax-cell：默认
--output-dir：08_relax
--results：08_relax/relaxation_results.jsonl
```

点击：

```text
运行任务
```

预期结果：SQS、CaSe endpoint、CaTe endpoint 都成功 relaxation。

### Step 11: 混合焓

左侧选择：

```text
09 混合焓 -> 混合焓计算
```

保持默认值：

```text
--pairs：06_pair/final_pairs.csv
--relax-results：08_relax/relaxation_results.jsonl
--output：09_mixing/mixing_enthalpy.csv
--summary：09_mixing/mixing_summary.json
```

点击：

```text
运行任务
```

### Step 12: 声子谱一步式运行

左侧选择：

```text
10 声子谱 -> 声子谱一步式运行
```

保持默认值：

```text
--relax-results：08_relax/relaxation_results.jsonl
--supercell：1,1,1
--allow-loose-input：勾选
--mesh：6,6,6
--band-points：21
--model-path：data/mace-mpa-0-medium.model
--model-name：mace-mpa-0-medium
--device：cuda:0
--dtype：float32
--output-dir：10_phonon
```

点击：

```text
运行任务
```

该设置是快速演示设置，不是最终科研级声子收敛设置。

### Step 13: MP API 竞争相与凸包

左侧选择：

```text
11 竞争相 / 凸包 -> 竞争相与凸包一步式运行
```

确认右侧 Properties 已填写：

```text
MP API Key：来自 data/API Key.txt
运行后端：WSL Python / .venv-mlp
```

保持默认值：

```text
--relax-results：08_relax/relaxation_results.jsonl
--mp-backend：api
--thermo-type：GGA_GGA+U
--api-timeout：180
--model-path：data/mace-mpa-0-medium.model
--model-name：mace-mpa-0-medium
--device：cuda:0
--dtype：float32
--fmax：0.03
--max-steps：200
--allow-incomplete：勾选
--output-dir：11_phase
```

点击：

```text
运行任务
```

预期输出：

```text
11_phase/phase_stability.csv
11_phase/hull_entries.csv
11_phase/summary.json
```

若网络或 Materials Project 服务波动导致失败，保留日志；这一步可以单独重跑，不需要从 Stage 01 开始。

### Step 14: 综合推荐

左侧选择：

```text
12 综合推荐 -> 综合推荐
```

保持默认值：

```text
--pairs：06_pair/final_pairs.csv
--gap-results：05_gap/results_normalized.csv
--mixing-enthalpy：09_mixing/mixing_enthalpy.csv
--phonons：10_phonon/phonon_summary.csv
--phase-stability：11_phase/phase_stability.csv
--output：12_recommend/recommendations.csv
--report：12_recommend/recommendation_report.md
--summary：12_recommend/recommendation_summary.json
```

点击：

```text
运行任务
```

最终汇报时打开：

```text
12_recommend/recommendation_report.md
12_recommend/recommendations.csv
```

## 5. 汇报建议

可以这样介绍当前进度：

1. GUI 已经能从 Windows 调 WSL 后端，前中段用 `.venv`，MACE/phonon/phase 用 `.venv-mlp`。
2. 当前演示输入是同事给的 PBE relaxed VASP 结构和 VASP gap 结果，不是 mock 数据。
3. MACE 模型文件 `data/mace-mpa-0-medium.model` 已接入，SQS、MACE relaxation、混合焓和声子谱可以由 GUI 触发。
4. MP API Key 已验证可用，因此凸包阶段可以走在线 Materials Project 后端，不再把 `mp_offline` 作为当前演示阻塞项。
5. 当前 CaSe-CaTe 的科学结论仍要谨慎：此前真实运行中混合焓略高于 promising 阈值，声子有明显虚频；GUI 演示重点是流程打通和证据链可追踪。
