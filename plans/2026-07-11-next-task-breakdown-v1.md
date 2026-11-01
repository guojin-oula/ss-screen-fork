# 下一步任务拆分

## Objective

把当前 `ss-screen` 工作重新组织成两个并行交付物：中文技术文档项目，以及英文 CLI/package 程序项目。近期目标不是扩大功能面，而是先把项目范围、语言边界、文档骨架、测试缺口和 M2 数据层入口整理清楚，使后续实现能被 CI、用户指南和技术报告共同支撑。

依据：

- 当前状态记录为 M0/M1 已完成，`ss-screen pair` 已能复现实验 notebook 的 52 个 binary pairs；下一里程碑是 M2 数据层，另有 `pair` CLI 集成测试缺口，见 `docs/PROJECT_LOG.md:12`、`docs/PROJECT_LOG.md:14`、`docs/PROJECT_LOG.md:15`、`docs/PROJECT_LOG.md:107`、`docs/PROJECT_LOG.md:109`。
- 原计划中的目标包结构已经预留 `data/mp.py`、`data/wbm.py`、`data/condense.py`、CLI 子命令、测试和文档位置，见 `docs/PROJECT_PLAN.md:60`、`docs/PROJECT_PLAN.md:70`、`docs/PROJECT_PLAN.md:72`、`docs/PROJECT_PLAN.md:74`、`docs/PROJECT_PLAN.md:93`、`docs/PROJECT_PLAN.md:101`、`docs/PROJECT_PLAN.md:107`。
- 第一部分算法文档已经清楚描述 structure grouping 的中文技术材料基础，包括两层 match、robocrys 凝聚和输出 schema，见 `docs/algorithm_structure_grouping.md:10`、`docs/algorithm_structure_grouping.md:50`、`docs/algorithm_structure_grouping.md:76`、`docs/algorithm_structure_grouping.md:155`。
- 第二部分算法文档已经清楚描述 gap 计算、回填、pair enumeration、覆盖率和 direct 处理的中文技术材料基础，见 `docs/algorithm_gap_backfill_pairing.md:11`、`docs/algorithm_gap_backfill_pairing.md:41`、`docs/algorithm_gap_backfill_pairing.md:129`、`docs/algorithm_gap_backfill_pairing.md:203`、`docs/algorithm_gap_backfill_pairing.md:249`。

## Implementation Plan

- [ ] **整理项目范围与语言规范**：更新项目管理文档，把项目正式拆成两个 workstream：中文技术报告/中文用户指南，以及英文 CLI/package/CI。该任务应明确技术报告、用户指南、algorithm appendices、README、CLI help、docstring、测试和错误信息各自使用的主要语言，避免后续文档风格反复摇摆。影响文件主要是 `docs/PROJECT_PLAN.md` 和 `docs/PROJECT_LOG.md`。

- [ ] **建立中文技术报告主文档骨架**：新增或重构一份中文主报告，建议命名为 `docs/technical_report.md`。它不应简单复制两个 algorithm 文档，而应面向读者组织叙事：研究目标、筛选问题定义、总 pipeline、structure grouping、gap backfill、pair enumeration、参数含义、覆盖率问题、direct/indirect 解释、局限性和后续 DFT/defect 排序。现有 `algorithm_structure_grouping.md` 与 `algorithm_gap_backfill_pairing.md` 保留为详细附录和证据索引。

- [ ] **建立中文用户指南骨架**：新增 `docs/user_guide.md`，面向实际使用者解释如何安装、准备输入、运行 `ss-screen valence-filter`、`ss-screen group`、`ss-screen pair`，如何理解输出文件和常见失败。该文档要以中文为主，但命令名、参数名、文件格式字段保持英文原样，便于和 CLI 对齐。

- [ ] **修补 M1 的测试保护缺口**：为 `ss-screen pair` 添加一个小型 CLI 集成测试，使用提交在仓库内的 tiny group fixture 和 gaps CSV，覆盖 `attach_gaps_and_compress` 的等长列表压缩行为。这个任务优先级高，因为项目日志明确指出该行为曾由端到端真实数据测试捕获，但缺少轻量回归测试。影响文件主要是 `tests/`、`tests/data/`，必要时补充 README 或 user guide 中的 fixture 说明。

- [ ] **审计当前 CLI 与文档命名一致性**：检查现有 CLI 子命令名称、计划文档中的旧名称和用户指南拟写内容是否一致。当前代码已有 `valence-filter`、`group`、`pair` 三个命令，而旧计划中仍出现 `group-screen`、`pair-screen` 等名称；应选择一套稳定名称，并让 README、user guide、PROJECT_PLAN 与 CLI help 一致。

- [ ] **实施 M2 的最小数据层切片：condense**：先做 `data/condense.py` 和 `ss-screen condense`，因为 structure grouping 的运行依赖预先生成的 condensed JSON，而当前 M1 只能消费已有 `.df` 和 condensed 文件。该切片应支持单结构文件和批量目录，输出 `{material_id}.json`，统计成功、失败、跳过数量，并为 robocrys 缺失或凝聚失败提供清晰错误信息。

- [ ] **实施 M2 的数据读取切片：MP/WBM loader**：在 `condense` 稳定后，再移植 `data/mp.py` 和 `data/wbm.py`。这部分应外部化 MP API key 到 `MP_API_KEY`，对私有 `mp_offline` 做可选依赖处理，并把 WBM entry-to-summary matcher 独立成可测试 helper。这个任务的验收标准是能生成 `ss-screen group` 所需的 DataFrame schema，而不是一次性重跑全量数据库。

- [ ] **加入 CI 基线**：在程序侧补齐最小 CI 工作流，使 lint、format check 和 pytest 能在 clean checkout 上运行。CI 先覆盖 core package、CLI 轻量测试和文档链接/存在性检查；`condense`、AiiDA、DFT 相关依赖只做可选或跳过测试，避免把重依赖引入默认 CI。

- [ ] **补英文 README 的快速入口**：README 保持英文为主，作为包入口和 CI/开源风格说明；它应链接中文技术报告和中文用户指南，简短说明安装、核心命令、输入输出和 optional extras。详细科学解释不要塞进 README，避免和中文技术报告重复。

- [ ] **记录本轮范围澄清到项目日志**：在 `docs/PROJECT_LOG.md` 追加一条 2026-07-11 记录，说明项目被明确拆分为中文技术文档和英文 CLI/package 两个交付物，用户指南中文为主，程序接口英文为主，并列出下一步优先任务。

## Verification Criteria

- `docs/PROJECT_PLAN.md` 明确列出两个 workstream，并写清语言边界：技术报告和用户指南中文为主，CLI/API/CI/测试英文为主。
- `docs/technical_report.md` 存在，并能从现有两个 algorithm 文档自然引用到详细算法附录。
- `docs/user_guide.md` 存在，并至少覆盖当前已实现的 `valence-filter`、`group`、`pair` 三个命令。
- `ss-screen pair` 的 CLI 集成测试能在无全量数据、无 AiiDA、无 robocrys 运行环境下执行。
- M2 的第一个实现切片优先落在 `data/condense.py` 和 CLI command 上，并且不要求运行真实 DFT、notebook 或 AiiDA daemon。
- CI 默认路径只验证 core package，不强制安装 `[dft]` 重依赖。
- `docs/PROJECT_LOG.md` 新增条目记录本轮范围澄清和下一步安排。

## Potential Risks and Mitigations

1. **文档项目和程序项目互相打架**
   Mitigation: 把中文技术报告作为科学叙事来源，把英文 CLI/package 作为可执行接口；二者通过 input/output schema 和命令示例连接，不要求同一文档承担所有读者。

2. **技术报告过早追求完整，拖慢程序封装**
   Mitigation: 先写主报告骨架和关键章节摘要，把现有 algorithm 文档作为附录；完整结果讨论和图表可以后续迭代。

3. **M2 数据层依赖 robocrys、mp_api、私有 mp_offline，导致 CI 不稳定**
   Mitigation: 默认 CI 用 mock/tiny fixtures；真实 MP/WBM 下载和全量 condense 作为手动流程或 optional extra，不进入默认测试路径。

4. **历史命名中的 mBJ/HSE06 混乱继续进入用户接口**
   Mitigation: 用户文档和 CLI 参数统一使用 gap source / method 的真实含义；中文技术报告专门解释 binary/ternary 历史命名差异。

5. **direct/indirect 是否硬过滤尚未定论**
   Mitigation: 程序先保持当前行为，即 direct 是信息列；文档明确提醒当前结果中 indirect-indirect 比例较高，后续可作为可配置过滤项加入。

## Alternative Approaches

1. 先写完整中文技术报告，再继续任何程序工作：优点是科学叙事会最完整；缺点是当前 CLI 测试和 M2 数据层会停滞，CI 可复用目标推进较慢。

2. 先全力做 M2 程序功能，再补文档：优点是更快消除“只能消费预构建输入”的限制；缺点是刚刚明确的双项目边界和语言规范不能及时固化，后续文档债会变大。

3. 推荐路径：先用一次短任务固化项目范围、语言边界、文档骨架和 CLI 回归测试，再进入 M2 condense。这个路径能让中文报告和英文程序并行推进，同时给后续实现一个稳定的验收框架。
