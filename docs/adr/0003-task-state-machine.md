# ADR-0003: 数据库权威任务状态机

- 状态：已接受
- 日期：2026-08-27

## 决策

Run、Task 和 Attempt 状态由 PostgreSQL 记录，Celery result backend 不构成业务事实。合法转换
集中定义在 `domain/transitions.py`；每次转换和 Event 在同一事务提交。Run/Task 使用乐观锁，
重试创建新 Attempt，旧 Attempt 和 Artifact 保持不变。每条投递消息绑定明确的 Attempt 编号，
而不是在 Worker 端隐式选择“最新一次”。

## 结果

Router 和 Worker 只能调用集中状态规则。入队通过事务 outbox 登记，dispatcher 可重放失败消息；
Worker 按 Task ID 和 Attempt 编号重读权威状态，并对重复或过期投递幂等退出。控制层定期把长时间
停留在 `PUBLISHED`、但数据库任务仍为 `QUEUED` 的 outbox 消息重新置为待投递，并把失去 Worker
心跳语义、长期停留在 `RUNNING` 的任务标记为 `worker.lost`，使异常退出可以审计和恢复。短 demo
与长时间 Stage 1 Dataset 使用各自的服务端失联阈值，避免用控制任务时限误杀真实数据导出。
