# SS-Screen Web 平台实施交接任务书

**用途：** 交给新的 Codex 窗口直接执行  
**状态：** 已确认实施约束  
**日期：** 2026-08-26  
**上位设计：** [SS-Screen Web 平台开发指南](web_platform_development_guide.md)  

## 1. 给实施 Codex 的直接指令

在当前工作区实现 SS-Screen Web 方案二。开始任何修改前，完整阅读：

1. `AGENTS.md`；
2. `ZMD/README.md`；
3. `docs/PROJECT_LOG.md`；
4. `docs/PROJECT_PLAN.md`；
5. `docs/web_platform_development_guide.md`；
6. 本任务书。

本轮不是讨论或重新选型。已经确定的决策如下：

| 决策 | 已确认值 |
|---|---|
| Git 分支 | `codex/web-platform`，当前已经处于该分支 |
| Git 提交 | 禁止创建提交，除非用户以后另行明确授权 |
| 工作树 | 已有大量用户/前序开发变更，必须全部保留 |
| 产品范围 | 实验室内网多用户 Web 平台，先完成 Stage 1--5 MVP |
| 首轮编码范围 | Phase 0 非破坏性预检 + Phase 1 控制层垂直切片 |
| 前端 | React + TypeScript + Vite，使用 npm |
| 后端 | FastAPI + Pydantic + SQLAlchemy 2 + Alembic |
| 数据库 | PostgreSQL |
| 队列 | Celery + Redis，业务状态以 PostgreSQL 为准 |
| 制品 | 仓库外 `FileSystemArtifactStore`，以后可替换 MinIO/S3 |
| 制品根目录 | `/vepfs-mlp2/project-battery/zuolong/ss-screen-web-data` |
| 部署 | 单台服务器，API/PostgreSQL/Redis/CPU Worker；GPU Worker 使用本机 CUDA |
| 身份 | 开发阶段单用户身份，保留生产 OIDC 接口 |
| 服务管理 | 提供 Compose 配置；本机目前没有 Compose 命令，不得安装系统包绕过 |
| 科学边界 | `ssscreen_web -> ssscreen`，不得反向依赖 |

若实施中发现某个事实与表中不一致，以当前真实文件系统和最新 `PROJECT_LOG.md` 为准，并先记录差异。不要为普通实现细节请求用户确认；按本任务书的默认值推进。

## 2. 当前环境快照

交接时已确认：

```text
workspace: /vepfs-mlp2/project-battery/zuolong/ss-screen-learning-20260722
branch: codex/web-platform
base HEAD: 33ddf40291aea89a93a7fb5aa3b5ac037a944f1d
Python: 3.11.15 from .venv
ssscreen: 1.0
Node: 20.20.2
npm: 10.8.2
Docker engine/client: 24.0.9
pnpm: unavailable
docker compose: unavailable
ports 5173/8000/5432/6379: free at handoff time
core tests: 166 passed
```

工作树基于很早的 HEAD，包含大量未提交的 Stage 7--11、文档、ZMD 和测试。实施者必须把它视为用户工作成果，而不是待清理内容。

制品目录当前存在，但交接时为 `root:root`、权限 `755`。当前执行身份可以访问不代表未来非 root 容器一定可写。实现时必须：

- 只在该目录中新建 Web 平台自己的子目录；
- 启动前执行实际运行 UID 的可写性检查；
- 不擅自 `chown -R` 或放宽整个父目录权限；
- 权限不满足时给出精确诊断和管理员操作建议，而不是回退到仓库内。

## 3. 本轮交付目标

本轮完成一个真实、可运行、可测试的控制层垂直切片：

```text
Browser
  -> FastAPI
  -> PostgreSQL Project/Run/Task/Attempt/Artifact/Event
  -> Celery 示例任务
  -> repository-external ArtifactStore
  -> SSE 状态更新
  -> Browser 下载生成制品
```

该垂直切片暂不运行 Stage 1 科学算法，但所有接口和状态规则必须能够在下一轮替换为真实 StageRunner，而无需推翻数据库或前端结构。

### 3.1 必须完成

- 建立 `web/backend` 独立 Python 包；
- 建立 `web/frontend` React/TypeScript 应用；
- 建立 `web/deploy` 开发部署配置；
- 建立 PostgreSQL 初始 schema 和 Alembic migration；
- 实现开发身份、Project、Run、Task、Attempt、Artifact、Event；
- 实现数据库权威状态机；
- 实现安全的 `FileSystemArtifactStore`；
- 实现一个确定性示例 Task：生成小型 JSON 制品；
- 实现 Celery 入队、执行、失败、显式重试和取消请求基础语义；
- 实现 Run 事件 SSE，支持 `Last-Event-ID` 恢复；
- 实现项目列表、项目详情和 Run 状态页；
- 实现制品元数据与下载；
- 建立后端、前端和 Playwright 的最小测试链；
- 提供无需猜测的本地开发说明；
- 更新 ZMD 和 `PROJECT_LOG.md`。

### 3.2 本轮禁止扩展

- 不实现 Stage 1--11 的具体 StageRunner；
- 不实现 GPU Worker、MACE、Phonopy、Slurm 或 AiiDA；
- 不实现正式 OIDC 登录；
- 不实现用户上传任意脚本或任意 Shell 执行；
- 不把现有 Click CLI 包装为后台子进程；
- 不移动或删除 `work/`、`aiida-module/`、模型或其他既有文件；
- 不整理、格式化或重写本任务之外的历史文件；
- 不创建 Git commit、tag、merge 或 rebase。

## 4. 强制依赖方向

```text
web/frontend
    -> generated OpenAPI client
web/backend/ssscreen_web
    -> application/domain/infrastructure
    -> ssscreen public Python functions (future StageRunner only)
src/ssscreen
    -X-> web/backend
    -X-> FastAPI/SQLAlchemy/Celery/Redis
```

首轮可以安装 Web 后端包与根包到同一个项目 `.venv`，但依赖元数据必须分开。核心 `pyproject.toml` 不加入 FastAPI、SQLAlchemy、Celery 或前端依赖。

## 5. 目标目录与文件

实施者可以在保持职责等价的前提下微调文件名，但不得把层次压回一个大文件。

```text
web/
├── README.md
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/0001_control_plane.py
│   ├── src/ssscreen_web/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── settings.py
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   ├── errors.py
│   │   │   ├── health.py
│   │   │   ├── me.py
│   │   │   ├── projects.py
│   │   │   ├── runs.py
│   │   │   ├── tasks.py
│   │   │   ├── artifacts.py
│   │   │   └── events.py
│   │   ├── application/
│   │   │   ├── projects.py
│   │   │   ├── runs.py
│   │   │   ├── tasks.py
│   │   │   └── unit_of_work.py
│   │   ├── domain/
│   │   │   ├── enums.py
│   │   │   ├── transitions.py
│   │   │   └── errors.py
│   │   ├── infrastructure/
│   │   │   ├── database.py
│   │   │   ├── models.py
│   │   │   ├── repositories.py
│   │   │   └── artifacts.py
│   │   └── workers/
│   │       ├── celery_app.py
│   │       └── example_task.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── conftest.py
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   ├── playwright.config.ts
│   └── src/
│       ├── app/
│       ├── api/
│       ├── components/
│       └── features/
└── deploy/
    ├── compose.yaml
    ├── env.example
    └── README.md
```

同时新增：

```text
docs/adr/0001-web-core-boundary.md
docs/adr/0002-artifact-store.md
docs/adr/0003-task-state-machine.md
docs/adr/0004-development-auth.md
```

## 6. 数据库基线

### 6.1 表

首个 migration 至少创建：

| 表 | 必需字段 |
|---|---|
| `users` | UUID、OIDC subject、display name、status、created/updated |
| `projects` | UUID、name、description、owner ID、retention policy、created/updated |
| `project_members` | project/user、role、created；组合唯一约束 |
| `runs` | UUID、project、pipeline version、status、configuration JSONB、timestamps、version counter |
| `tasks` | UUID、run、stage、task type、status、scientific status、depends_on JSONB、timestamps、version counter |
| `attempts` | UUID、task、number、status、settings hash、worker ID、error code/message、timestamps |
| `artifacts` | UUID、project、attempt、kind、URI/key、filename、content type、size、SHA-256、schema version、created |
| `events` | 单调事件 ID、project/run/task、kind、payload JSONB、actor、created |

### 6.2 约束

- 所有业务实体使用 UUID；
- `events.id` 必须支持 SSE 游标单调排序；
- `attempts(task_id, number)` 唯一；
- Artifact SHA-256 长度和非负大小受约束；
- role/status 使用数据库可校验值；
- 外键删除策略不得导致审计历史意外级联删除；
- Run/Task 带乐观锁版本或等价并发保护；
- 时间使用带时区列；
- migration 的 downgrade 要么可逆，要么明确拒绝并解释，不得伪装可逆。

### 6.3 状态机

实现上位设计中的生命周期状态，并把转换集中在 `domain/transitions.py`。Router、Celery task 和 ORM model 不得各自复制一套状态判断。

首轮至少支持：

```text
Run: DRAFT -> QUEUED -> RUNNING -> SUCCEEDED | FAILED | CANCELLED
Task: PENDING -> READY -> QUEUED -> RUNNING -> SUCCEEDED | FAILED | CANCEL_REQUESTED | CANCELLED
Task: FAILED -> READY only through explicit retry use case
```

每次成功转换与对应 Event 必须处于同一数据库事务。

## 7. API 基线

统一前缀 `/api/v1`，健康检查除外。

### 7.1 必须实现的端点

```text
GET    /health/live
GET    /health/ready
GET    /api/v1/me

GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}

POST   /api/v1/projects/{project_id}/runs
GET    /api/v1/projects/{project_id}/runs
GET    /api/v1/runs/{run_id}
POST   /api/v1/runs/{run_id}/actions/start
POST   /api/v1/runs/{run_id}/actions/cancel
GET    /api/v1/runs/{run_id}/events

GET    /api/v1/runs/{run_id}/tasks
GET    /api/v1/tasks/{task_id}
POST   /api/v1/tasks/{task_id}/actions/retry
POST   /api/v1/tasks/{task_id}/actions/cancel

GET    /api/v1/runs/{run_id}/artifacts
GET    /api/v1/artifacts/{artifact_id}
GET    /api/v1/artifacts/{artifact_id}/download
```

### 7.2 示例 Run 行为

`POST /projects/{id}/runs` 创建 DRAFT Run，configuration 至少包含：

```json
{
  "pipeline": "control-plane-demo",
  "message": "SS-Screen Web control plane"
}
```

`start` 创建一个 `example.generate-json` Task 并入队。Worker 在 Attempt 沙箱生成：

```json
{
  "schema_version": 1,
  "run_id": "<uuid>",
  "task_id": "<uuid>",
  "message": "SS-Screen Web control plane",
  "ssscreen_version": "1.0"
}
```

然后计算 SHA-256、发布 Artifact、完成 Attempt/Task/Run，并在每一步写 Event。该 JSON 是控制层测试制品，不是科研结果。

### 7.3 错误格式

```json
{
  "code": "task.invalid_transition",
  "message": "Task cannot be retried from RUNNING",
  "field_errors": [],
  "trace_id": "..."
}
```

错误码稳定，message 可读；不得把 traceback 或数据库连接信息返回浏览器。

## 8. ArtifactStore 基线

### 8.1 根目录

```text
/vepfs-mlp2/project-battery/zuolong/ss-screen-web-data
```

开发实例在其下使用：

```text
artifacts/
attempt-sandboxes/
uploads-quarantine/
```

不得使用 `/tmp` 作为最终制品，也不得回退到仓库 `work/`。

### 8.2 安全要求

- key 只能由服务端 UUID 和白名单片段组成；
- `Path.resolve()` 后必须仍位于配置根目录；
- 拒绝绝对路径、`..`、符号链接跳转和 NUL；
- 写入同目录临时文件，fsync/关闭、计算 SHA 后原子发布；
- Artifact 完成后不可原地修改；
- 下载由 Project 权限控制，不能通过猜 UUID 越权；
- 测试覆盖路径穿越、符号链接、重复文件名、部分写入和哈希不匹配；
- 删除功能不在首轮开放。

## 9. 身份和权限

### 9.1 开发身份

开发模式通过服务端设置注入固定用户，不接受客户端任意传 `X-User-Id` 冒充：

```text
APP_ENV=development
DEV_AUTH_ENABLED=true
DEV_USER_SUBJECT=dev-local-user
DEV_USER_DISPLAY_NAME=SS-Screen Developer
```

若 `APP_ENV` 不是 `development` 且 `DEV_AUTH_ENABLED=true`，应用必须拒绝启动。

### 9.2 Project 权限

实现 `owner/editor/viewer`：

| 操作 | owner | editor | viewer |
|---|---:|---:|---:|
| 查看 Project/Run/Artifact | 是 | 是 | 是 |
| 新建和启动 Run | 是 | 是 | 否 |
| 重试/取消 Task | 是 | 是 | 否 |
| 修改成员和保留策略 | 是 | 否 | 否 |

首轮 UI 可以只暴露 owner，但后端权限模型和测试必须包含三种角色。

## 10. Celery 和一致性

### 10.1 队列

首轮只建立：

```text
control
cpu
```

示例 Task 进入 `control`。不要提前建立 GPU 逻辑。

### 10.2 入队一致性

避免数据库已提交但消息丢失：优先实现事务 outbox，或者实现清晰、可测试的 enqueue reconciliation。不得在 Router 中先发 Celery 再提交数据库。

最低可接受行为：

- start 事务创建 Task 和 `task.queued` Event/outbox；
- dispatcher 发布 Celery 消息；
- Worker 通过 Task ID 重新读取权威状态；
- 重复投递根据状态/幂等指纹安全退出；
- Worker 崩溃后 Task 可由恢复任务标记为 FAILED 或重新排队；
- Celery result backend 不作为业务事实来源。

### 10.3 取消

- queued Task 可进入 `CANCELLED`；
- running Task 先进入 `CANCEL_REQUESTED`；
- 示例 Worker 在安全检查点读取取消标志；
- 不能保证立即中断时，API 必须如实返回“取消已请求”；
- 不对运行中的 Python 进程使用不受控强杀作为唯一方案。

## 11. SSE

`GET /api/v1/runs/{run_id}/events`：

- `Content-Type: text/event-stream`；
- 只发送已授权 Project 的事件；
- 使用 Event ID；
- 支持 `Last-Event-ID`；
- 心跳注释保持代理连接；
- 客户端断线重连不丢已提交事件；
- 数据库查询分页，不把全部历史一次读入内存；
- 前端动态状态区域使用 `aria-live="polite"`。

## 12. 前端首轮范围

### 12.1 页面

```text
/projects
/projects/:projectId
/projects/:projectId/runs/new
/runs/:runId
/artifacts/:artifactId
```

### 12.2 页面行为

`/projects`：

- 展示名称、owner、最近运行和更新时间；
- 提供新建 Project 对话框；
- loading/empty/error/success 状态齐全。

Project 详情：

- 展示基本信息和 Run 表；
- 可以新建 demo Run；
- viewer 看不到写操作。

Run 页面：

- 固定 Stage/Task 状态表；
- SSE 实时更新；
- 显示 Run 和科学状态为两个字段；
- 展示 Attempt、错误、事件时间线和 Artifact；
- 提供允许状态下的取消/重试；
- Artifact 可下载并显示 SHA。

### 12.3 设计约束

- 数据密集型科研工作台，不做 landing page；
- 左侧导航、主内容和详情区，不使用横向旅程；
- 使用 Lucide 图标，不使用 emoji 图标；
- body 移动端不小于 16 px；
- 触控目标至少 44 x 44 px；
- 正文对比度至少 4.5:1；
- 图标按钮有 `aria-label` 和 tooltip；
- 表单显式 label，错误靠近字段；
- 所有可点击行为支持键盘；
- 动画只使用 150--300 ms 的颜色/透明度，并尊重 reduced motion；
- 375、768、1024、1440 px 均无不可控页面横向溢出；
- 表格可局部横向滚动，身份列保持可见；
- 不使用玻璃拟态、渐变装饰、巨大标题、嵌套卡片和纯颜色状态。

## 13. 包管理和本地开发

### 13.1 Python

所有 Python 操作必须：

```bash
cd /vepfs-mlp2/project-battery/zuolong/ss-screen-learning-20260722
source .venv/bin/activate
```

在同一 `.venv` 中安装根包和 `web/backend` editable。禁止使用系统 Python 或全局 pip。Web 后端自己的 `pyproject.toml` 保存运行/开发依赖，核心根包不接收 Web 依赖。

### 13.2 Node

使用 npm 和 `package-lock.json`。不得因个人偏好安装全局 pnpm/yarn。Node 包只安装到 `web/frontend/node_modules`，该目录必须被 Git 忽略。

### 13.3 容器服务

必须创建 `web/deploy/compose.yaml`，但交接环境没有 `docker compose` 或 `docker-compose` 命令。不得修改系统或静默安装 Compose 插件。

实施验证可以采用以下之一：

1. 若新窗口环境已经提供 Compose，使用 Compose；
2. 使用显式、命名的临时 PostgreSQL/Redis `docker run` 容器；
3. 若 Docker 服务不可用，完成全部不依赖服务的测试，并明确报告集成测试未运行。

不得把 SQLite 作为 PostgreSQL 集成测试替代品。临时容器的删除属于测试清理，只能删除本任务创建且名称精确匹配的容器/volume。

### 13.4 默认端口

```text
frontend: 5173
api: 8000
postgres: 5432
redis: 6379
```

启动前检测占用；若被占用，使用环境变量选择其他端口，不终止未知进程。

## 14. 配置文件

`web/deploy/env.example` 只放无密钥示例：

```text
APP_ENV=development
DATABASE_URL=postgresql+psycopg://ssscreen:ssscreen@postgres:5432/ssscreen
REDIS_URL=redis://redis:6379/0
ARTIFACT_ROOT=/data/ss-screen-web
DEV_AUTH_ENABLED=true
DEV_USER_SUBJECT=dev-local-user
DEV_USER_DISPLAY_NAME=SS-Screen Developer
CORS_ORIGINS=http://localhost:5173
API_BASE_URL=http://localhost:8000
LOG_LEVEL=INFO
```

真实 `.env` 必须被忽略。生产配置如果把 Artifact 根指向 Git 工作树，后端必须拒绝启动。

## 15. 实施顺序

每一步完成后立即运行对应验证，不要等到最后统一修复。

### Step 0：非破坏性基线检查

- 确认分支仍为 `codex/web-platform`；
- 保存 `git status --short` 输出到会话记录，不写生成文件；
- 运行 Python/包版本、166 项测试和正式范围 Ruff；
- 检查授权制品目录和工具链；
- 不移动大型文件，不清理工作树，不提交。

**完成条件：** 已知基线可重复，现有变更未受影响。

### Step 1：ADR 和包骨架

- 新增四个 ADR；
- 新建 backend/frontend/deploy 目录；
- 后端提供 `/health/live`；
- 前端可显示 API live 状态；
- 设置 CORS 只允许配置来源。

**完成条件：** 后端单元测试和前端生产构建通过。

### Step 2：数据库和权限

- 建立 models、migration、repositories、Unit of Work；
- 实现开发身份和 Project 权限；
- 用真实 PostgreSQL 跑 migration up/down/up 或明确的不可逆策略；
- API 实现 `/me` 和 Project 列表/创建/详情。

**完成条件：** owner/editor/viewer 与跨 Project 越权测试通过。

### Step 3：ArtifactStore

- 实现 FileSystemArtifactStore；
- 实现 Artifact 表和下载授权；
- 增加路径安全、原子写和 SHA 测试；
- 后端 ready 检查验证根目录存在和可写，但不得留下垃圾文件。

**完成条件：** 路径穿越和未授权下载均被拒绝。

### Step 4：Run/Task/Attempt/Event

- 实现集中状态机和事务 Event；
- 实现 Run 创建、启动、查看；
- 实现 Task/Attempt 查询；
- 实现取消请求和显式重试；
- 非法转换返回稳定错误码。

**完成条件：** 状态转换、并发和回滚测试通过。

### Step 5：Celery 示例任务

- 实现 outbox/调和机制；
- Worker 生成确定性 JSON；
- 发布 Artifact 并完成状态；
- 重复投递不重复发布；
- 模拟 Worker 失败可生成 FAILED Attempt 并重试。

**完成条件：** 一个 Run 从 DRAFT 走到 SUCCEEDED，并可下载校验哈希一致的 JSON。

### Step 6：SSE 和 React 工作台

- 实现事件流和游标恢复；
- 实现五个首轮页面；
- 使用生成的 OpenAPI TypeScript client；
- 使用 TanStack Query 管理服务器状态；
- 完成键盘、错误、空状态和响应式布局。

**完成条件：** 浏览器刷新或 SSE 断线重连后仍显示一致状态。

### Step 7：端到端和文档

- Playwright 创建 Project、Run、启动、观察完成、下载 Artifact；
- 验证错误/重试路径；
- 更新 `web/README.md`、部署说明、ZMD 和项目日志；
- 全量运行核心和 Web 门禁；
- 截图检查桌面/移动界面，确认无重叠、裁切或空白主视图。

**完成条件：** 本任务书第 17 节全部满足。

## 16. 测试命令基线

实施者可以根据实际包脚本调整命令名称，但最终 README 必须给出唯一权威命令。

```bash
# Core
source .venv/bin/activate
pytest
ruff check src tests scripts

# Backend
python -m pytest web/backend/tests
ruff check web/backend
black --check web/backend

# Frontend
npm --prefix web/frontend run lint
npm --prefix web/frontend run typecheck
npm --prefix web/frontend run test
npm --prefix web/frontend run build

# Browser
npm --prefix web/frontend run test:e2e
```

新增类型检查工具时写入 backend/frontend 的开发依赖并记录命令。不要声称通过未实际运行的检查。

## 17. 首轮验收清单

### 17.1 功能

- [ ] 可以打开项目列表；
- [ ] 可以创建 Project；
- [ ] 可以创建 demo Run；
- [ ] 可以启动 Run；
- [ ] Run 创建 Task 和 Attempt；
- [ ] Worker 生成 JSON Artifact；
- [ ] 页面通过 SSE 显示状态变化；
- [ ] 页面可以查看事件和 SHA；
- [ ] 授权用户可以下载 Artifact；
- [ ] 失败 Task 可以显式重试；
- [ ] 取消语义与真实状态一致；
- [ ] 重复 start/消息不会生成重复结果。

### 17.2 安全和数据

- [ ] viewer 无法启动、取消或重试；
- [ ] 用户无法读取其他 Project 的 Run/Artifact；
- [ ] 路径穿越和符号链接逃逸测试通过；
- [ ] `.env`、密钥和数据库 URL 不进入日志或前端 bundle；
- [ ] 制品实际位于授权仓库外目录；
- [ ] Artifact SHA 与下载内容一致；
- [ ] 数据库状态和 Event 在失败事务中共同回滚；
- [ ] Celery result backend 不是权威状态。

### 17.3 工程质量

- [ ] 原有 166 项核心测试继续通过；
- [ ] 正式范围 Ruff 通过；
- [ ] backend tests/format/type checks 通过；
- [ ] frontend lint/type/test/build 通过；
- [ ] Playwright 主路径通过，或因明确外部工具缺失而如实报告；
- [ ] migration 在真实 PostgreSQL 验证；
- [ ] OpenAPI client 可重复生成且工作树无意外漂移；
- [ ] 375/768/1024/1440 px 页面无重叠和全局横向溢出；
- [ ] ZMD 链接零失效；
- [ ] `git diff --check` 通过；
- [ ] 没有创建 Git commit。

## 18. 停止和升级条件

只有出现以下情况才停止并询问用户：

- 授权制品目录对实际服务 UID 不可写，且无法通过应用配置解决；
- 需要修改仓库外其他路径或删除既有数据；
- 发现真实 Secret 已进入待新增文件；
- 当前工作树发生无法归因的重叠修改，继续会覆盖用户内容；
- 要求安装系统级软件、改变 Docker daemon 或管理员权限；
- 已确认的架构无法满足现有科学 API 的真实行为，需要改变上位设计。

以下情况不应停止：npm 包选择的小差异、内部文件命名、测试工具配置、UI 细节或可从代码发现的 schema。使用代码库既有模式和本任务书默认值处理。

## 19. 完成交接时的报告格式

最终回复必须包含：

1. 已实现的垂直切片和主要文件；
2. 本地访问 URL；
3. 实际运行的测试及数量；
4. 未运行的验证及原因；
5. 数据库、Redis 和 ArtifactStore 的实际位置；
6. 当前分支和明确的“未创建提交”；
7. 剩余风险和下一步 Stage 1 StageRunner；
8. 不把 demo JSON 描述为科研结果。

## 20. 复制给新 Codex 的启动提示

```text
请在当前工作区实现 SS-Screen Web 控制层第一轮垂直切片。

必须先完整阅读 AGENTS.md、ZMD/README.md、docs/PROJECT_LOG.md、
docs/PROJECT_PLAN.md、docs/web_platform_development_guide.md 和
docs/web_platform_implementation_handoff.md，然后严格执行最后一份任务书。

已确认：使用 codex/web-platform 分支，不创建 Git 提交；保留全部既有脏工作树；
制品目录为 /vepfs-mlp2/project-battery/zuolong/ss-screen-web-data；单机内网部署；
开发期单用户身份并保留 OIDC 接口；前端 React/TypeScript/Vite + npm，后端
FastAPI/PostgreSQL/Redis/Celery。完成 Phase 0 非破坏性预检和 Phase 1 控制层
垂直切片，持续测试并同步 ZMD/PROJECT_LOG。不要实现 Stage 1--11、GPU、Slurm
或 AiiDA，不要移动/删除既有 work、模型、aiida-module 或其他用户文件。
```
