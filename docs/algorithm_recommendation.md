# Stage 11 综合推荐算法与文件契约

## 1. 目标与边界

Stage 11 将 Stage 5 的端元对和 Stage 8--10 的稳定性证据汇总为可审计的研究优先级。命令输出 `promising`、`uncertain` 或 `low-priority`，用于决定下一步 DFT、缺陷或实验投入，不用于宣称材料已经热力学稳定、可合成或具备器件性能。

算法不计算不透明的综合科学分数。每条结果保留正向证据、风险、缺失数据、来源警告、推荐理由和下一步建议，用户可以追溯分类依据。

## 2. 命令

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

缺陷结果是可选输入：

```bash
ss-screen recommend \
  ... \
  --defects 12_defects/defect_ranking.csv \
  --require-defects
```

未提供 `--defects` 时，输出会记录 `defects:not_requested`，但默认不会因此把完整的 L5 证据降为 `uncertain`。使用 `--require-defects` 后，缺失或失败的缺陷证据会成为不确定性来源。

## 3. 推荐单元与连接键

每条推荐对应一个 `pair_index + structure_id`：

- `pair_index` 是 `final_pairs.csv` 的零基行号；
- `structure_id` 是 Stage 6 以后同一 SQS 结构在混合焓、声子和相图表中的标识；
- 程序取 Stage 8--10 以及可选缺陷表中结构 ID 的并集，防止某一阶段缺失时整条候选被静默删除；
- 如果一个材料对没有任何下游结构记录，仍保留一条 `structure_id` 为空的 `uncertain` 记录。

同一阶段、同一推荐单元出现多条本应唯一的记录时，状态为不兼容，不会任意选择其中一条。

## 4. 输入契约

| 输入 | 必需字段 | 作用 |
|---|---|---|
| `final_pairs.csv` | `comp_a`、`comp_b`、`mp_id_a`、`mp_id_b` | Stage 5 端元对；可带 `gap_a/b`、directness 和 `gap_method` |
| `gap_results.normalized.csv` | `material_id`、`method`、`band_gap`、`is_direct`、`status` | 核对两个端元的高精度带隙来源和数值 |
| `mixing_enthalpy.csv` | `pair_index`、`sqs_structure_id`、`mixing_enthalpy_meV_per_atom`、`status`、`usable_for_screening` | Stage 8 混合焓与 MLP 来源 |
| `phonon_summary.csv` | `pair_index`、`structure_id`、`status`、`dynamical_status` | Stage 9 动力学预筛 |
| `phase_stability.csv` | `pair_index`、`structure_id`、`energy_above_hull_eV_per_atom`、`hull_signal`、`status`、`usable_for_screening` | Stage 10 同 MLP 竞争相凸包 |
| 可选缺陷 CSV | `pair_index`、`status`、`defect_signal`；可选 `structure_id` | L6 缺陷风险证据 |

缺陷信号允许 `favorable`、`neutral`、`low_risk`、`risky` 和 `uncertain`。未知信号被视为不兼容。缺陷表是 Stage 11 的消费契约；当前软件尚未提供缺陷计算命令。

## 5. 证据等级

证据等级只表示完成到哪一层，不表示结果一定正向：

| 等级 | 已完成证据 |
|---|---|
| `L2` | 已通过结构匹配并形成材料对 |
| `L3` | 两个端元的规范化高精度带隙完整且与 pair 表一致 |
| `L4` | L3，并有可用的同基准 SQS/MLP 混合焓 |
| `L5` | L4，并有完整声子结果和完整同 MLP 竞争相凸包 |
| `L6` | L5，并有成功且可解释的缺陷证据 |

例如，声子明确不稳定但其他证据完整的候选仍可以是 `L5`，同时分类为 `low-priority`。等级与推荐结论是两个不同维度。

## 6. 默认阈值

阈值集中在 `RecommendationSettings`，并可由 CLI 覆盖：

| 判据 | 正向范围 | 不确定范围 | 低优先级范围 |
|---|---:|---:|---:|
| 混合焓 | `<= 25 meV/atom` | `(25, 50] meV/atom` | `> 50 meV/atom` |
| 同 MLP 凸包距离 | `<= 0.025 eV/atom` | `(0.025, 0.1] eV/atom` | `> 0.1 eV/atom` 或 `hull_signal=unstable` |

端元带隙和 pair 表的一致性容差默认为 `1e-6 eV`。这些数值是可复现的初筛默认值，不是跨材料体系通用的物理常数。正式研究必须按化学体系、模型误差和研究目标校准。

## 7. 分类优先级

分类遵循以下顺序：

1. 出现明确负面信号时为 `low-priority`，包括显著虚频、高混合焓、高凸包距离或 `risky` 缺陷；
2. 没有明确负面信号，但核心证据缺失、失败、边界、歧义或不兼容时为 `uncertain`；
3. 核心 L5 证据完整且没有配置判据下的负面或不确定信号时为 `promising`。

Stage 8--10 记录的 MLP 模型 SHA-256 必须一致。模型不一致时，即使每个阶段单独成功，也分类为 `uncertain`。离线 MP 快照范围和未使用 NAC 会记录为风险，但不会单独改变分类，因为它们属于后续复核边界。

端元 direct/indirect 属性保持信息字段。两个端元都为间接带隙时会记录风险，但不作为硬过滤条件。

## 8. 排序

输出按以下确定性顺序排列：

1. `promising`、`uncertain`、`low-priority`；
2. 更高证据等级；
3. 更少风险和缺失项；
4. 更低混合焓；
5. 更低同 MLP 凸包距离；
6. `pair_index` 和 `structure_id`。

这一顺序用于报告阅读，不把不同量纲、不同可信度的证据压缩为一个总分。

## 9. 输出

- `recommendations.csv`：逐材料对、逐 SQS 的完整机器可读审计表；
- `recommendation_report.md`：排名表、逐候选理由、风险、缺失项和下一步；
- 可选 `recommendation_summary.json`：输入路径、分类/等级计数、阈值、排序政策和科学范围。

三类证据列表在 CSV 中使用 JSON 数组字符串保存，避免用不可解析的自由文本分隔符。输出文件采用原子替换写入，减少中断后留下半写文件的风险。

## 10. 科学解释

`promising` 的准确含义是“在当前文件中，Stage 3--10 必需证据完整，且未触发配置的低优先级信号，值得进一步验证”。它不等于：

- 已证明有限温热力学稳定；
- 已完成 SQS、组分、模型、声子或 DFT 收敛；
- 已证明可以实验合成；
- 已证明目标组分具有目标带隙；
- 已完成缺陷、载流子、界面或器件性能研究。

正式结论仍需要真实高精度带隙、多个组分和 SQS、收敛的声子与竞争相集合，以及一致设置的 DFT 或实验验证。
