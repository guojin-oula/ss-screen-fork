# pair 筛选核心导航

真实目录：[`src/ssscreen/pair/`](../../src/ssscreen/pair/)

该目录保存项目的科学核心：把组成候选按局部结构环境归组，再结合外部高精度带隙结果枚举可合金化材料对。

## 文件职责

| 文件 | 主要职责 | 直接测试 |
|---|---|---|
| [`__init__.py`](../../src/ssscreen/pair/__init__.py) | pair 包入口 | 由模块测试间接覆盖 |
| [`grouping.py`](../../src/ssscreen/pair/grouping.py) | 二元/三元组成模板、候选筛选、附加 PBE gap | [`test_grouping.py`](../../tests/test_grouping.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`envmatch.py`](../../src/ssscreen/pair/envmatch.py) | `X` 占位元素替换、唯一局部环境提取、相似结构分组、`StructureGroup` | [`test_envmatch.py`](../../tests/test_envmatch.py) |
| [`filters.py`](../../src/ssscreen/pair/filters.py) | 价态可分配性、元素排除、gap 多样性和原子数门槛 | [`test_filters.py`](../../tests/test_filters.py) |
| [`structure_match.py`](../../src/ssscreen/pair/structure_match.py) | 把组成候选与 condensed JSON 结合，输出环境匹配分组和缺失/损坏统计 | [`test_structure_match.py`](../../tests/test_structure_match.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`gap_export.py`](../../src/ssscreen/pair/gap_export.py) | 导出版本化带隙任务、JSON/CIF/POSCAR 结构和结果/方法模板；严格校验外部返回结果并生成审计产物 | [`test_gap_export.py`](../../tests/test_gap_export.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`gap_collect_vasp.py`](../../src/ssscreen/pair/gap_collect_vasp.py) | 批量解析按task ID组织的 `vasprun.xml[.gz]`，为每项任务输出结果行，并生成逐任务错误、目录和四状态报告 | [`test_gap_collect_vasp.py`](../../tests/test_gap_collect_vasp.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`gap_feedback.py`](../../src/ssscreen/pair/gap_feedback.py) | 导入已校验的外部 gap 结果、保持未知 directness、统计覆盖率、配对和多方法比较 | [`test_gap_feedback.py`](../../tests/test_gap_feedback.py)、[`test_cli.py`](../../tests/test_cli.py) |
| [`pairing.py`](../../src/ssscreen/pair/pairing.py) | gap 有效性规则、成员压缩、无序材料对枚举和结果 DataFrame | [`test_pairing.py`](../../tests/test_pairing.py)、[`test_cli.py`](../../tests/test_cli.py) |

## 算法阅读顺序

1. [`config.py`](../../src/ssscreen/config.py)：先理解所有阈值。
2. [`grouping.py`](../../src/ssscreen/pair/grouping.py)：按化学计量模板生成候选。
3. [`envmatch.py`](../../src/ssscreen/pair/envmatch.py)：用 `X` 归一化变量位并匹配局部环境。
4. [`structure_match.py`](../../src/ssscreen/pair/structure_match.py)：把候选与 condensed 描述连接。
5. [`gap_export.py`](../../src/ssscreen/pair/gap_export.py)：生成确定性任务身份、多格式结构和外部返回模板。
6. [`gap_collect_vasp.py`](../../src/ssscreen/pair/gap_collect_vasp.py)：批量收集VASP结果，再由 `gap_export.py` 的校验器严格校验。
7. [`gap_feedback.py`](../../src/ssscreen/pair/gap_feedback.py) 与 [`pairing.py`](../../src/ssscreen/pair/pairing.py)：回填并枚举材料对。

## 科学说明

- [`docs/algorithm_structure_grouping.md`](../../docs/algorithm_structure_grouping.md)
- [`docs/algorithm_gap_backfill_pairing.md`](../../docs/algorithm_gap_backfill_pairing.md)
- [`references/pair-screening/README.md`](../../references/pair-screening/README.md)

## 当前注意事项

- 二元历史结果已精确复现 52 对。
- 三元算法在字段临时归一化后可精确复现 299 对，但历史 `Compositions` 字段别名仍需正式修复。
- README 中“直接带隙”表述与当前 directness 主要作为信息列的行为需要继续保持文档一致。
- 可选 PBE fallback 尚未实现。
- 高精度带隙执行不进入本包；AiiDA、VASP、ABACUS 等平台只需按任务/结果契约交换文件。

## 最近同步

- 2026-08-24：完善VASP批量结果收集器；支持方法元数据哈希、可选报告路径、逐任务错误和未知目录审计，缺失任务以 `missing` 行保留。
- 2026-07-31：完成外部高精度带隙契约，加入确定性任务/结构哈希、多格式结构、结果和方法模板、拒绝行与审计报告；重复结果不再静默覆盖。
- 2026-07-22：根据当前 8 个 pair 文件、算法文档和测试建立初始索引。
