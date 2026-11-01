# 第二部分算法说明 — 高精度带隙计算、回填与端元对枚举

> 本文档描述固溶体筛选 pipeline 的**第二部分**：对第一部分筛出的候选材料组合，
> 计算高精度带隙，回填进 structure group，再在 group 内枚举出「合金后能调谐带隙」的端元对。
> 配套文档见 [`algorithm_structure_grouping.md`](./algorithm_structure_grouping.md)（第一部分：成组）。
>
> 所有陈述均附源代码索引，见文末 §8。源代码位于只读目录 `../screen-mbj/`、`../pair-screening/`。

---

## 1. 目的与定位

第一部分用数据库自带的 **PBE 带隙**做廉价初筛，输出 structure group（一族族等结构、X 位可相互替换的材料）。但 PBE 系统性低估带隙（尤其半导体），不足以据此判断「合金后带隙能否落到可用区间」。因此第二部分对第一部分筛出的材料重算**高精度带隙**，再用它做最终的端元对选择。

### 为什么对带隙做范围筛选是合理的（方法论的根基）

这一步筛选面对一个本质困难：**DFT 算出的带隙必然带系统性误差，不可能与实验值完全一致**（PBE 系统性偏低，mBJ/HSE06 更准但仍有偏差）。但如果筛选目标是**固溶体**，这个困难就被化解了，原因在于：

> 固溶体是一个**组分连续可调的区间**，而非两个离散点。带隙随组分连续变化，因此 DFT 的系统性误差最终会被「吸收」成**组分上的平移误差**——也就是说，即便计算带隙整体偏了一个常数，我们仍然可以通过微调合金组分，把材料的真实带隙调到目标窗口里。

正因为材料组合是一个**范围（连续体）**，它天然具有对计算误差的容忍度。这也决定了我们要找的端元对形态：**一端带隙接近 0，另一端带隙较小（如 0~0.5 eV）**，这样合金后带隙才能在某个小区间（如 0~0.15 eV）内连续可调——只有具备这种「可调范围」的组合，才有可能通过组分调控去抵消计算误差、命中目标带隙。

这一动机贯穿整个 pipeline：第一部分找「等结构可替换」的 group（提供组分可调的物理前提），第二部分找「带隙跨度合适」的端元对（提供带隙可调的目标区间）。两者合一，才得到「既能合金、又能调到目标带隙」的候选。

**上述鲁棒性论证依赖两点近似（须显式承认）**：
1. **带隙随组分连续、单调性可接受（近似 Vegard 行为，bowing 有限）**。当合金出现强 bowing、带隙在组分区间内有极值/转折、或组分区间内发生结构相变/相分解时，「微调组分命中目标窗」不再成立。
2. **同一泛函对该 group 内各端元的系统偏差近似一致（可当常数平移）**。同一种泛函对不同化学体系（不同端元）的低估量差别可以很大（半导体与半金属尤其），因此「整体偏一个常数、靠组分平移抵消」只在该 group 内偏差缓变时才近似有效；当两端元误差方向/大小不一致时，鲁棒性下降。

也正因如此，§5 的端元对形态特意限定为「两端带隙都较小（如 0~0.5 eV）」——只有跨度小，平移抵消才在目标窗（如 0~0.15 eV）内有效。这两条假设是该筛选方法的适用边界，迁移与结果解读时须牢记。

### 关键定位：高精度方法是「筛子参数」，不是算法核心

第二部分中，**用哪种泛函（mBJ / VASP-HSE06 / ABACUS-HSE06）算带隙，本身不是算法核心**——它是一个**可替换的、可配置的输入**，作用等同于第一部分里的那些「可移动闸门」。换一种泛函只改变带隙数值的精度，不改变第二部分的算法骨架（计算 → 回填 → 枚举）。这一点和第一部分「两层 match 是唯一骨架，其余是闸门」的精神一致。

### 为什么必须先成组、再算高精度带隙

高精度带隙计算（杂化泛函 / mBJ）成本远高于 PBE。第一部分的价值就是把「哪些材料值得花这个预算」的集合压到最小（实测送算：binary 665 个、ternary 1588 个，其中成功算出带隙的子集更小，见 §4.3）。第一部分漏掉一个好 group = 永久错过；第二部分则是「在这个已压缩的集合上做精算 + 决策」。

---

## 2. 算法骨架（三步，顺序固定）

```
(a) 高精度带隙计算   →   (b) 回填进 group   →   (c) group 内枚举端元对
   (DFT, 贵)              (按 material_id)        (gap 判据, 近零端)
```

三步顺序固定，原因：(a) 产出 (b) 的输入；(b) 产出 (c) 的输入。三者缺一不可，且不可换序。

---

## 3. 步骤 (a)：高精度带隙计算

### 3.1 输入

第一部分生成的 mBJ 输入清单（`binary_mbj_calc_structures_*.json` / `ternary_mbj_calc_structures.json`）——即第一部分所有 group 成员的并集（去重），经 `natoms` 上限闸门砍过后，落盘的 primitive 结构字典。

### 3.2 计算方法（可配置）

当前工作区里实跑过**四条独立的高精度/基线 DFT 线**（按方法学预期成本递增；未附实测工时）：

| 方法 | 计算器/泛函 | 成本 | 作用于 | 证据 |
|---|---|---|---|---|
| **PBE** | VASP, `VaspBandUpdater`, `gga=None`/PBE | 低 | 二元（基线；数据库自带 PBE 亦可） | `screen-mbj/pbe-screen-binary.ipynb` Cell 10 |
| **mBJ**（真 meta-GGA） | VASP, `VaspHybridBandUpdater`, `metagga='mbj'` | 中 | **三元**（`hc-ternary-mbj`） | `screen-mbj/mbj-screen-ternery.ipynb` Cell 11 |
| **VASP HSE06** | VASP, `VaspHybridBandUpdater`, `hfscreen=0.2` | 高 | 二元（`hc-binary-mbj`） | `screen-mbj/hse-screen-binary.ipynb` Cell 10 |
| **ABACUS HSE06** | ABACUS, `AbacusBandWorkChain`, `dft_functional=hse`, 原子轨道基 | 中高（低于 VASP HSE06） | 二元（`hc-binary-hse-abacus`） | `screen-mbj/mbj-screen-binary.ipynb` Cell 11 |

**⚠️ 关键事实（迁移者必读）**：工作区里**二元与三元用了不同的高精度方法**，文档/文件名里的 "mbj" 在两套体系上含义不同：

- **二元** `mbj_gaps_binary_2025_0425_pmg_info.csv` 来自 **VASP HSE06**（`hse-screen-binary.ipynb`）；另外 `mbj-screen-binary.ipynb`（名字叫 mbj）实际跑的是 **ABACUS HSE06**。
- **三元** `mbj_gaps_tenary_2025_0425_pmg_info.csv` 来自 `mbj-analysis.ipynb` 读取 `hc-ternary-mbj`，而该组由 `mbj-screen-ternery.ipynb` 用**真正的 mBJ 泛函**（`metagga='mbj'`）填充——所以**三元这条线是货真价实的 mBJ (meta-GGA)**。

因此工作区实际上有三套独立的高精度方法在跑（二元 HSE06、二元 ABACUS-HSE06、三元 mBJ），不能笼统说成"全部用 HSE06"。迁移时：高精度方法必须做成**可配置输入**（mBJ / VASP-HSE06 / ABACUS-HSE06 任选），按体系分别指定，且**不应假设二元三元方法一致**。

### 3.3 计算流程（每条线通用）

每条 DFT 线都遵循相同模式（证据：四个 `*-screen-*.ipynb` 结构一致）：
1. 加载结构清单 → 存入 AiiDA `GroupPathX('hc-...')` 的 `structures` 子组。
2. 按位点数排序（`nodes.sort(key=lambda x: len(x.sites))`）。
3. 用 `callback` / `get_upd` 构造 process builder（封装泛函/基组/k 点/资源等参数）。
4. 用 `GroupLauncher(workpath, batch_size, callback, ...)` 批量提交，`launcher.launch_loop()` 分批跑。
5. **弛豫处理各线不同**：ABACUS HSE06 线含 **PBE cell-relax** 预弛豫（`mbj-screen-binary.ipynb` Cell 11 的 `builder.relax` 段，`dft_functional=pbe`, `calculation=cell-relax`）再算 HSE06 能带；VASP HSE06/mBJ 线建有 `VaspRelaxUpdater` 子链但 `perform=False`（仅取 IBZKPT，不实际优化晶格）。

### 3.4 带隙提取

对每个 `is_finished_ok` 的节点，用 pymatgen 重建带结构并取带隙：

```python
bs = get_pmg_bandstructure(node.outputs.band_structure, node.outputs.primitive_structure)
band_info = bs.get_band_gap()                    # 用 pymatgen 的，比 AiiDA 自带的更鲁棒
band_info['band_gap'] = band_info.pop('energy')  # 字段改名
out_dict = {'formula': ..., 'material_id': node.label.split()[?], **band_info}
```

> **迁移注意（两个 analysis notebook 不一致）**：`mbj-analysis.ipynb` Cell 8 用 `node.label.split()[1]`（label 格式为 `"<formula> <mp_id> ..."`）；而 `abacus-hse-analysis.ipynb` Cell 5 用 `node.label.split()[0]`（label 格式以 mp_id 开头）并额外记录 `uuid`。回填时依赖 mp_id 正确，迁移时须按实际 label 格式解析。

**产物**：CSV（`mbj_gaps_*_pmg_info.csv`），列为 `formula, material_id, direct, transition, band_gap`。`direct`（布尔）来自 pymatgen 的 `bs.get_band_gap()['direct']`，表示是否直接带隙。

### 3.5 正式软件边界：外部计算、内部契约与校验

`ss-screen` 不启动 VASP、ABACUS、AiiDA 或其他高精度带隙计算。正式软件负责导出任务和结构，用户在任意外部平台完成计算，再把结果交回软件统一校验和分析。这个边界使核心筛选不依赖许可证、集群、调度器、profile、赝势安装或特定工作流插件。

当前 `gap-export` 输出 `schema_version`、确定性 `task_id`、`material_id`、方法标识和 `structure_sha256`；结构可同时写成 pymatgen JSON、CIF 和 POSCAR，并可生成结果表及方法元数据 JSON 模板。任务 ID 由 schema 版本、材料 ID、方法标识和结构哈希确定，同一输入重复导出保持稳定。

当前 `gap-validate` 保留历史七列 CSV/JSON 兼容，同时在提供任务表时严格核对：

- 任务表自身的 schema 版本、ID 格式、结构哈希及确定性任务身份是否合法；
- 任务是否存在，材料 ID、化学式、方法和结构哈希是否一致；
- 成功带隙是否为有限非负 eV 数值；失败、未收敛和跳过行是否有明确状态；
- 结果是否重复，方法元数据及其设置哈希是否冲突；
- 缺失任务、各状态计数和拒绝原因。

校验输出分为规范化结果、拒绝行和 JSON 审计报告；报告区分完全未返回的任务和已返回但未获接受的任务。`is_direct` 未知时保留为空，不伪装成 `False`；不同高精度方法必须使用不同的稳定方法标识，不得静默混合。只有规范化结果进入回填、配对和多方法比较。

VASP批量结果可由 `gap-collect-vasp` 自动转换为上述稳定结果契约。收集器要求每个子目录以确定性 `task_id` 命名，并读取其中的 `vasprun.xml` 或 `vasprun.xml.gz`。默认处理任务表中的全部任务；`--task-id`仅用于单任务调试或选择性重试。可解析且收敛的任务写入带隙、directness和transition，未收敛、解析失败与缺少结果分别写成 `not_converged`、`failed` 和 `missing`，因此每个选中任务在结果CSV中恰有一行。收集报告保存四种状态的完整计数、逐任务解析错误、发现的子目录和未知目录。可选方法元数据会生成 `settings_sha256`，供后续 `gap-validate` 核对；收集器不启动VASP，也不替代最终身份与数值校验。

若外部平台是 AiiDA，SS-Screen 不读取 AiiDA profile、PostgreSQL/RabbitMQ、SSH、Computer、Code 或赝势路径。外部收集脚本只需原样传递 `task_id` 和 `structure_sha256`，填写标准结果字段，并可把 `aiida_process_uuid`、远端任务号或可追溯 URI 作为附加列；附加列会保留在规范化结果中，但不得包含凭据。

---

## 4. 步骤 (b)：回填进 structure group

### 4.1 输入

- 第一部分的 group 集合（`binary-group-df.json` / `ternary-group-df.json`）。
- 步骤 (a) 的高精度带隙 CSV。

### 4.2 回填逻辑与产物 schema 变化

`pairing_mbj_gaps_*.ipynb` Cell 1–4：构造 `{material_id: [band_gap, direct]}` 字典，遍历每个 group 的 `mp_ids`，按 ID 把高精度带隙贴到对应成员上：

```python
mbj_gap_dict = {row.material_id: [row.band_gap, row.direct] for _, row in df_gaps.iterrows()}  # Cell 3
for index, row in df_groups.iterrows():
    gaps_hse06 = [mbj_gap_dict.get(material_id) for material_id in row.mp_ids]   # 按 ID 回填
    is_valid = [x is not None for x in gaps_hse06]                               # 没算高精度的 → None
    outdict['gaps_mbj'] = [x for mask, x in zip(is_valid, gaps_hse06) if mask is True]  # 新字段，丢弃 None
    if len(outdict['mp_ids']) > 1:
        new_rows.append(outdict)
```

**⚠️ 回填不是「覆盖 band_gaps」，而是「新建 gaps_mbj + 重建 group」**（接口契约要点）：
- **新增字段 `gaps_mbj`**：值为 `[[band_gap, direct], ...]` 列表（与第一部分 `band_gaps` 的标量列表不同，这是二元组列表）。原来的 PBE `band_gaps` 字段**保留不动**。
- **成员集合缩小**：没有高精度带隙的成员被 `is_valid` 过滤掉（`outdict` 里所有等长列表都只保留有效成员），因此回填后的 group 成员数 ≤ 第一部分。
- **group 失效丢弃**：若回填后某 group 有效成员 ≤1（`len(outdict['mp_ids']) > 1` 不成立），整组丢弃。
- 回填产出的 DataFrame（`df_mbj`）是步骤 (c) 的输入，**不再写回第一部分的 JSON**。

### 4.3 ⚠️ 覆盖率问题（实测，文档须如实记录）

回填用 `.get(material_id)`，**没算高精度带隙的成员返回 `None`，随后被 `is_valid` 直接丢弃**。当前 group 成员对高精度带隙的覆盖率（实测）：

| 体系 | group 总成员（去重） | 送算结构数 | 高精度带隙覆盖（成功算出的子集） | 覆盖率 |
|---|---|---|---|---|
| binary | 680 | 665 | 286（VASP-HSE06, 2025-0425）/ 504（ABACUS-HSE06, 2025-0528） | 42% / 74% |
| ternary | 1646 | 1588 | 909（mBJ, 2025-0425；CSV 共 927 行，去重后与 group 交集 909） | 55% |

注意"送算"与"覆盖"是两个概念：送算 665/1588 是落盘进 mBJ 输入清单的结构数；覆盖 286/504/909 是其中**成功算出带隙并写进 CSV** 的子集（差额是计算未完成或失败）。两道损耗叠加，导致大量 group 成员被悄无声息地排除。**这是当前结果（binary 仅 52 对、ternary 仅 299 对）偏少的主要原因之一。** 迁移时应：(i) 把送算数、成功数、覆盖率分别作为可监控指标；(ii) 允许「PBE 兜底」（对没算高精度的成员用 PBE 带隙参与，而非直接丢弃），或明确标注哪些成员是 PBE 哪些是高精度。

### 4.4 三元的小修正

三元 group JSON 用了内联副本的字段命名（`Compositions` 大写），所以三元 pairing Cell 1 多一步重命名：

```python
df_groups = df_groups.rename({'Compositions': 'compositions'}, axis=1)
```

这是第一部分已知缺陷（内联副本 vs 模块版）的下游连锁。迁移统一字段命名后此步可去掉。

---

## 5. 步骤 (c)：group 内枚举端元对 + gap 判据

回填后，每个 group 的每个成员都带一个 `[band_gap, direct]`。本步在**每个 group 内部**枚举端元对，用 gap 判据挑出「合金后能调谐带隙」的对。

### 5.1 我们要找的端元对形态（判据的物理来源）

判据不是任意设的数字，而是来自 §1 的方法论根基——只有满足下面形态的对，才「既能合金、又能调到目标带隙」：

- **物理目标**：一端带隙接近 0（近零端），另一端带隙较小（如 0~0.5 eV，小带隙端），这样合金后带隙才能在某个小区间（如 0~0.15 eV）内**随组分连续变化**。

正是这个「连续可调范围」让我们能通过组分调控去抵消 DFT 的系统性误差、命中目标带隙（见 §1）。如果两端带隙都很大、或都近零，合金后带隙无法跨过目标窗口，组合就没有调谐价值。

> **物理目标窗口 vs 工程阈值（务必区分）**：上面的 0~0.5 eV / 0~0.15 eV 是**物理目标窗口**的举例，描述我们想要什么样的端元对；而下面 §5.2/§5.3 代码里出现的 0.15 / 1.5 / 0.2 / 0.3 / 0.8 是**工程阈值**，是上述物理目标的数值化实现。**组级（宽松）与 pair 级（严格）故意用了不同阈值**（组级用 0.15/1.5 先粗筛有调谐潜力的 group，pair 级用 0.2/0.3/0.8 再精选对）。两组数字不一一对应，是设计意图而非笔误。

下面的组级和 pair 级判据，都是对这一物理形态的工程化实现。

### 5.2 组级判据（gaps_valid，先筛 group）

`pairing_mbj_gaps_*.ipynb` Cell 6：对整个 group 做整体判断——group 内必须**同时存在近零带隙成员和小（中）带隙成员**，才有调谐空间：

```python
def gaps_valid(gaps):
    has_mid = any(0.15 < entry[0] < 1.5 for entry in gaps)   # 至少一个小/中等带隙端元
    has_low = any(entry[0] < 0.15 for entry in gaps)         # 至少一个近零端元
    return has_mid and has_low
```

> 代码中变量名写作 `has_direct`，但实际只用 gap 数值判断、未读 `direct` 标志位，**属命名误导**（迁移时应改名 `has_mid`）。注意原代码注释 `# There is a direct but small gap betweem 0.1 and 0.5` 的数字（0.1/0.5）也与实际代码（0.15/1.5）不符，迁移时一并修正。阈值（0.15、1.5）是可配置参数，见 §6。

### 5.3 pair 级枚举（在通过 5.2 的 group 内两两配对）

`pairing_mbj_gaps_*.ipynb` Cell 8：对 group 内所有成员两两组合 `(i, j)`，选出符合 §5.1 形态的对——**至少一端近零、至少一端进入小带隙区、且两端都不超出可调范围**：

```python
for i in range(len(row.compositions)):
    for j in range(i, len(row.compositions)):     # ⚠️ j 从 i 开始,会含自配对 (i,i),见下方注
        if any([mbj_gaps[i][0] < LOW_HI, mbj_gaps[j][0] < LOW_HI]) and \      # 至少一端近零
           any([mbj_gaps[i][0] > MID_LO, mbj_gaps[j][0] > MID_LO]) and \      # 至少一端进入小带隙区
           not any([mbj_gaps[i][0] > HI, mbj_gaps[j][0] > HI]):               # 两端都不超出可调范围
            ...记录 comp_a/comp_b/gap_a/gap_b/mp_id_a/mp_id_b/gap_direct_a/gap_direct_b...
```

**判据对应 §5.1 的形态**：
- `gap < LOW_HI`（近零端上限）：对应「一端带隙接近 0」；
- `gap > MID_LO`（小带隙端下限）：对应「另一端进入较小带隙区」；
- `gap < HI`（两端上限）：限定可调范围不超出目标窗口。

> ⚠️ **实现缺陷（迁移时修正）**：当前 `LOW_HI=0.3` 与 `MID_LO=0.2` 区间重叠（0.2–0.3），且判据用 `any(...)` 而非 `min(...)`/`max(...)`，因此**当某个端元带隙落在 0.2–0.3 时，它能同时满足"近零端"和"小带隙端"两条 any**，理论上可能选出「两端都不真正近零」的对——这与 §5.1「一端必须接近 0」的物理意图有出入。若迁移时希望严格保证「一端近零」，应改为 `min(gap_i, gap_j) < LOW_HI and max(gap_i, gap_j) > MID_LO` 的形式。当前实现属实验调参阶段的近似，阈值归入 `config.py` 的 `Thresholds` dataclass。
>
> ⚠️ **自配对 (i,i)**：`j in range(i, ...)` 含 `j==i`，会枚举自配对。当某成员带隙落在重叠区时自配对可能通过判据，产生「自己和自己合金」的退化对（当前代码靠 `if data['comp_a'] == data['comp_b']: continue` 兜底过滤同组分，但同 material_id 不同 comp 字符串的情况未必覆盖）。迁移时应明确是否允许 `i==j`，建议改为 `range(i+1, ...)`。

### 5.4 direct 的处理（信息列，非硬过滤）

`gap_direct_a` / `gap_direct_b` **作为信息列输出**，**不参与硬过滤**。证据：`pairing_mbj_gaps_*.ipynb` Cell 9 的 `pairs = pairs[pairs.gap_direct_a | pairs.gap_direct_b]` 是**注释掉的**。

> 设计说明（用户确认）：判据**只用带隙大小**，direct/indirect 作为后续参考数据。这避免在带隙判据之上再叠加可能过严的 direct 要求。迁移时保持这一行为——direct 是输出字段，不进判据。

**⚠️ 实测后果（迁移时须权衡）**：当前产物中，两端都是间接带隙的对占比很高：

| 体系 | 总对数 | 两端均 indirect | 至少一端 direct | 两端均 direct |
|---|---|---|---|---|
| binary | 52 | 28（**54%**） | 24 | 3 |
| ternary | 299 | 212（**71%**） | 87 | 10 |

也就是说，超过一半的候选对（三元高达 71%）两端都不是直接带隙。**如果下游目标是「直接带隙可调的固溶体」，当前输出里充斥对目标无意义的 indirect–indirect 对**。迁移时应重新决策：是保持现状（让用户在结果里自行筛 direct），还是把"至少一端 direct"或"两端 direct"做成可配置的硬过滤。另注：CSV 里的 `direct` 字段是字符串 `"True"/"False"` 而非布尔，若将来要进判据须先转 bool。

### 5.5 产物 schema

`mbj_result_*.csv`，每行一个端元对：

| 列 | 含义 |
|---|---|
| `comp_a`, `comp_b` | 两端元的化学式 |
| `gap_a`, `gap_b` | 两端元的高精度带隙 |
| `mp_id_a`, `mp_id_b` | 两端元的材料 ID |
| `gap_direct_a`, `gap_direct_b` | 两端元是否直接带隙（信息列，非判据） |

实测规模：binary 52 对、ternary 299 对。注意两者基于不同的高精度带隙源（binary 用 VASP-HSE06、ternary 用 mBJ，均覆盖率不足，见 §4.3/§7）。

---

## 6. 可配置参数（闸门）

第二部分的「筛子参数」集中在步骤 (a) 的方法选择和步骤 (c) 的阈值上，迁移时统一进 `config.py`：

| 参数 | 当前默认 | 位置 | 说明 |
|---|---|---|---|
| 高精度带隙方法 | VASP-HSE06 / ABACUS-HSE06 / mBJ | 步骤 (a) | **可替换**，算法不绑定具体泛函 |
| `gaps_valid` 近零端阈值 | `< 0.15 eV` | 步骤 (c).2 | group 必须含近零端元 |
| `gaps_valid` 小带隙端区间 | `0.15 ~ 1.5 eV` | 步骤 (c).2 | group 必须含小带隙端元 |
| pair `LOW_HI`（近零端上限） | `0.3 eV` | 步骤 (c).3 | pair 至少一端近零（对应 §5.1 近零端） |
| pair `MID_LO`（小带隙端下限） | `0.2 eV` | 步骤 (c).3 | pair 至少一端进入小带隙区（对应 §5.1 小带隙端） |
| pair `HI`（两端上限） | `0.8 eV` | 步骤 (c).3 | 两端都不超出可调范围 |
| direct 是否硬过滤 | 否（仅信息列） | 步骤 (c).4 | 用户确认 |

---

## 7. 当前 notebook 实际使用的带隙来源（如实记录）

两个 pairing notebook 的 Cell 1 都**硬编码**读取 `mbj_gaps_*_2025_0425_pmg_info.csv`，但**这两个 CSV 来自不同的高精度方法**（见 §3.2）：

| pairing notebook | 读取的 CSV | CSV 实际来源 | 覆盖率 |
|---|---|---|---|
| `pairing_mbj_gaps_binary.ipynb` | `mbj_gaps_binary_2025_0425_pmg_info.csv` | **VASP HSE06**（`hse-screen-binary.ipynb`） | 286/680 = 42% |
| `pairing_mbj_gaps_ternary.ipynb` | `mbj_gaps_tenary_2025_0425_pmg_info.csv` | **mBJ**（`mbj-screen-ternery.ipynb` 真用 `metagga='mbj'`） | 909/1646 = 55% |

此外二元还有一套**未被 pairing 采用**的更新数据 `abacus_hse_gaps_binary_2025_0528_pmg_info.csv`（ABACUS-HSE06，覆盖 504/680=74%）。历史演进：先算二元 VASP-HSE06（4月）和三元 mBJ（4月），后因 ABACUS-HSE06 成本更低补算二元一批（5月，覆盖更广），但 pairing notebook 没有切换到新数据。

- **迁移时**：高精度带隙方法应做成可配置输入（CLI 参数 / config），不硬编码文件名；二元/三元可分别指定方法；并补上覆盖率监控，避免成员被静默丢弃（见 §4.3）。

---

## 8. 源代码索引（证据）

| 概念 | 源文件 : 位置 |
|---|---|
| mBJ 输入清单（第一部分衔接） | `../screen-mbj/binary_mbj_calc_structures_2025_03_19.json`（665 结构）；`../screen-mbj/ternary_mbj_calc_structures.json`（1588 结构）；生成于 `../pair-screening/screening-binary.ipynb` Cell 41 / `screening-tenary.ipynb` Cell 32 |
| PBE 线启动（二元基线） | `../screen-mbj/pbe-screen-binary.ipynb` Cell 10（`VaspBandUpdater`, PBE） |
| VASP HSE06 线启动（二元） | `../screen-mbj/hse-screen-binary.ipynb` Cell 10（`VaspHybridBandUpdater`, `hfscreen=0.2`） |
| **mBJ 线启动（三元，真 meta-GGA）** | `../screen-mbj/mbj-screen-ternery.ipynb` Cell 11（`VaspHybridBandUpdater`, `metagga='mbj'`） |
| ABACUS HSE06 线启动（二元，含 PBE cell-relax） | `../screen-mbj/mbj-screen-binary.ipynb` Cell 11（`AbacusBandWorkChain`, `dft_functional=hse`） |
| 批量提交（GroupLauncher） | 各 `*-screen-*.ipynb` Cell 12–15 |
| 带隙提取（pymatgen bs.get_band_gap） | `../screen-mbj/mbj-analysis.ipynb` Cell 8（取 `label.split()[1]`）；`../screen-mbj/abacus-hse-analysis.ipynb` Cell 5（取 `label.split()[0]` + `uuid`） |
| 回填逻辑（按 material_id，新建 gaps_mbj） | `../pair-screening/pairing_mbj_gaps_binary.ipynb` Cell 3–4 |
| 三元字段重命名（内联副本连锁） | `../pair-screening/pairing_mbj_gaps_ternary.ipynb` Cell 1 |
| `gaps_valid` 组级判据 | `../pair-screening/pairing_mbj_gaps_binary.ipynb` Cell 6（三元 Cell 6 逐字相同） |
| pair 枚举 + 三阈值 | `../pair-screening/pairing_mbj_gaps_binary.ipynb` Cell 8（三元 Cell 8 逐字相同） |
| direct 过滤被注释（非硬过滤） | `../pair-screening/pairing_mbj_gaps_binary.ipynb` Cell 9 |
| 产物 CSV schema | `../pair-screening/mbj_result_binary_20250426.csv`（52 对）/ `mbj_result_ternary_20250426.csv`（299 对） |

### 已知缺陷 / 待办（迁移时处理）

- **"mBJ" 命名误导（分体系）**：二元 `mbj-screen-binary.ipynb` 实为 ABACUS HSE06、`mbj_gaps_binary` 来自 VASP HSE06；但三元 `mbj-screen-ternery.ipynb` 与 `mbj_gaps_tenary` 是**真 mBJ**。命名应澄清为实际方法名，且不要假设二元三元同方法。
- **pairing 硬编码 CSV**：读 `*_2025_0425`（二元 VASP-HSE06 覆盖 42%、三元 mBJ 覆盖 55%），二元未切到 `*_2025_0528`（ABACUS-HSE06 覆盖 74%）。应改为可配置输入。
- **回填静默丢弃**：`.get()` 返回 None 的成员被直接排除，导致覆盖率低 → 成对数偏少。应加覆盖率监控 + 可选 PBE 兜底。
- **`gaps_valid` 变量名误导**：`has_direct` 只用 gap 数值，未读 direct 标志位；原注释数字（0.1/0.5）也与代码（0.15/1.5）不符。变量应改名（如 `has_mid`），注释一并修正。
- **阈值重叠 + any 逻辑**：pair 级 `LOW_HI=0.3` 与 `MID_LO=0.2` 重叠，`any(...)` 形式可放过"两端都不近零"的对。迁移时改为 `min/max` 形式或归入 `Thresholds` dataclass。
- **自配对 (i,i)**：`j in range(i, ...)` 含自配对，建议改 `range(i+1, ...)`。
- **direct 字段类型**：CSV 中 `direct` 是字符串 `"True"/"False"` 非布尔，进判据前须转换。
- **三元 pairing 与二元逐字相同**，仅多一行字段重命名——逻辑统一后可合并为一个函数。
