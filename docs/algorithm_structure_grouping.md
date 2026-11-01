# 第一部分算法说明 — 候选材料组合的构造（Structure Grouping）

> 本文档描述固溶体筛选 pipeline 的**第一部分**：从数据库中构造候选材料组合。
> 与之配套的「第二部分」（mBJ 高精度带隙计算 + 结果回填 + 端元对枚举）单独成文。
>
> 所有陈述均附源代码索引，见文末 §7。源代码位于只读目录 `../pair-screening/`、`../mp-condense/`。

---

## 1. 目的与成本动机

整个 pipeline 由两部分组成，分开的根本原因是 **mBJ 带隙计算成本高**：

| 部分 | 作用 | 成本 |
|---|---|---|
| **第一部分**（本文档） | 用廉价手段（robocrys 凝聚，秒级/结构）把数据库压缩成「**结构上可相互替换的材料组合**」 | 极低 |
| **第二部分** | 只对第一部分筛选出的材料集合算 mBJ，再把高精度带隙回填进组合，判断哪些是真正想要的 | 高 |

**第一部分的本质价值**：把「哪些材料值得花 mBJ 预算」这个集合压到最小，但不漏掉任何潜在有用的组合。压得越准，第二部分越省钱；而第一部分漏掉一个好组合 = 永久错过（因为它永远不会被送去算 mBJ）。

因此第一部分的设计原则是：**宁可松（保留更多候选），不可漏。**

### 全 pipeline 数据流总图（贯穿第一、第二部分）

```
condensed/*.json (robocrys 凝聚, 预计算)
        │
        ▼  ──────────── 第一部分（本文档）────────────
robocrys 凝聚 + 组分模板聚类  ──►  StructureGroup 集合
        │   (两层 match)           (binary/ternary-group-df.json)
        │                              │ band_gaps = PBE 值
        ▼                              ▼
        └──► ∪ group 的 mp_ids (去重) ──► natoms 闸门
                                          │
                                          ▼  ─── 第二部分（见配套文档）───
                                  mBJ 输入清单 JSON (665/1588 结构)
                                          │
                                          ▼  DFT (mBJ/HSE06, 贵)
                                  mbj_gaps_*.csv (带隙+direct)
                                          │
                                          ▼  按 material_id 回填进 group
                                  df_mbj (新增 gaps_mbj, 成员可能变少)
                                          │
                                          ▼  组级 + pair 级 gap 判据
                                  mbj_result_*.csv (端元对)
```

---

## 2. 核心算法：两层 match（不可省、不可换序的骨架）

第一部分的算法骨架只有两个动作，**缺一不可，顺序固定**：

1. **组分 match（初筛）**：从数据库中找到「在组分上能够替换」的一系列材料。
2. **结构 match（细筛）**：在这系列材料中，确认它们「在结构上是否也能替换」。

最终确认「结构上可相互替换」的材料集合，就是 **structure group**。每个 structure group 中，X 位（可替换位点）上可能有多个不同元素，因此天然包含**多对**潜在的固溶体端元组合。

### 2.1 第一层：组分 match（组分模板聚类）

**输入**：经过预过滤闸门的还原组成（reduced composition）集合。

**做法**：对每个组成，**枚举「哪个元素当可替换元素 X」**，其余元素当固定骨架（spectator / A 元素）。把骨架组成 + X 占位拼成一个**模板字符串**当作聚类 key。所有结构按模板 key 聚到一起。

- 二元 `AₓBᵧ`：X 可在第 1 位或第 2 位 → 产生 2 个模板。
- 三元 `AₓBᵧC_z`：X 可在 3 个位置之一 → 产生 3 个模板。

**成组条件**：同一个模板下，**至少有两种不同的 X 元素**（`len(value) > 1`）。否则这个模板无法形成「替换组合」。

**物理意义**：这是「化学式上把 X 换掉能对得上」的判断——**化学计量层面的必要筛**。化学式都对不上，结构必然不同；但化学式对得上，结构也未必相同（例如同为本征 AB，可能是岩盐也可能是闪锌矿）。

> 注（设计选择）：模板同时**钉死宿主元素的身份与化学计量**（不只是「同 AB 型」），这是比「仅同化学式型」更强一档的要求，与「等结构替代固溶体」的物理图像一致。三元模板用 `reduced_formula` 拼骨架（二元因骨架仅 1 元素，用 `str(Composition(...))` 等价）——见 §7 已知不一致。

> 证据：`screening-binary.ipynb` Cell 15（二元，2 模板）；`screening-tenary.ipynb` Cell 5（三元，3 模板）。详见 §7。

### 2.2 第二层：结构 match（局域环境指纹细分，envmatch）

**输入**：第一层得到的某个组分组 + 该组每个结构的 robocrystallographer 凝聚描述。

**做法**：在组分组内，对每个结构构造一个**局域环境指纹字符串**，再按指纹聚类。指纹构造的关键是：**把可变元素 X 的身份抹掉**，只保留结构拓扑——这样化学上不同、但结构原型相同的材料会塌缩成同一个指纹。

四个步骤：

1. **robocrys 凝聚**（预计算，离线批量）：对每个结构用 `StructureCondenser` 生成逐位点的配位多面体描述——位点取 `(poly_formula, geometry.type)` 二元组。
2. **环境提取**（`find_unique_envs`）：按元素归类，得到 `{元素: {(poly_formula, geometry.type), ...}}`。
3. **指纹构造**（`group_similar_structures`）：
   - 区分骨架元素（来自第一层的模板）和 X 元素（自动反推为「环境里唯一不在骨架列表中的那个」）。
   - 指纹 = `X 位点自身配位环境 | 各骨架位点的配位环境`。
   - 关键步骤：在骨架位点的环境描述里，**把出现的 X 元素统一改写成占位符 `X`**（`swap_elem_by_X`）。这使「X=Co 的结构」和「X=Ni 的结构」指纹可比。
4. **分组**：对指纹做去重聚类，`group_size > 1` 且**组内 X 元素种类 > 1** 才成有效组。

**物理意义**：这是「局域配位层面也能对得上」的判断——**比第一层更强的必要筛**。指纹相同意味着被替换元素在各自结构里的局域配位环境一致，但这**不等于**「真的能形成固溶体」——指纹只取 `(poly_formula, geometry.type)` 两个量，**不捕获**空间群、晶格常数/原子尺寸比（Hume-Rothery 判据）、同一 `geometry.type` 内的畸变、电子结构等。因此指纹相同是一个**近似「同原型」判据**，会容许少量假阳性（这正是 §1「宁可松不可漏」原则的体现——真正判定哪些组合有价值，留给第二部分的高精度带隙）。

> 证据：`envmatch.py` 第 8–108 行（`find_unique_envs` / `swap_elem_by_X` / `group_similar_structures`）。详见 §7。

### 2.3 两层是逐级必要筛，顺序固定

综合 §2.1/§2.2：第一层（组分 match）是化学计量层面的必要筛，第二层（环境 match）是局域配位层面更强的必要筛，两者合起来给出一个**近似的「同原型」判据**，而「同原型」本身只是实际可合金性的**必要非充分条件**。

- **只做组分 match**：会把「同化学式、不同结构原型」（如岩盐 AB 与闪锌矿 AB）误并成一组——第二层能把这类多形体分开（octahedral 与 tetrahedral 的 `geometry.type` 不同）。
- **只做结构 match**：本实现中，结构 match 的输入（谁是骨架、谁是 X）由组分模板提供（`group_similar_structures` 从 `comp_template` 反推 spectator），故必须先做组分 match。
- 所以顺序固定为 **组分 → 结构**。这是第一部分唯一的、不可调换的算法骨架。

> 注：两层的产物都是「候选集合的逐级压缩」，最终是否真正有用由第二部分判定。这与 §1 的成本动机（第一部分高召回、不漏；第二部分在压缩集上精算）一致。

---

## 3. envmatch 算法细节

### 3.1 robocrys 凝聚（数据来源）

对每个结构用 robocrystallographer 的 `StructureCondenser.condense_structure()` 生成凝聚描述字典，其中 `sites[site_id]` 含：
- `element`：位点元素（可能带氧化态后缀，如 `"Hf1.5+"`）
- `poly_formula`：连接性化学式
- `geometry.type`：配位多面体几何类型

凝聚描述在 MP/WBM 全量结构上离线批量生成，存为单文件 JSON（`mp-condense/condensed/*.json`、`wbm-dataset/condense/condensed/*.json`），运行时按材料 ID 按需加载。

### 3.2 环境提取 — `find_unique_envs`

逐位点取 `(poly_formula, geometry.type)` 二元组，按元素归类成集合。输出 `[[formula, {元素: {(pform, ptype), ...}}], ...]`（代码用列表 `[formula, env]` 而非元组）。

**注意（实现细节，迁移时必须保留）**：位点 `element` 字段可能形如 `"Hf1.5+"`（混合价态/分数占位），需先用正则 `re.match(r'[A-Z][a-z]?', elem).group(0)` 剥成元素符号再归类。三元 notebook 的内联副本漏掉了这步（见 §7 已知缺陷）。

### 3.3 指纹构造与 `swap_elem_by_X`

指纹字符串结构（`|` 分隔）：

```
<sorted X位点环境集合> | <骨架元素1名>,<其pform,ptype>,... | <骨架元素2名>,<其pform,ptype>,... | ...
```

其中骨架位点环境描述里出现的 X 元素被 `swap_elem_by_X` 改写成占位符 `X`。例如骨架为 O、X 在阳离子位变动（CoO→`O1X1` 中 O 位点的 `poly_formula` 由 `"OCo6"`→`"OX6"`，NiO 同理 `"ONi6"`→`"OX6"`），于是 CoO 与 NiO 产生**相同指纹**——只要两者的配位拓扑一致。

**这是整个算法的关键技巧**：抹掉可变元素的身份，让不同化学成分但等结构的原型塌缩到一起。

> **非对称性（实现细节）**：`swap_elem_by_X` 只作用于**骨架位点**的环境描述（把骨架看到的 X 改成占位符）；**X 位点自身**的环境（`item[elem]`）则保留骨架元素的真实符号不动（骨架符号在全组内本就不变，无需抹）。实现时不要对 X 位点也做替换。

### 3.4 分组与组级有效性判据

- 按指纹字符串做 `np.unique` 聚类。
- 成组条件：`group_size > 1`（同一指纹下 ≥2 个结构）。
- 组级有效性：组内 X 元素种类数 `> 1`（`len(np.unique(X_element)) > 1`）——确保同一结构骨架下确实有不同元素占据，才是真正的「等结构可替换组」，而非重复条目。**注意**：`group_size > 1` 判据在 `group_similar_structures` 内部（`envmatch.py` 第 98 行），而 `X 种类 > 1` 是 notebook 调用方的后置过滤（`screening-binary.ipynb` Cell 26 / `screening-tenary.ipynb` Cell 19 末行）。

### 3.5 边界条件与异常处理（迁移时补全）

当前 notebook 对异常情况的处理较粗，迁移成正式包时须显式处理：

- **robocrys 凝聚失败/字段缺失**：某些结构 `StructureCondenser.condense_structure()` 可能抛异常或返回缺字段。当前 `find_unique_envs` 对 `cs is None` 返回 `[None, None]` 并赋随机指纹（避免误匹配）；但其它异常（如缺 `geometry`/`poly_formula` 键）会直接抛。迁移时应捕获并记日志、决定是跳过该结构还是填默认。
- **X 元素反推歧义**：`group_similar_structures` 假设「环境里唯一不在骨架列表中的元素」就是 X（`assert len(x_candidiate) == 1`）。若某结构环境里出现 ≥2 个非骨架元素（理论上多 X 或数据噪声），会断言失败。迁移时应改为软处理（跳过 + 告警，或按组分模板拆分）。
- **缺失 condensed 数据**：`get_groups` 用 `condense_loader.get_condensed(idx)`，加载不到则该材料不参与分组（`if output is not None`）。当前是静默跳过，迁移时应统计缺失率。

---

## 4. 产物：StructureGroup schema

第一部分的输出是一组 `StructureGroup`，落盘为 JSON（`binary-group-df.json` / `ternary-group-df.json`）。这是第二部分的输入接口：

| 字段 | 类型 | 含义 |
|---|---|---|
| `A_elements` | list | 骨架元素（整组相同） |
| `X_element` | list | 每个成员的 X 元素（组内可不同，**种类数 > 1**） |
| `compositions` | list | 每个成员的化学式 |
| `mp_ids` | list | 每个成员的材料 ID（MP 或 WBM） |
| `band_gaps` | list | 每个成员的**PBE 带隙**（初筛时动态挂上，见下方注） |
| `group_size` | int | 成员数 |
| `group_repr` | str | 环境指纹（debug / 去重用） |
| `entry_idx` | list | 成员在原始数据集中的行索引（内部用） |

**等长列表对齐**：`X_element`、`compositions`、`mp_ids`、`band_gaps` 都是**等长列表**，按下标对齐。一个 group 描述「一类可替换材料」，X 位可能有 2 个元素，也可能有十几个——**不是成对结构**。成对枚举发生在第二部分（拿到高精度带隙之后）。

> **`band_gaps` 字段说明（迁移注意）**：它**不在 `StructureGroup` dataclass 声明里**（`envmatch.py:110-130` 只声明前 7 个字段），而是 notebook 运行时动态挂上的（`screening-binary.ipynb` Cell 26：`entry.band_gaps = [...]`；三元 Cell 19 同理），随后随序列化进入 JSON。值是 PBE 带隙（来自数据库），仅供第一部分后过滤用。
>
> **与第二部分的接口契约**：第二部分回填高精度带隙时，**不会覆盖 `band_gaps`**，而是**新建一个 `gaps_mbj` 字段**（值为 `[band_gap, direct]` 列表），同时**重建 group 只保留有高精度带隙的成员**（详见第二部分 §4）。因此「第一部分输出的 group」与「第二部分回填后的 group」在字段集合和成员集合上都不同——迁移时应区分这两套 schema（建议分别定义在 `_schema.py` 里）。

---

## 5. 可调压缩闸门（非核心，可移动）

以下过滤步骤**不属于算法骨架**，它们只是把送进 match 的集合变小，**放在算法链开头还是结尾、松还是紧，结果逻辑等价**。迁移时应统一成可配置参数（`config.py`），而非散落的硬编码字面量。

| 闸门 | 当前默认值 | 位置（当前代码） | 说明 |
|---|---|---|---|
| 稳定性 `e_hull` | `≤ 0` | 数据加载阶段 | 落在凸包上 |
| PBE 带隙上限 | `< 1 eV` | 数据加载阶段 | 排除宽间隙绝缘体 |
| 元素数 | 二元 `==2` / 三元 `==3` | 分支选择 | 选定处理哪类体系 |
| 价态过滤（BVAnalyzer） | 可分配氧化态才保留 | 数据加载阶段 | 剔除金属/混合价态；**可开关** |
| 元素排除清单 | 见下 | 环境分组之后 | 剔除放射性/磁性/过渡金属等 |
| **组级带隙多样性** | 二元 `any(x==0)`；三元 `any(x>0) and any(x==0)` | 环境分组之后 | 直接服务于「带隙可调」目标：组内须同时含零隙与非零隙成员。**二元/三元定义不一致**，三元更合理 |
| 原子数上限 `natoms` | 二元 `<30` / 三元 `<45` | **后置**（生成 mBJ 输入时） | 压缩的是「送进 DFT 的池」而非「送进 match 的池」，性质与上列前置闸门不同 |

**已知不一致（迁移时须统一，均不影响算法本质）**：
- 二元有价态过滤、有 `e_hull` 门槛；三元两者皆无。
- 元素排除清单：二元约 30 个（含 3d 过渡金属 Fe/Co/Ni/Mn、镧系、锕系），三元仅 5 个（U/Th/Po/Tl/Hg）。
- 组级带隙多样性判据：二元只要求「有零隙」，三元要求「既有零隙又有非零隙」（见上行闸门表）。
- 模板字符串构造：二元用 `str(Composition(...))`，三元用 `.reduced_formula`（骨架多元素时必须 reduced；二元单元素骨架两者等价）。
- 上述不一致只影响候选集合大小，不改变两层 match 的分组结果。

---

## 6. mBJ 输入清单的生成（第一部分到第二部分的衔接）

第一部分输出 group 后，**抽取所有 group 内材料的并集（去重）**，再用廉价闸门（`natoms` 上限）砍掉 DFT 太贵的，落盘成 mBJ 输入清单（JSON）：

```
group 集合 → ∪ 每个 group 的 mp_ids（set 去重）→ natoms 上限过滤 → mBJ 输入结构清单
```

实测送算规模（落盘进 JSON 的结构数）：二元 **665** 个、三元 **1588** 个（相对全库已大幅压缩）。注意这是"送算数"；其中成功算出高精度带隙的子集更小（见第二部分 §4.3 覆盖率表）。

> 证据：`screening-binary.ipynb` Cell 34 / 36 / 41；`screening-tenary.ipynb` Cell 27 / 29 / 32。

第二部分（mBJ 计算 + 回填 + pair 枚举）单独成文。

---

## 7. 源代码索引（证据）

| 概念 | 源文件 : 位置 |
|---|---|
| 组分模板聚类（二元） | `../pair-screening/screening-binary.ipynb` Cell 15 |
| 组分模板聚类（三元） | `../pair-screening/screening-tenary.ipynb` Cell 5 |
| 预过滤闸门（二元） | `../pair-screening/screening-binary.ipynb` Cell 12 |
| 预过滤闸门（三元） | `../pair-screening/screening-tenary.ipynb` Cell 3 |
| 价态过滤动机与实现 | `../pair-screening/valence-filter.ipynb` Cell 9, 11 |
| 环境提取 `find_unique_envs` | `../pair-screening/envmatch.py` 第 8–25 行 |
| 元素符号正则清洗 | `../pair-screening/envmatch.py` 第 21–22 行 |
| 占位替换 `swap_elem_by_X` | `../pair-screening/envmatch.py` 第 27–35 行 |
| 指纹构造与分组 `group_similar_structures` | `../pair-screening/envmatch.py` 第 37–108 行 |
| `StructureGroup` dataclass | `../pair-screening/envmatch.py` 第 110–133 行 |
| 环境分组调用（二元） | `../pair-screening/screening-binary.ipynb` Cell 26 |
| 环境分组调用（三元，内联副本） | `../pair-screening/screening-tenary.ipynb` Cell 17, 19 |
| 组级有效性（X 种类 > 1） | `../pair-screening/screening-binary.ipynb` Cell 26 末行；`screening-tenary.ipynb` Cell 19 末行 |
| 后过滤（元素排除 + 带隙多样性） | `../pair-screening/screening-binary.ipynb` Cell 29；`screening-tenary.ipynb` Cell 21–22 |
| mBJ 输入清单生成 | `../pair-screening/screening-binary.ipynb` Cell 34, 36, 41 |

### 已知缺陷（迁移时修复，记于 `PROJECT_LOG.md`）

- `envmatch.py:132` — `StructureGroup.__getitem___`（3 个尾下划线，拼错 dunder），索引协议失效。
- `screening-tenary.ipynb` Cell 17 — 内联了 envmatch 的副本（函数改名 `group_likestructures`、返回 dict 而非 dataclass、字段大写 `Compositions`、且漏掉 `re` 正则清洗）。**迁移以 `envmatch.py` 模块版为基准。**
- 二元/三元在价态过滤、`e_hull` 门槛、元素排除清单上不一致（见 §5）——属可调闸门，统一即可。
