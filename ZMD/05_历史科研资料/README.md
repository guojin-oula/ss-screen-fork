# 历史科研资料导航

真实目录：[`references/`](../../references/)

`references/` 保存经过筛选、带来源信息的历史 notebook 和源代码快照。它们用于理解算法来源、科研背景和未迁移工作流，不能作为当前运行时代码直接依赖。

## 总入口与清单

| 文件 | 作用 |
|---|---|
| [`references/README.md`](../../references/README.md) | 研究资料家族总览 |
| [`references/manifest.json`](../../references/manifest.json) | 原始路径、SHA-256、别名、脱敏、排除和许可/来源信息 |

初始清单记录：78 个存储产物、2 个脱敏 notebook、35 个字节相同别名、101 个明确排除项。

## 研究家族映射

| 研究家族 | 真实路径和入口 | 主要内容 | 与正式代码的关系 |
|---|---|---|---|
| Pair screening | [`references/pair-screening/README.md`](../../references/pair-screening/README.md) | MP/WBM 加载、价态过滤、二元/三元分组、mBJ gap 和配对 notebook；含 [`source/`](../../references/pair-screening/source/)、[`notebooks/`](../../references/pair-screening/notebooks/)、[`revisions/`](../../references/pair-screening/revisions/) | 主要迁移到 `data/` 和 `pair/` |
| MP condense | [`references/mp-condense/README.md`](../../references/mp-condense/README.md) | robocrys 单/批量 condensation、combined archive；含 [`source/`](../../references/mp-condense/source/) 和 [`revisions/`](../../references/mp-condense/revisions/) | 迁移到 `data/condense.py` |
| WBM dataset | [`references/wbm-dataset/README.md`](../../references/wbm-dataset/README.md) | 原始 step 数据匹配、extxyz 转换和 condensation helper；含 [`source/`](../../references/wbm-dataset/source/) | 当前只迁移 extxyz 消费，原始构建仍缺失 |
| Band screening | [`references/screen-mbj/README.md`](../../references/screen-mbj/README.md) | VASP/ABACUS PBE、HSE06、mBJ 启动、恢复、k-path、分析和导出；含 [`notebooks/`](../../references/screen-mbj/notebooks/) 和 [`revisions/`](../../references/screen-mbj/revisions/) | 当前仅由 gap 文件交接契约替代 |
| Promising materials | [`references/screen-promising/README.md`](../../references/screen-promising/README.md) | 候选材料 PBE/HSE band workflow、MP 结构获取和绘图；含 [`source/`](../../references/screen-promising/source/)、[`notebooks/`](../../references/screen-promising/notebooks/) 和 [`revisions/`](../../references/screen-promising/revisions/) | DFT launcher/analysis 未迁移 |
| Antiperovskite | [`references/screen-antiperovskite/README.md`](../../references/screen-antiperovskite/README.md) | 原型枚举、MACE 弛豫、mBJ/HSE 和 hull 分析；含 [`notebooks/`](../../references/screen-antiperovskite/notebooks/) 和 [`revisions/`](../../references/screen-antiperovskite/revisions/) | generic SQS 只覆盖很小一部分 |
| Simple defects | [`references/simple-defects/README.md`](../../references/simple-defects/README.md) | 元素参考、bulk/supercell、vacancy workchain、化学势、SQS vacancy 和排名；含 [`notebooks/`](../../references/simple-defects/notebooks/) 和 [`revisions/`](../../references/simple-defects/revisions/) | defects 模块尚未实现 |
| Historical baseline | [`references/old-screen-202411/README.md`](../../references/old-screen-202411/README.md) | 较早分组/配对阈值、direct-gap 行为和示例 notebook | 大部分被当前核心替代，保留历史对照 |
| Rocksalt prototypes | [`references/prototypes/rocksalt/README.md`](../../references/prototypes/rocksalt/README.md) | rocksalt builder、HSE/mBJ/SOC、PbSe-Te SQS | generic SQS 部分迁移，其余未迁移 |
| Zincblende prototypes | [`references/prototypes/zincblend/README.md`](../../references/prototypes/zincblend/README.md) | zincblende builder、HSE/mBJ/SOC、ABACUS 提交知识 | 未迁移 |
| Chalcopyrite prototypes | [`references/prototypes/chalcopyrite/README.md`](../../references/prototypes/chalcopyrite/README.md) | CdSnSb2 PBE/HSE/mBJ/SOC 和 band plot | 未迁移 |

## 安全与使用规则

- 不直接执行历史 notebook、DFT 作业或 AiiDA daemon，除非用户明确要求。
- 不把参考源码直接 import 到正式包。
- 移植逻辑时注明来源 notebook/文件和 cell。
- 先阅读家族 README，再决定是否需要打开大型 notebook。
- 发现秘密或历史凭据时不得复制到代码、ZMD 或输出；应报告并建议撤销/轮换。
- `manifest.json` 是资料来源和完整性校验的权威机器可读记录。

## 推荐追溯路径

```text
ZMD 家族说明
  → references/<family>/README.md
  → source/ 或 notebooks/
  → revisions/（仅在需要历史差异时）
  → 当前 src/ 实现
  → 当前 tests/ 行为证据
```

## 最近同步

- 2026-07-22：依据 `references/README.md`、manifest 和真实目录建立 11 个研究家族的初始导航。

