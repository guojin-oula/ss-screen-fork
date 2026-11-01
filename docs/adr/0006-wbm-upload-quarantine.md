# ADR-0006：WBM 上传隔离与 Dataset 发布

日期：2026-09-01

## 决策

浏览器只上传 `.xyz`/`.extxyz` 及可选 `.csv`/`.tsv`，不接受服务器文件路径。API 将输入流式写入仓库外 `UPLOADS_QUARANTINE_ROOT`，以不透明 UUID 组成逻辑 key，并记录显示文件名、MIME、字节数和 SHA-256 到草稿 Run configuration。

CPU Worker 从逻辑 key 读取文件，在独立 Attempt sandbox 中重新计算字节数和 SHA-256，然后以核心 `load_wbm_dataset(strict=True)` 校验非空、必需 gap/hull 数值、唯一 ID 及摘要对齐。只有全部验证和 Artifact 发布成功后才登记 Dataset；provenance 记录输入哈希但删除隔离 key/绝对路径，成功后清理隔离副本。

## 理由与后果

- Run configuration 足以作为当前不可变上传 manifest，无需在首个切片增加 Upload 表和 migration。
- 原始输入作为不可变 Artifact 保留，规范化 DataFrame 与 provenance 可反向审计。
- 失败输入暂留用于显式重试；草稿、排队和运行中取消均在数据库终态提交后回收隔离输入。
- 清理采用幂等、尽力而为语义；删除失败写日志但不反转已经提交的取消终态。生产化仍需保留期垃圾回收。
- API、Worker 与反向代理必须同时配置请求大小边界，容器需安装项目的 `wbm` 可选依赖。
