# SS-Screen Web 平台

本目录已实现 Phase 1 控制层，以及 Phase 2 的 Stage 1 MP/WBM Dataset、Stage 1a composition
和 Stage 2 condensation。
平台管理 Project、Run、Task、Attempt、Artifact、Event 和 Dataset；确定性 demo 仍只用于
验证编排。Stage 1 调用 `src/ssscreen` 的权威 loader，Stage 1a 调用权威组成筛选函数；所有科学
输出都带不可变 Artifact 与 provenance。

## 目录

- `backend/`：FastAPI、SQLAlchemy 2、Alembic、Celery、权限、状态机、StageRunner 和 ArtifactStore；
- `frontend/`：React、TypeScript、Vite、TanStack Query/Router 和 OpenAPI 类型客户端；
- `deploy/`：PostgreSQL、Redis、API、control/CPU Worker 和前端 Compose 基线。

依赖方向固定为 `ssscreen_web -> ssscreen`。根包不依赖 Web 运行时。

## 本机开发

所有 Python 命令必须使用项目 `.venv`：

```bash
cd /vepfs-mlp2/project-battery/zuolong/ss-screen-learning-20260722
source .venv/bin/activate
python -m pip install --no-build-isolation -e 'web/backend[dev]'
npm --prefix web/frontend install
```

启动前确认 5432、6379、8000 和 5173 未被未知进程占用。Stage 1 还要求服务器能够只读访问
经过验证的 `mp_offline` SQLite 快照和 `mp_offline` Python 包。数据库路径只由管理员设置，
不得从浏览器请求接收。当前主机没有 Compose，可使用本任务专用容器；若同名容器已存在，
先判断是否为本项目创建，不要删除未知容器：

```bash
docker run -d --name ssscreen-web-dev-postgres \
  -e POSTGRES_USER=ssscreen -e POSTGRES_PASSWORD=ssscreen \
  -e POSTGRES_DB=ssscreen -p 5432:5432 postgres:16-alpine
docker run -d --name ssscreen-web-dev-redis -p 6379:6379 redis:7-alpine

cd web/backend
alembic upgrade head
cd ../..
MP_OFFLINE_DATABASE_PATH=/absolute/read-only/path/to/default.db \
MP_OFFLINE_DATABASE_REFERENCE=lab-mp-offline-snapshot \
SSSCREEN_CORE_REVISION=git:development-worktree \
uvicorn ssscreen_web.main:app --host 0.0.0.0 --port 8000
```

另开两个已激活 `.venv` 的终端：

```bash
MP_OFFLINE_DATABASE_PATH=/absolute/read-only/path/to/default.db \
MP_OFFLINE_DATABASE_REFERENCE=lab-mp-offline-snapshot \
SSSCREEN_CORE_REVISION=git:development-worktree \
celery -A ssscreen_web.workers.celery_app:celery_app worker \
  -Q control,cpu --loglevel=INFO --concurrency=1
npm --prefix web/frontend run dev -- --host 0.0.0.0 --port 5173
```

若主机的 inotify watcher 已耗尽、Vite 开发服务报告 `ENOSPC`，不要修改系统限制；先构建再用
不依赖源码监听的预览服务：

```bash
npm --prefix web/frontend run build
npm --prefix web/frontend run preview -- --host 0.0.0.0 --port 5173
```

浏览器访问 [http://localhost:5173](http://localhost:5173)。API 文档位于
[http://localhost:8000/docs](http://localhost:8000/docs)，ready 检查位于
[http://localhost:8000/health/ready](http://localhost:8000/health/ready)。

远程服务器开发时，本机浏览器中的 `localhost` 指本机，不是服务器。请在本机建立 SSH 隧道：

```bash
ssh -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 USER@SERVER
```

然后在本机打开上述两个 `localhost` 地址。

## Stage 1 使用流程

1. 打开一个 Project，选择“准备数据集”；
2. 输入数据集名称和 `max_e_hull`，创建 `stage-1-mp-offline` 草稿；
3. 在 Run 页面检查已冻结的参数、科学核心版本和修订标识，点击“开始”；
4. CPU Worker 读取管理员配置的只读快照，排除 deprecated 记录并生成规范化 DataFrame；
5. 成功后进入 Dataset 页面，检查记录数、快照引用/SHA-256、查询阈值和两个不可变制品。

输出的 `mp.df` 是 pandas pickle，只能在可信的 SS-Screen Python 环境中加载。provenance 记录
数据库 SHA-256、大小、查询、pipeline 版本、核心版本、部署修订标识和核心源码 SHA-256，但不
写入服务器绝对路径。完整快照运行可能生成数百 MB 制品；应预留 ArtifactStore 空间，且不要把
制品复制回 Git 工作树。

## Stage 1a 使用流程

1. 在已登记的 MP/WBM Dataset 详情页选择“组成筛选”；
2. 选择二元或三元，设置最大带隙、最大 `e_hull` 和可选高级分组门槛；
3. 创建草稿后，在 Run 页核对被冻结的 Dataset Artifact SHA、科学核心身份和全部阈值，再启动；
4. CPU Worker 生成并验证 `composition-candidates.csv` 与 provenance；
5. 成功后 Run 页显示最多前 20 条候选和候选总数，完整 CSV 仍从不可变 Artifact 下载。

候选预览 API 只允许返回 1--100 行，并只读取数据库登记的同一 Attempt 候选/provenance 制品；
零候选是合法科学结果。当前预览用于 Run 内快速核对，不替代后续 Stage 5 的可分页候选领域模型。

## Stage 2 使用流程

1. 在成功的 Stage 1a Run 页面选择“生成结构描述”；
2. 核对候选总数并设置每批材料数（1--100），创建 `stage-2-condensation` 草稿；
3. 在 Run 页复核来源 composition Run、候选 Artifact SHA、Dataset Artifact SHA 和批大小后启动；
4. CPU Worker 每批调用核心 `condense_dataframe`，逐材料原子写 JSON、写持久检查点并检查取消请求；
5. Run 页实时显示处理/成功/本次写入/检查点跳过/失败数量，完成后下载 ZIP、逐材料 index、失败
   CSV、JSONL manifest 和 provenance。

单材料 Robocrys 错误属于可见科学结果，不会吞掉同批其他结构。Worker 中断造成 Task 失败时，显式
重试会从 Task 检查点恢复，已完成且校验通过的 JSON 记为 `skipped`；成功发布五类不可变制品后
检查点才被清理。取消也只在批边界生效，以保证每个已登记结构和检查点都是完整文件。最终
manifest 使用 `condensed/{material_id}.json` 逻辑路径，不写入服务器沙箱绝对路径。

开发 ArtifactStore 固定在仓库外：

```text
/vepfs-mlp2/project-battery/zuolong/ss-screen-web-data/
├── artifacts/
├── attempt-sandboxes/
└── uploads-quarantine/
```

服务启动前检查实际运行 UID 对根目录的可写和执行权限。不要 `chown -R` 整个父目录，也不要
回退到仓库 `work/`。若非 root 容器不可写，请管理员只为 Web 服务创建专用组，并向上述三个
子目录授予该组写权限。

`/health/ready` 会真实探测 PostgreSQL、Redis、三个存储目录的可写性，以及核心源码版本与
installed distribution metadata 是否一致，并清理探针文件。科学 Run 创建时冻结版本、部署修订
和源码 SHA-256；启动及 Worker 执行前再次比较，身份变化时要求创建新 Run。Artifact 发布使用
不覆盖已有 key 的原子操作；任务消息绑定明确的 Attempt，重复/过期投递会幂等退出。
控制层还会重新投递停滞的 outbox 消息，并按独立阈值把超时的 demo、Dataset、composition 或
condensation 任务记录为
`worker.lost`。`control` 与 `cpu` 使用不同 exchange/routing key，避免长数据任务阻塞控制任务。

## OpenAPI 客户端

后端 schema 和前端类型必须一起更新：

```bash
source .venv/bin/activate
python web/backend/export_openapi.py
npm --prefix web/frontend run api:generate
git diff --exit-code -- web/backend/openapi.json web/frontend/src/api/schema.d.ts
```

最后一条在存在预期未提交生成变更时会失败；先审查并保留生成文件，再次运行即可检查漂移。

## 测试门禁

```bash
source .venv/bin/activate
pytest
ruff check src tests scripts
python -m pytest web/backend/tests
ruff check web/backend
black --check web/backend

npm --prefix web/frontend run lint
npm --prefix web/frontend run typecheck
npm --prefix web/frontend run test
npm --prefix web/frontend run build
```

Playwright 浏览器安装到前端自己的忽略目录：

```bash
cd web/frontend
PLAYWRIGHT_BROWSERS_PATH=.playwright-browsers npx playwright install chromium
cd ../..
npm --prefix web/frontend run test:e2e
```

E2E 需要正在运行的 PostgreSQL、Redis、API、control/CPU Worker 和前端。当前 20 项浏览器检查
覆盖 375、768、1024 和 1440 四种宽度，包括 Project -> Run -> Task -> Artifact demo 主路径、
Stage 1 Dataset 草稿、Stage 1a 冻结配置/候选预览、Stage 2 创建与进度界面、下载文件 SHA-256
校验、确定性失败后的显式重试，以及全局横向溢出。后端当前为 54 项 pytest，前端另有 1 项
Vitest。测试不会对 2.2 GB 真实快照执行全量导出；
WBM 集成测试会真实解析微型 extxyz，并验证隔离、二次 SHA 校验、制品、Dataset 和清理。

## Compose

在已提供 Docker Compose 的机器：

```bash
cp web/deploy/env.example web/deploy/.env
docker compose --env-file web/deploy/.env -f web/deploy/compose.yaml up --build
```

`.env` 被 Git 忽略。示例凭据仅用于隔离开发环境；生产环境必须使用 Secret Manager、正式
OIDC、非默认数据库凭据和独立运行 UID。`MP_OFFLINE_DATABASE_HOST_PATH` 指向单个只读 SQLite
文件，`MP_OFFLINE_PACKAGE_HOST_PATH` 指向含 `src/mp_offline` 的只读包目录；CPU Worker 需要
两者，API 只需数据库文件用于创建前可用性检查。
`SSSCREEN_CORE_REVISION` 必须标识实际部署的 Git commit 或发布构建；production 拒绝默认
`development-worktree`。精确代码内容另由自动计算的核心源码 SHA-256 固定。

## 当前边界

- 已完成 Stage 1 MP 离线 Dataset；demo 仍可用于控制面诊断；
- 已完成 WBM 用户上传、仓库外 quarantine、严格 schema/provenance 校验、Dataset 登记，以及
  草稿/排队/运行中取消后的隔离输入回收；校验失败输入保留供显式重试；
- 已完成从统一 Dataset Artifact 启动 Stage 1a 二元/三元组成筛选、发布候选 CSV/provenance，
  并在 Run 页显示冻结参数、受限候选预览和完整 CSV 入口；
- 已完成 Stage 2 condensation：双输入身份冻结、批处理、逐材料失败、取消检查点、失败后续跑、
  实时进度和五类不可变输出；
- 尚未实现在线 MP API，以及 Stage 3--11 Web StageRunner；
- 尚未接入正式 OIDC、GPU/HPC、Slurm 或 AiiDA；
- Web 不改变科学核心的权威地位，也不把离线快照覆盖范围表述为当前在线 MP 的完整覆盖。
