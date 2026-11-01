# ADR-0007：Stage 1a 使用 Dataset Artifact 作为冻结输入

日期：2026-09-01

## 决策

组成筛选 Run 只接受同一 Project 内已登记的 MP/WBM Dataset。创建 Run 时冻结 Dataset ID、规范 DataFrame Artifact ID/SHA-256、全部阈值、默认排除元素和科学核心身份；不接受客户端路径或 Artifact key。

Worker 从 PostgreSQL 解析受信逻辑 key，在 Attempt sandbox 中流式物化并重新核验大小/SHA，然后调用核心 `screen_composition_candidates`。输出为不可变 `composition-candidates.csv` 与 provenance JSON，作为 Run Artifact 而不是新的 Dataset；零候选是有效终态。

## 后果

- Dataset 保持“外部/规范化数据源登记”的语义，Stage 1a 转换结果不污染 Dataset 列表。
- Stage 2 可通过来源 Run 与 Artifact ID/SHA 引用候选，形成连续审计链。
- 通用 worker 生命周期显式区分 `register_dataset` 和科学状态，继续复用取消、重试、原子发布及失联恢复。
