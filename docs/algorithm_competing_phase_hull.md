# Stage 10 竞争相与同能量基准凸包

## 1. 目的与边界

Stage 10 判断已经完成 Stage 7 弛豫的 SQS 候选相，在同一化学体系的元素相和化合物竞争相面前处于什么能量位置。Materials Project API 或显式 `mp_offline` SQLite 快照只用于发现条目和取得结构；候选相与竞争相进入最终凸包的能量全部由同一个 MLP checkpoint、dtype 和完整弛豫设置重新计算。

该结果是 0 K MLIP 势能凸包预筛，不包含构型熵、振动自由能、非谐效应、有限温相变或动力学势垒，也不能替代 DFT 相图复核。

## 2. 分阶段契约

```text
Stage 7 relaxation_results.jsonl
  -> competing-export: MP API/离线快照条目、原胞结构、哈希和 manifest
  -> competing-relax: 同一 MACE 模型的竞争相弛豫结果
  -> convex-hull: candidate/competing 同源核验、分解组合和凸包距离
```

`phase-diagram` 是以上三步的一步式入口。大体系建议使用分阶段命令，以便在集群上分片弛豫和恢复失败任务。

## 3. Materials Project 查询

`--mp-backend api` 保留原在线流程。对每个候选 SQS 的完整化学体系调用 `MPRester.get_entries_in_chemsys()`；该接口同时返回父体系及所有子体系，查询使用显式 thermo scheme 和 MP `energy_above_hull` 窗口。每次在线命令都通过隐藏交互提示读取 API key，仅在请求期间放入当前进程环境，请求结束后恢复；网络失败写为 `query-failure-*`。

`--mp-backend offline --offline-db <path>` 使用 separately installed 的 `mp_offline` 包。实现从候选体系枚举全部非空元素子体系，以索引字段 `chemsys`、`energy_above_hull` 和 `deprecated` 查询 `MaterialSummary`，只投影材料 ID、组成和结构等必要字段，不把完整 SQLite 数据库载入内存。

离线 `MaterialSummary` 缓存没有在线 thermo-entry 的 `thermo_type` 过滤接口，因此离线 manifest 明确写入：

- `mp_source_backend=offline` 与 `mp_source_scope=offline_summary_snapshot`；
- 数据库 SHA-256、基于哈希的快照版本和本次读取时间；
- `mp_thermo_type_filter_applied=false` 和快照可能缺少更新条目的警告。

两种后端都只把 MP `energy_above_hull` 用作结构选择溯源，不进入最终 MLP 凸包。后端必须显式选择，不允许 API 失败后静默回退到离线库，也不应把不同快照的 manifest 混在一次凸包计算中。离线 `competing_set_complete=true` 只表示相对于记录的数据库快照没有导出/弛豫缺失，不证明最新 MP 数据中不存在新增竞争相。

## 4. 能量一致性

每条候选相和竞争相必须同时满足：

- `status=success` 且 `usable_for_thermodynamics=true`；
- 后端名称、版本、模型 SHA-256 和 dtype 一致；
- 优化器、cell mode、`fmax`、最大步数和全部结构 QC 设置一致；
- 总能和每原子能有限，输出结构存在且哈希匹配。

计算设备可以不同。任何 MP 结构跳过、MACE 未收敛、结果缺失或能量来源不兼容，都会使竞争集不完整。默认状态为 `incomplete_competing_set`，不报告可用于筛选的凸包值；只有显式 `--allow-incomplete` 才计算带 `uncertain_incomplete_competing_set` 标签的结果。

## 5. 凸包量

对候选条目 `target`，先用不含该候选的同源竞争条目建立 `PhaseDiagram`，再计算：

```text
energy_relative_to_competing_hull = E_target - E_decomposition
energy_above_hull = max(energy_relative_to_competing_hull, 0)
```

- 相对值小于负数值容差：候选降低当前竞争相凸包，`candidate_lowers_hull=true`；
- 相对值在数值容差内：`stable`；
- 正值但不超过 screening cutoff：`metastable_within_cutoff`；
- 超过 cutoff：`unstable`。

结果同时保存最优分解条目及分数。`hull_entries.csv` 使用加入候选后的凸包，列出参与本次比较的每个相及其 `e_above_hull`，便于审计竞争关系。

## 6. 输出与失败语义

| 产物 | 内容 |
|---|---|
| `competing_phases.jsonl` | MP entry ID、API/离线来源、数据库版本/SHA、thermo 适用性、父化学体系、结构路径/哈希和状态 |
| `competing_export_summary.json` | 查询体系、条目去重、失败、筛选阈值、快照范围或密钥不落盘声明 |
| `competing_relaxation_results.jsonl` | 与 Stage 7 一致的 MACE E/F/stress、收敛、QC 和运行指纹 |
| `phase_stability.csv` | 每个 SQS 的分解、相对凸包能、`e_above_hull`、信号、快照范围、完整性和来源 |
| `hull_entries.csv` | 每个候选对应的全部凸包条目和加入候选后的凸包距离 |
| `phase_stability_summary.json` | 状态计数、阈值、能量策略和科研边界 |

实现不会使用“竞争相 MACE 失败后回退到 MP DFT 能量”的参考脚本行为，因为这会把不同能量零点和理论层级混入同一凸包。

## 7. 历史来源

- `references/screen-antiperovskite/notebooks/satbility-mp.ipynb`：`ComputedStructureEntry`、`PhaseDiagram` 和 `get_e_above_hull` 的历史研究流程。
- 只读 `../solid-solutions-all/solid-solutions-mace/stability/stability_line_mace.py`：竞争相结构重算、化学体系缓存和批处理思路；其中 DFT 能量回退未移植。
- `src/ssscreen/stability/thermodynamics.py`：Stage 8 的同模型哈希和完整弛豫设置一致性契约。
