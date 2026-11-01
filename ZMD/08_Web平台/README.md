# Web 平台导航

真实目录：[`web/`](../../web/)

## 依赖与边界

`web/backend/ssscreen_web -> src/ssscreen` 是唯一允许方向。科学核心不依赖 FastAPI、
SQLAlchemy、Celery、Redis 或 React。当前已实现 Phase 1 控制层，以及 Phase 2 的 Stage 1 MP 离线
和 WBM 隔离上传 Dataset、Stage 1a composition、Stage 2 condensation 垂直切片；科学查询/
标准化/筛选/结构凝聚仍由
`src/ssscreen` 提供，Web 不复制算法。

## 文件映射

| 路径 | 职责 | 关联验证 |
|---|---|---|
| [`web/README.md`](../../web/README.md) | 本地安装、启动、OpenAPI、测试和 Compose 权威入口 | 按命令从空服务启动 |
| [`web/backend/pyproject.toml`](../../web/backend/pyproject.toml) | 独立 Python 依赖和工具配置 | `pip check`、Ruff、Black |
| [`web/backend/src/ssscreen_web/domain/`](../../web/backend/src/ssscreen_web/domain/) | Run/Task 状态、合法转换和稳定领域错误 | unit pytest |
| [`web/backend/src/ssscreen_web/application/`](../../web/backend/src/ssscreen_web/application/) | Project/Run/Task use case、pipeline registry、事务 Event 和重试/取消 | integration pytest |
| [`web/backend/src/ssscreen_web/application/scientific_runtime.py`](../../web/backend/src/ssscreen_web/application/scientific_runtime.py) | 核心源码/distribution版本、部署修订、源码SHA与冻结身份门禁 | runtime unit/integration pytest |
| [`web/backend/src/ssscreen_web/application/stages/`](../../web/backend/src/ssscreen_web/application/stages/) | MP/WBM Dataset、composition 与 condensation 的 prepare/execute/validate/publish | StageRunner unit/integration pytest |
| [`web/backend/src/ssscreen_web/infrastructure/`](../../web/backend/src/ssscreen_web/infrastructure/) | PostgreSQL models、Dataset、权限仓库和流式 ArtifactStore | PostgreSQL/安全 pytest |
| [`web/backend/src/ssscreen_web/api/`](../../web/backend/src/ssscreen_web/api/) | REST、Dataset API、健康检查、SSE、错误和开发身份 | FastAPI integration pytest |
| [`web/backend/src/ssscreen_web/workers/`](../../web/backend/src/ssscreen_web/workers/) | Celery control/CPU 队列、outbox dispatcher、demo、MP/WBM Dataset、composition 与 condensation Worker | Worker 成功/失败/重试/取消测试 |
| [`web/backend/migrations/`](../../web/backend/migrations/) | 控制层与 Dataset PostgreSQL schema、可逆 Alembic migrations | `up/down/up`、`alembic check` |
| [`web/backend/openapi.json`](../../web/backend/openapi.json) | FastAPI 生成的前后端契约 | 客户端重复生成 |
| [`web/frontend/src/api/`](../../web/frontend/src/api/) | OpenAPI 类型客户端和请求封装 | TypeScript 构建 |
| [`web/frontend/src/features/`](../../web/frontend/src/features/) | Project、Run、Dataset 新建/详情和 Artifact 工作台 | Vitest/Playwright |
| [`web/frontend/src/styles.css`](../../web/frontend/src/styles.css) | 科研工作台、响应式表格、焦点/触控/动效规则 | 四宽度截图与 DOM 审计 |
| [`web/deploy/compose.yaml`](../../web/deploy/compose.yaml) | PostgreSQL、Redis、API、control/CPU Worker、只读 MP 源和前端 | Compose 可用主机验收 |

## 数据位置

数据库开发实例使用 PostgreSQL；Redis 只作 broker。最终制品只能写到仓库外：

```text
/vepfs-mlp2/project-battery/zuolong/ss-screen-web-data/
├── artifacts/
├── attempt-sandboxes/
└── uploads-quarantine/
```

三个子目录由本轮创建，属主为 `root:root`、权限 `755`。当前 root 开发进程可写；未来非 root
容器必须先由管理员向专用组授予子目录写权限，禁止放宽整个父目录或回退到仓库。ready 端点
会分别执行无残留的真实写入探针；Artifact 以不覆盖既有 key 的原子操作发布。

MP SQLite 快照和 `mp_offline` 包也位于仓库外并只读使用。路径只由 API/CPU Worker 的服务端环境
配置；浏览器 Run 参数和 provenance 只保存稳定快照引用与 SHA-256，不保存绝对路径。

## 当前边界

- 首个真实运行已在仓库外 ArtifactStore 生成46,675行、430,317,793字节 `mp.df` 和脱敏
  provenance；Run/Task/Attempt/Dataset/Artifact 终态及文件 SHA 已核验一致；
- 已实现 Project/Run/Task/Attempt/Artifact/Event、owner/editor/viewer、SSE、取消和显式重试；项目列表
  显示 owner 与最近 Run，viewer 页面隐藏写操作；
- Celery 消息绑定 Attempt 编号，重复/过期投递幂等退出；控制层可重新投递停滞 outbox，并把超时
  演示任务以 `worker.lost` 失败原因落库；
- 已实现 `stage-1-mp-offline-v1`：Dataset 模型/API、真实核心 loader、脱敏 provenance、流式大文件
  发布、Dataset 页面和独立 CPU 队列；
- 已实现 `stage-1-wbm-upload-v1`：白名单 multipart 流式隔离、大小/SHA 二次核验、严格 WBM schema/
  summary 对齐、原始输入与规范 DataFrame 发布、WBM Dataset 页面，以及成功/取消清理隔离副本；
- 已实现 `stage-1a-composition-v1`：冻结 Dataset Artifact ID/SHA 与参数，物化后复核完整性，调用核心
  二元/三元组成筛选并发布候选 CSV/provenance；前端可从 Dataset 详情创建草稿，Run 页显示冻结
  参数，并通过同项目鉴权的 1--100 行只读接口预览候选、跳转完整 CSV；
- 已实现 `stage-2-condensation-v1`：同时冻结规范 Dataset、候选 CSV/provenance 的 Artifact ID/SHA，
  按 1--100 条分批调用核心 condense，批边界写检查点/进度 Event/取消检查；失败重试跳过已完成
  JSON，逐材料错误进入失败清单，成功后发布 ZIP、index、failures、manifest 和 provenance；
- 科学 Run 创建时冻结核心版本、部署修订和源码 SHA；ready、启动与 Worker prepare 三处复核，
  身份变化时拒绝写入旧 Run；
- 当前验证基线为核心 172 项、Web 后端 54 项 pytest、前端 1 项 Vitest 和四宽度
  20 项 Playwright；Stage 2 Run 另经真实 Robocrys 两结构运行和 1440 视觉检查；
- demo JSON 的 `scientific_status` 为 `not_applicable`，不能描述为科研结果；
- 未实现在线 MP、Stage 3--11 Web StageRunner、正式 OIDC、GPU、MACE、Phonopy、
  Slurm 或 AiiDA；
- 下一步是实现 Stage 3 structure-match StageRunner，把 composition 候选与 Stage 2 ZIP/manifest
  汇合为结构环境分组。
