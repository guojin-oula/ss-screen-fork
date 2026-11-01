# SS-Screen 完整功能版用户使用手册 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一套面向材料科研用户的中文完整功能版手册，包括可维护的 Markdown 源稿和经过逐页渲染检查的正式 Word 文档。

**Architecture:** `docs/user-guide/SS-Screen_完整功能版_用户使用手册.md` 是内容权威来源；`scripts/build_full_user_manual.py` 读取该源稿并确定性生成 `.docx`。当前命令从真实 CLI 核对，未来命令以醒目的“完整版本预期接口——当前代码尚未提供”标识呈现；所有昂贵计算都通过明确输入/输出文件契约与主流程连接。

**Tech Stack:** Markdown、Python 3.11、bundled `python-docx`、LibreOffice headless、Documents skill `render_docx.py`、PowerShell/WSL Git 检查。

---

## 文件结构

**新增：**

- `docs/user-guide/SS-Screen_完整功能版_用户使用手册.md`：完整中文内容源稿；
- `docs/user-guide/SS-Screen_完整功能版_用户使用手册.docx`：正式 Word 交付物；
- `scripts/build_full_user_manual.py`：Markdown 到 Word 的确定性构建器；
- `docs/superpowers/plans/2026-07-22-full-user-manual.md`：本实施计划。

**修改：**

- `ZMD/04_项目文档与开发计划/README.md`：登记正式手册和构建脚本；
- `ZMD/06_脚本与自动化/README.md`：登记 Word 构建脚本；
- `ZMD/07_版本与变更索引/README.md`：登记本次同步；
- `docs/PROJECT_LOG.md`：记录交付、边界和验证证据。

**不修改：**

- `src/ssscreen/` 和 `tests/`；
- 当前 CLI、科学算法和默认阈值；
- `references/` 历史资料。

根据 `AGENTS.md`，本次不创建 Git 提交，除非用户另行明确要求。

### Task 1: 固化真实接口证据

**Files:**
- Read: `src/ssscreen/cli/app.py`
- Read: `README.md`
- Read: `docs/PROJECT_PLAN.md`
- Read: `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md`
- Read: `docs/algorithm_structure_grouping.md`
- Read: `docs/algorithm_gap_backfill_pairing.md`

- [x] **Step 1: 激活并验证 WSL 环境**

Run:

```bash
cd /home/zuolong/projects/ss-screen-learning-20260722
source .venv/bin/activate
python --version
python -c "import ssscreen; print(ssscreen.__version__)"
```

Expected: Python 3.11，包版本输出 `0.1.0`。

- [x] **Step 2: 导出当前 CLI 帮助用于核对**

Run:

```bash
ss-screen --help
ss-screen dataset --help
ss-screen stability --help
```

Expected: 顶层、`dataset` 和 `stability` 命令组均成功返回帮助；命令名与 `ZMD/02_正式源码/cli.md` 一致。

- [x] **Step 3: 核对完整路线与当前边界**

检查：Stage 1-6 为当前主线，Stage 7-12 仍在规划；DFT/AiiDA 与缺陷模块在 `PROJECT_PLAN.md` 中仍为未来里程碑。任何尚未实现的命令只进入预期接口章节。

### Task 2: 编写 Markdown 权威源稿

**Files:**
- Create: `docs/user-guide/SS-Screen_完整功能版_用户使用手册.md`
- Reference: `docs/superpowers/specs/2026-07-22-full-user-manual-design.md`

- [x] **Step 1: 写入封面信息与状态图例**

包含软件全称、英文简称、文档版本、适用对象、文档性质、当前实现版本和以下图例：

```text
[当前可用] 已在 ss-screen 0.1.0 中实现并有测试覆盖
[完整版本预期接口] 完整产品的目标接口，当前代码尚未提供
[外部计算] 由 VASP/ABACUS/AiiDA/MLP/声子后端执行，结果按契约回收
```

- [x] **Step 2: 编写第一、二部分**

完整写出软件概述、科学目标、限制、工作流、系统要求、核心与可选安装、凭据、计算后端、项目目录和安装验证。不得出现真实密钥、个人路径或未公开数据。

- [x] **Step 3: 编写当前可用的 Stage 1-6**

逐阶段写出目的、输入、命令、关键参数、输出、检查、恢复和结果解释。命令必须来自真实 CLI；示例统一使用 `my-screening-project/` 相对路径。

- [x] **Step 4: 编写完整版本 Stage 7-14**

覆盖高精度托管计算、MLP 驰豫、混合焓、声子、相图、缺陷和推荐报告。每个命令前加入完整版本标识，并为每一阶段定义稳定的 CSV/JSON/JSONL/结构文件契约。

- [x] **Step 5: 编写结果解释与命令参考**

明确筛选证据等级、缺失数据原则、三档推荐、完整命令索引、核心文件字段、退出码、日志和断点续算。

- [x] **Step 6: 编写附录并自检**

包含完整示例、常见错误、术语、许可证和版本记录。运行：

```bash
rg -n 'TO''DO|TB''D|待补充|以后填写' docs/user-guide/SS-Screen_完整功能版_用户使用手册.md
```

Expected: 无匹配。手册中的“完整版本预期接口”是状态标签，不属于未完成占位。

### Task 3: 实现确定性的 Word 构建器

**Files:**
- Create: `scripts/build_full_user_manual.py`
- Read: `docs/user-guide/SS-Screen_完整功能版_用户使用手册.md`

- [x] **Step 1: 定义命令行和输入检查**

脚本接受：

```text
--input <markdown>
--output <docx>
--check
```

`--check` 验证必需章节、当前/预期状态标签、禁止占位词和输出文件非空；失败时返回非零退出码。

- [x] **Step 2: 定义 A4 科研手册样式令牌**

使用明确值：A4 纵向、上下 2.54 cm、左右 2.6 cm；正文中文字体 `Microsoft YaHei`/回退 `Noto Sans CJK SC` 10.5 pt；代码字体 `Consolas` 8.5 pt；标题 1/2/3 为 18/14/12 pt；正文 1.35 倍行距；深蓝主色、浅蓝表头、橙色预期接口提示框。

- [x] **Step 3: 实现 Markdown 块转换**

支持标题、正文、粗体/行内代码、无序/有序列表、引用提示、围栏代码块和 GitHub 风格表格。表格必须使用固定总宽度、重复表头、单元格内边距和跨页安全设置。

- [x] **Step 4: 实现正式文档部件**

生成封面、文档信息表、静态目录、页眉、页码、状态提示框、流程图式阶段表和版本说明。未来接口不得生成伪造成功截图，只使用“交互示意”标签。

- [x] **Step 5: 清理文档元数据**

作者、最后修改者和公司字段使用 `SS-Screen Project`，不得包含本机用户名；核心属性使用稳定标题、主题和关键词。

### Task 4: 生成并结构检查 Word 文档

**Files:**
- Create: `docs/user-guide/SS-Screen_完整功能版_用户使用手册.docx`

- [x] **Step 1: 使用 bundled Python 构建 DOCX**

Run from Windows with the workspace dependency Python:

```powershell
& 'C:\Users\19756\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  '\\wsl.localhost\Ubuntu\home\zuolong\projects\ss-screen-learning-20260722\scripts\build_full_user_manual.py' `
  --input '\\wsl.localhost\Ubuntu\home\zuolong\projects\ss-screen-learning-20260722\docs\user-guide\SS-Screen_完整功能版_用户使用手册.md' `
  --output '\\wsl.localhost\Ubuntu\home\zuolong\projects\ss-screen-learning-20260722\docs\user-guide\SS-Screen_完整功能版_用户使用手册.docx'
```

Expected: DOCX 存在且非空。

- [x] **Step 2: 执行构建器结构检查**

Run the same command with `--check`.

Expected: 输出标题数、表格数、代码块数和状态标签数；所有必需检查通过。

- [x] **Step 3: 执行隐私和结构审计**

使用 Documents skill 的 `privacy_scrub.py`、`heading_audit.py`、`section_audit.py` 和 `a11y_audit.py` 检查元数据、标题层级、A4 分节和表头。任何安全修复必须重新构建或写回最终 DOCX。

### Task 5: 渲染并逐页视觉检查

**Files:**
- Read: `docs/user-guide/SS-Screen_完整功能版_用户使用手册.docx`
- Temporary QA: Windows 临时目录中的 PNG/PDF，不交付

- [x] **Step 1: 渲染全部页面**

Run:

```powershell
& '<bundled-python>' '<documents-skill>\render_docx.py' `
  '<manual.docx>' --output_dir '<temporary-qa-dir>' --emit_pdf
```

Expected: 每页一个 `page-<N>.png`，并生成非空 PDF。

- [x] **Step 2: 逐页以原始分辨率检查**

检查每一页：中文字体、乱码、标题孤行、代码截断、表格越界、提示框拥挤、页眉页脚、页码、意外空白和章节分页。

- [x] **Step 3: 修复并重新渲染**

发现任何缺陷时修改 Markdown 或构建器，重新生成 DOCX 并重新渲染全部页面；最终一轮必须检查全部页面而不是只检查修改页。

### Task 6: 同步导航与完成验证

**Files:**
- Modify: `ZMD/04_项目文档与开发计划/README.md`
- Modify: `ZMD/06_脚本与自动化/README.md`
- Modify: `ZMD/07_版本与变更索引/README.md`
- Modify: `docs/PROJECT_LOG.md`

- [x] **Step 1: 更新 ZMD 路径和职责**

登记 Markdown、DOCX 和构建器真实路径；说明 Markdown 是内容权威来源、DOCX 是正式交付物、构建器用于确定性再生成。

- [x] **Step 2: 更新项目日志**

记录手册页数、章节数、当前/预期接口边界、渲染结果和未运行昂贵科学计算的事实。

- [x] **Step 3: 运行最终检查**

Run:

```bash
git diff --check
python -m pytest -q
ruff check .
```

Expected: diff 检查、97 项现有测试和 Ruff 均通过；文档构建未改变软件行为。

- [x] **Step 4: 检查 ZMD 本地链接**

验证新加入的 Markdown、DOCX、脚本和设计/计划链接均存在，不恢复或移动用户已有文件。

- [x] **Step 5: 交付**

最终只向用户链接 Markdown 与 Word 正式手册，不链接内部 PNG、PDF、临时构建文件或审计日志。
