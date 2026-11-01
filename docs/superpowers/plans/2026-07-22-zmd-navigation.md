# ZMD Workspace Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一个与真实工作区同步的 `ZMD/` 路径导航知识库，并把同步流程写入 `AGENTS.md`。

**Architecture:** ZMD 是只包含 Markdown 的索引层。一级目录按知识功能划分，页面通过仓库相对链接指向真实文件；根入口提供总地图，分区页面负责详细文件映射，变更索引记录同步状态。

**Tech Stack:** Markdown、Git 相对路径、PowerShell/WSL 只读扫描、项目现有 Python 3.11 环境。

---

### Task 1: 建立总入口和导航规则

**Files:**
- Create: `ZMD/README.md`
- Create: `ZMD/00_总览与使用规则/README.md`
- Create: `ZMD/00_总览与使用规则/工作区目录树.md`
- Create: `ZMD/00_总览与使用规则/文件资产总索引.md`
- Create: `ZMD/00_总览与使用规则/推荐阅读路径.md`
- Create: `ZMD/00_总览与使用规则/ZMD同步更新规则.md`

- [ ] 根据真实扫描结果写带注释的工作区树。
- [ ] 写按目标查找文件的入口表和推荐阅读路线。
- [ ] 写新增、删除、移动、重命名和内容更新的同步规则。
- [ ] 确认总入口不把 ZMD 描述为正式内容副本。

### Task 2: 建立源码、测试和工程文档映射

**Files:**
- Create: `ZMD/01_项目入口与配置/README.md`
- Create: `ZMD/02_正式源码/README.md`
- Create: `ZMD/02_正式源码/data.md`
- Create: `ZMD/02_正式源码/pair.md`
- Create: `ZMD/02_正式源码/stability.md`
- Create: `ZMD/02_正式源码/cli.md`
- Create: `ZMD/03_测试与测试数据/README.md`
- Create: `ZMD/04_项目文档与开发计划/README.md`

- [ ] 为每个正式源码文件登记职责、对应测试和相关文档。
- [ ] 为全部测试文件和夹具登记覆盖对象。
- [ ] 区分当前实现、设计计划和历史审计。

### Task 3: 建立历史资料、脚本和变更映射

**Files:**
- Create: `ZMD/05_历史科研资料/README.md`
- Create: `ZMD/06_脚本与自动化/README.md`
- Create: `ZMD/07_版本与变更索引/README.md`

- [ ] 索引每个 `references/` 研究家族及其 README/源码/notebook/修订目录。
- [ ] 索引参考资料清单生成脚本和 GitHub Actions。
- [ ] 记录 ZMD 初始同步日期、范围和后续登记格式。

### Task 4: 固化 AI 工作流程

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/PROJECT_LOG.md`

- [ ] 在 `AGENTS.md` 中要求环境激活后阅读 ZMD，并在真实文件变化后同步导航。
- [ ] 在项目日志顶部登记 ZMD 建立、设计决策和验证结果。
- [ ] 不创建 Git 提交；提交必须等待用户明确要求。

### Task 5: 验证

**Files:**
- Verify: `ZMD/**/*.md`
- Verify: `AGENTS.md`
- Verify: `docs/PROJECT_LOG.md`

- [ ] 对 ZMD 内所有本地 Markdown 链接进行存在性检查，预期失效链接为 0。
- [ ] 对照 `find` 输出核对导航目录树和资产索引。
- [ ] 运行 `git diff --check`，预期退出码 0。
- [ ] 在激活环境中运行 `python -m pytest -q -p no:cacheprovider`，预期全部通过。
- [ ] 运行 `ruff check src tests`，预期输出 `All checks passed!`。
- [ ] 核对 Git 修改范围，确保没有移动或删除现有内容。

