# stability 稳定性输入导航

真实目录：[`src/ssscreen/stability/`](../../src/ssscreen/stability/)

## 文件职责

| 文件 | 主要职责 | 直接测试 |
|---|---|---|
| [`__init__.py`](../../src/ssscreen/stability/__init__.py) | SQS/MLP/混合焓/声子/凸包/推荐公共入口 | 模块测试间接覆盖 |
| [`sqs.py`](../../src/ssscreen/stability/sqs.py) | 推断单一替换位、生成随机或 icet SQS、写出端元/合金结构和带哈希 manifest | [`test_stability_sqs.py`](../../tests/test_stability_sqs.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`mlp.py`](../../src/ssscreen/stability/mlp.py) | 后端协议、MACE 模型单次加载、ASE FIRE 弛豫与固定结构能量/力/应力 | [`test_stability_relax.py`](../../tests/test_stability_relax.py)、[`test_stability_phonon.py`](../../tests/test_stability_phonon.py)、显式真实模型冒烟 |
| [`relax.py`](../../src/ssscreen/stability/relax.py) | manifest 任务展开、端元去重、指纹续跑、原子写入、完整能量/力/应力和质量检查结果 | [`test_stability_relax.py`](../../tests/test_stability_relax.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`thermodynamics.py`](../../src/ssscreen/stability/thermodynamics.py) | SQS/端元能量匹配、来源一致性校验、实际组分混合焓和失败审计汇总 | [`test_stability_thermodynamics.py`](../../tests/test_stability_thermodynamics.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`phonon.py`](../../src/ssscreen/stability/phonon.py) | Phonopy 位移任务、MACE 能量/力续算、力常数、网格、频带、DOS、图和动力学状态 | [`test_stability_phonon.py`](../../tests/test_stability_phonon.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`competing.py`](../../src/ssscreen/stability/competing.py) | MP API/离线快照竞争相查询、密钥/快照 provenance、结构 manifest、同 MACE 弛豫、凸包分解和完整性审计 | [`test_stability_competing.py`](../../tests/test_stability_competing.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`recommendation.py`](../../src/ssscreen/stability/recommendation.py) | 按 pair/SQS 连接 Stage 5、8--10 和可选缺陷证据，给出 L2--L6、三类推荐、确定性排名与审计报告 | [`test_stability_recommendation.py`](../../tests/test_stability_recommendation.py)、[`test_cli.py`](../../tests/test_cli.py) |

## CLI 入口

```bash
ss-screen stability sqs-generate --help
ss-screen stability relax --help
ss-screen stability mixing-enthalpy --help
ss-screen stability phonon-export --help
ss-screen stability phonon-forces --help
ss-screen stability phonon-collect --help
ss-screen stability phonon-run --help
ss-screen stability competing-export --help
ss-screen stability competing-relax --help
ss-screen stability convex-hull --help
ss-screen stability phase-diagram --help
ss-screen recommend --help
```

命令定义位于 [`src/ssscreen/cli/app.py`](../../src/ssscreen/cli/app.py)，需要 `final_pairs.csv` 和包含端元结构的规范化 DataFrame。

## 当前能力边界

- `random` 后端依赖较轻，按目标比例随机替换。
- `icet` 后端使用 cluster space 和 Monte Carlo 优化。
- Stage 6 同时写出 SQS 与端元结构路径/哈希，为同模型能量基准提供输入。
- Stage 7 首个正式后端为 MACE；可执行全晶胞或仅原子位置 FIRE 弛豫。
- 每条结果保存模型/输入/设置指纹、弛豫结构、总能/每原子能、完整力数组、`3×3` 应力、实际步数、收敛状态和结构质量检查。
- `success`、`not_converged`、`failed` 明确分离；未收敛结果不可用于后续热力学。
- Stage 8 按实际 SQS 组分计算每原子混合焓；旧记录缺失实际组分时允许带警告回退到目标组分。
- 混合焓只接受后端名称/版本、模型哈希、精度和全部驰豫设置一致的三条能量；设备允许不同。
- 每个 SQS 都写出成功或明确失败状态，缺失/不可用/来源不兼容/端元歧义不会静默丢弃。
- Stage 9 以 Phonopy 4.x 生成有限位移，由相同 checkpoint 的 MACE 记录固定结构总能、完整力和应力；任务可分阶段或一步式运行并按指纹续算。
- 收集阶段要求完整同模型力，默认扣除参考超胞残余力并对称化力常数；Gamma-centered q 网格负责虚频判据，高对称路径用于频带/DOS 图。
- `stable` 只表示在所用谐波 MLIP、超胞、网格和虚频容差下未检测到显著虚频；当前不含 NAC、非谐或有限温自由能。
- Stage 10 在线命令每次隐藏提示 Materials Project API key；密钥仅临时进入当前进程环境并在请求后恢复，不写入产物。
- Stage 10 离线命令要求显式 `--offline-db`，枚举全部非空子体系并查询 `mp_offline` 索引；不提示或读取 API key。
- 离线 manifest 和最终凸包结果保存数据库 SHA-256、快照 scope 和警告；完整性只相对于该快照，不能冒充在线 thermo-type 查询。
- MP API 返回父化学体系及所有子体系结构；MP 能量只作为结构选择溯源，最终凸包只接受与候选相完全兼容的 MLP 能量基准。
- `competing-export`/`competing-relax`/`convex-hull` 支持分阶段恢复，`phase-diagram` 提供一步式 MACE 流程；查询超时、结构过大、未收敛、缺失和来源不兼容均保留状态。
- 默认竞争集必须完整，禁止 MACE 失败后回退到 MP DFT 能量；`--allow-incomplete` 只生成明确 uncertain 的诊断结果。
- Stage 11 保留缺失/失败/不兼容证据，核对 Stage 8--10 模型 SHA，并按明确负面、核心不确定性和完整正向证据依次给出 `low-priority`、`uncertain`、`promising`。
- L2--L6 只描述证据完整度；排序不使用不透明总分，directness、离线快照范围和未使用 NAC 作为可见风险保留。
- 缺陷表默认可选；`--require-defects` 才把它设为强制证据。当前尚未实现缺陷计算命令，也未接入 MatterSim/eSEN/TorchSim 批处理后端。

## 历史来源

- [`references/prototypes/rocksalt/`](../../references/prototypes/rocksalt/)
- [`references/screen-antiperovskite/`](../../references/screen-antiperovskite/)
- [`references/simple-defects/`](../../references/simple-defects/)

## 最近同步

- 2026-09-18：`PhononSettings.max_input_force` 默认值由 `0.01` 调整为 `0.02 eV/Angstrom`；CLI 与 GUI
  的声子任务统一继承该默认值。
- 2026-08-03：新增 Stage 11 综合推荐模块和顶层命令，输出逐 SQS CSV、Markdown 报告和可选 JSON summary。
- 2026-08-01：Stage 10 增加显式 `mp_offline` provider，API/离线 manifest 契约统一且来源贯穿最终凸包结果。
- 2026-07-31：新增 Stage 10 四个竞争相/凸包命令、MP API 结构导出、统一 MACE 能量核验和严格失败语义。
- 2026-07-31：新增 Stage 9 四个声子命令、MACE 单点能量/力、可恢复任务和完整频谱/QC 产物。
- 2026-07-30：新增 Stage 8 `mixing-enthalpy`、实际组分追踪、同能量基准校验和逐 SQS 审计输出。
- 2026-07-30：接入 MACE-MPA-0 Stage 7 弛豫、端元 manifest、完整 E/F/stress 结果和断点续跑。
- 2026-07-22：根据当前 SQS 实现、CLI 和测试建立初始索引。
