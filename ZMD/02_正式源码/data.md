# data 数据层导航

真实目录：[`src/ssscreen/data/`](../../src/ssscreen/data/)

## 文件职责

| 文件 | 主要职责 | 直接测试 |
|---|---|---|
| [`__init__.py`](../../src/ssscreen/data/__init__.py) | 数据层包入口 | 由各数据测试间接覆盖 |
| [`mp.py`](../../src/ssscreen/data/mp.py) | 标准化 MP 文档；从 `mp_offline` 或 `mp_api` 加载；在线查询按稳定页码逐页重试；排除 deprecated；写出 DataFrame 和快照/query/request provenance | [`test_data_mp.py`](../../tests/test_data_mp.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`wbm.py`](../../src/ssscreen/data/wbm.py) | 从 WBM extxyz 读取结构并合并可选 summary；严格模式校验非空、行数、ID 唯一/对齐和 gap/hull 数值 | [`test_data_wbm.py`](../../tests/test_data_wbm.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`structures.py`](../../src/ssscreen/data/structures.py) | 递归读取本地 POSCAR/CIF/vasp/json 结构文件夹或单文件，生成 Stage 1 规范化 DataFrame，并可合并 metadata 中的 band gap/e_hull/source | [`test_data_structures.py`](../../tests/test_data_structures.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`condense.py`](../../src/ssscreen/data/condense.py) | 加载结构、调用 robocrys、原子写入逐材料 JSON、manifest/index、归档校验和失败记录 | [`test_condense_archive.py`](../../tests/test_condense_archive.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`io.py`](../../src/ssscreen/data/io.py) | `CondenseLoader`、StructureGroup JSON 读写、传统 mBJ gap CSV 读取和 pair CSV 写出 | [`test_cli.py`](../../tests/test_cli.py)、[`test_envmatch.py`](../../tests/test_envmatch.py) |

## 主要输入输出

| 阶段 | 输入 | 输出 |
|---|---|---|
| MP 数据 | 本地 `mp_offline` 数据库或 Materials Project API | 规范化 pickled DataFrame、`<output>.provenance.json` |
| WBM 数据 | extxyz，可选 summary CSV | 规范化 pickled DataFrame |
| 本地结构数据 | POSCAR/CIF/vasp/json 文件夹或单文件，可选 metadata CSV/TSV | 规范化 pickled DataFrame、可选 provenance JSON |
| Condense | 结构文件或含 `Structure` 的 DataFrame | `condensed/{material_id}.json`、manifest 和 index |
| Group I/O | records 或 pandas column-oriented JSON | `StructureGroup` 对象列表 |
| Legacy gaps | mBJ CSV | `{material_id: [gap, direct]}` 映射 |

## 能力边界

- WBM 当前只消费已经构建好的 extxyz；原始 step 数据到 extxyz 的完整重建尚未迁移。
- 本地结构数据入口只从 POSCAR/CIF 等文件获得结构；若无 metadata，band gap 和 e_hull 只能使用显式默认值，
  适合流程联调，不等同于真实 MP/WBM 数据证据。
- Web WBM StageRunner 强制使用严格模式；CLI 保持默认兼容模式，避免静默改变既有科研工作流。
- MP 在线后端依赖标准凭据发现，禁止在代码或 ZMD 中记录 API key。
- MP 在线全量结构查询按 `material_id` 稳定排序，每页500条、单请求超时120秒、失败页最多重试3次；这些操作设置进入 provenance，避免后续断流导致整批重下。
- MP 离线 Stage 1 只投影必需字段并显式排除 deprecated；sidecar 保存数据库 SHA-256、大小、样本文档 builder meta、查询边界和包版本，完整性范围只针对该快照。
- Web StageRunner 可向同一核心 loader 提供服务端 `database_reference`：此时 provenance 只保存稳定
  引用和 SHA-256，不写入服务器绝对路径；CLI 的显式本地路径行为保持不变。
- Condense 是可选 extra，运行前应确认 `robocrys` 和 `matminer` 可以导入。
- 历史三元 JSON 的大写 `Compositions` 兼容问题仍见[完整性审计](../../docs/review_upstream_completeness_2026-07-19.md)。

## 历史来源

- [`references/pair-screening/`](../../references/pair-screening/)
- [`references/mp-condense/`](../../references/mp-condense/)
- [`references/wbm-dataset/`](../../references/wbm-dataset/)

## 最近同步

- 2026-09-11：新增 `structures.py` 和 `dataset structures` 入口，用于把本地 POSCAR/CIF 文件夹规范化为
  Stage 1 DataFrame；已用 `data/CaS_CaSe_CaTe_POSCAR` 完成前中段 smoke。
- 2026-09-01：WBM loader 新增可选严格模式，拒绝空输入、summary 行数/ID 错位、重复材料 ID，
  以及缺失、非数值、非有限或负的 band gap/e_hull；Web 上传入口强制启用。
- 2026-09-01：为 Web MP 离线 StageRunner 增加可选 `database_reference`，保持核心算法不依赖 Web，
  并验证 provenance 不泄露服务端路径。
- 2026-08-28：Stage 1 在线 API 改为显式稳定分页和失败页重试；实际完成45,624条当前 MP 记录下载，数据库版本和请求设置进入 provenance。
- 2026-08-03：Stage 1 MP 离线读取接入经验证的外部 SQLite 快照；增加 deprecated 过滤、字段投影和默认 provenance sidecar。
- 2026-07-22：根据当前 data 模块、CLI 和测试建立初始索引。
