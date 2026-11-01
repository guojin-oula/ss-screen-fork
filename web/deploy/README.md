# 开发部署

1. 将 `env.example` 复制为本目录 `.env`，只在本地填写真实配置。
2. 确认 `.env` 中 `ARTIFACT_ROOT`、`ATTEMPT_SANDBOX_ROOT` 和 `UPLOADS_QUARANTINE_ROOT`
   均位于 Git 工作区外，并对容器运行 UID 可写。
3. 将 `MP_OFFLINE_DATABASE_HOST_PATH` 指向服务器上的只读 `default.db`，将
   `MP_OFFLINE_PACKAGE_HOST_PATH` 指向含 `src/mp_offline` 的只读包目录，并为快照设置不含路径的
   `MP_OFFLINE_DATABASE_REFERENCE`。
4. 将 `SSSCREEN_CORE_REVISION` 设置为实际部署 Git commit 或发布构建标识；production 不接受
   `development-worktree`。
5. 在提供 Compose 的机器运行 `docker compose --env-file web/deploy/.env -f web/deploy/compose.yaml up --build`。
6. 打开 `http://localhost:5173`；API 健康检查位于 `http://localhost:8000/health/ready`。

当前交接主机没有 Compose 命令。可按 `web/README.md` 使用两个精确命名的临时容器和本地
`.venv`/npm 进程完成等价验证。不要把 Artifact 根目录回退到 Git 工作树。

Compose 将 demo 路由到 `control-worker`，将 Stage 1 MP 离线任务路由到单并发 `cpu-worker`。
SQLite 文件和 `mp_offline` 源目录均以 `:ro` 挂载；前端不会看到或提交这些主机路径。远程主机
上的服务需通过 SSH 同时转发 5173 和 8000 端口，详见 [`web/README.md`](../README.md)。
ready、Run 启动和 CPU Worker 会共同检查核心源码版本与 distribution metadata；Run 冻结版本、
部署修订和源码 SHA-256，部署代码变化后必须创建新 Run。
