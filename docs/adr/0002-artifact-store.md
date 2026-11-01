# ADR-0002: PostgreSQL 与 ArtifactStore 分工

- 状态：已接受
- 日期：2026-08-27

## 决策

PostgreSQL 保存身份、权限、状态、审计事件、索引和小型 JSON。不可变科学制品保存在仓库外
ArtifactStore，数据库只登记服务端逻辑 key、大小、SHA-256、MIME、schema 和产生 Attempt。
首个适配器是 `FileSystemArtifactStore`，根目录由服务端配置。

## 结果

逻辑 key 不接受用户路径片段；解析后必须留在根目录内。写入采用同目录临时文件、文件
`fsync`、不覆盖既有目标的原子硬链接发布和目录 `fsync`；并发发布同一 key 时只有一个写入者
成功。大型 Stage 1 DataFrame 从 sandbox 发布时按块流式复制并同步计算 SHA-256，禁止把完整
文件一次性读入 Worker 内存。ready 检查会在 Artifact、Attempt sandbox 和上传隔离区分别执行无残留的写入探针，避免
仅凭目录存在误报可用。首轮不开放公开删除；未来 S3/MinIO 适配器保持相同不可变性和授权语义。
