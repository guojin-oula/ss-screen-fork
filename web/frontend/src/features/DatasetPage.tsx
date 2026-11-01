import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Database, FileJson, Fingerprint, TableProperties } from "lucide-react";
import { getDataset, getProject } from "../api/client";
import { ErrorState, LoadingState } from "../components/States";

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? value as Record<string, unknown> : {};
}

export function DatasetPage() {
  const { datasetId } = useParams({ from: "/datasets/$datasetId" });
  const dataset = useQuery({ queryKey: ["dataset", datasetId], queryFn: () => getDataset(datasetId) });
  const project = useQuery({ queryKey: ["project", dataset.data?.project_id], queryFn: () => getProject(dataset.data!.project_id), enabled: Boolean(dataset.data?.project_id) });
  if (dataset.isLoading || (dataset.data && project.isLoading)) return <LoadingState />;
  if (dataset.isError) return <ErrorState error={dataset.error} />;
  if (project.isError) return <ErrorState error={project.error} />;
  if (!dataset.data || !project.data) return <LoadingState />;
  const data = dataset.data;
  const isWBM = data.kind === "wbm-upload";
  const database = record(data.provenance.database);
  const query = record(data.provenance.query);
  const hullRange = record(query.energy_above_hull_eV_per_atom);
  const inputs = record(data.provenance.inputs);
  const structures = record(inputs.structures);
  const summary = record(inputs.summary);
  const execution = record(data.provenance.execution);
  const core = record(execution.scientific_core);

  return <section className="page narrow-page">
    <header className="page-header"><div><p className="eyebrow">DATASET</p><h1>{data.label}</h1><p>Stage 1 规范化数据集，可按来源 Run 和不可变制品反向审计。</p></div><div className="header-actions">{project.data.role !== "viewer" && <Link className="primary-button" to="/datasets/$datasetId/composition/new" params={{ datasetId }}>组成筛选</Link>}<Link className="secondary-button" to="/runs/$runId" params={{ runId: data.source_run_id }}>查看来源 Run</Link></div></header>
    <div className="summary-band dataset-summary"><div><span>材料记录</span><strong>{data.row_count.toLocaleString()}</strong></div><div><span>来源</span><strong>{data.kind}</strong></div><div><span>{isWBM ? "输入文件" : "最大 e_hull"}</span><strong>{isWBM ? (summary.filename ? "结构 + 摘要" : "结构文件") : `${String(hullRange.max ?? "-")} eV/atom`}</strong></div></div>
    <dl className="metadata-list">
      <div><dt><Database aria-hidden="true" />{isWBM ? "上传输入" : "快照引用"}</dt><dd>{isWBM ? String(structures.filename ?? "-") : String(database.reference ?? "-")}<small className="mono hash">SHA-256 {String(isWBM ? structures.sha256 ?? "-" : database.sha256 ?? "-")}</small>{isWBM && Boolean(summary.filename) && <small>摘要：{String(summary.filename)} · SHA-256 {String(summary.sha256)}</small>}</dd></div>
      <div><dt><Fingerprint aria-hidden="true" />科学核心</dt><dd>SS-Screen {String(core.version ?? "-")}<small>{String(core.revision ?? "未记录修订标识")}</small><small className="mono hash">Source SHA-256 {String(core.source_sha256 ?? "-")}</small></dd></div>
      <div><dt><TableProperties aria-hidden="true" />规范数据</dt><dd><Link to="/artifacts/$artifactId" params={{ artifactId: data.artifact_id }}>查看并下载 {isWBM ? "wbm.df" : "mp.df"}</Link><small>仅在可信的 SS-Screen Python 环境中加载 pickle。</small></dd></div>
      <div><dt><FileJson aria-hidden="true" />Provenance</dt><dd><Link to="/artifacts/$artifactId" params={{ artifactId: data.provenance_artifact_id }}>查看 provenance JSON</Link></dd></div>
      <div><dt>创建时间</dt><dd>{new Date(data.created_at).toLocaleString()}</dd></div>
    </dl>
    <p className="notice">{isWBM ? "原始上传已通过大小、SHA-256、结构格式、必需数值字段及摘要对齐校验；provenance 不暴露服务器存储路径。" : "离线快照的覆盖范围固定于显示的 SHA-256，不代表当前在线 Materials Project 的完整覆盖。"}</p>
  </section>;
}
