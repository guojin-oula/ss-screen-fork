# ADR-0005: Stage 1 MP 离线 Dataset 垂直切片

- 状态：已接受
- 日期：2026-09-01

## 决策

Phase 2 的首个科学 StageRunner 只实现 Materials Project 离线快照入口，pipeline 名称固定为
`stage-1-mp-offline`、版本为 `stage-1-mp-offline-v1`。浏览器只提交数据集名称和具名阈值
`max_e_hull`；SQLite 路径、快照引用和 `mp_offline` 包位置由服务器配置，不接受任意客户端路径。

CPU Worker 调用科学核心的 `ssscreen.data.mp.load_mp_dataset_offline`，不复制查询或标准化算法。
Runner 依次执行 prepare、execute、validate、publish，并发布两个不可变制品：

- `mp.df`：规范化 pandas DataFrame pickle；
- `mp.df.provenance.json`：数据库 SHA-256/大小、快照引用、查询和包版本。

两个制品成功校验并发布后，才在 PostgreSQL 注册 Dataset，并将 Task 科学状态设为
`dataset_ready`。`control` 与 `cpu` 队列使用独立 exchange/routing key；Stage 1 使用独立的长任务
失联阈值。

科学 Run 创建时冻结 `ss-screen` 源码版本、installed distribution 版本、服务端部署修订标识和
对实际 `ssscreen/**/*.py` 计算的源码 SHA-256。API ready、Run 启动和 Worker prepare 都要求源码
版本与 distribution metadata 一致；Run 创建后的身份变化以稳定错误拒绝执行，不能把新代码结果
写入旧 Run。最终 provenance 保存同一身份与 pipeline 版本。

## 结果

服务器绝对数据库路径不会进入 Run 配置、API 请求、Dataset provenance 或 Artifact；provenance
只公开管理员提供的稳定引用。大型 `mp.df` 通过流式、原子且不覆盖的 ArtifactStore 操作发布。
取消、失败或被新 Attempt 取代时清理本次已发布但未登记的制品；重试保留旧 Attempt 的审计事实。

pandas pickle 只能在可信 Python 环境中加载，UI 必须持续显示该安全提示。离线数据库的 SHA-256
证明使用了哪个快照，但不代表当前在线 Materials Project 的完整覆盖。WBM、用户上传、在线 MP
API 和 Stage 1a composition 不包含在本决策中，后续以独立入口和契约实现。
