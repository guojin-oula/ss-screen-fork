import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { ArrowRight, Database, FlaskConical, Upload } from "lucide-react";
import { getDatasets, getProject, getRuns } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";

export function ProjectPage() {
  const { projectId } = useParams({ from: "/projects/$projectId" });
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => getProject(projectId) });
  const runs = useQuery({ queryKey: ["runs", projectId], queryFn: () => getRuns(projectId) });
  const datasets = useQuery({ queryKey: ["datasets", projectId], queryFn: () => getDatasets(projectId) });
  if (project.isLoading || runs.isLoading || datasets.isLoading) return <LoadingState />;
  if (project.isError) return <ErrorState error={project.error} />;
  if (runs.isError) return <ErrorState error={runs.error} />;
  if (datasets.isError) return <ErrorState error={datasets.error} />;
  if (!project.data || !runs.data || !datasets.data) return <LoadingState />;
  const projectData = project.data;
  const runRows = runs.data;
  const datasetRows = datasets.data;
  const canWrite = projectData.role !== "viewer";

  return <section className="page">
    <header className="page-header"><div><p className="eyebrow">PROJECT</p><h1>{projectData.name}</h1><p>{projectData.description || "未填写项目描述。"}</p></div>{canWrite && <div className="header-actions"><Link className="primary-button" to="/projects/$projectId/datasets/new" params={{ projectId }}><Database aria-hidden="true" />准备数据集</Link><Link className="secondary-button" to="/projects/$projectId/datasets/wbm/new" params={{ projectId }}><Upload aria-hidden="true" />上传 WBM</Link><Link className="secondary-button" to="/projects/$projectId/runs/new" params={{ projectId }}><FlaskConical aria-hidden="true" />Demo Run</Link></div>}</header>
    <div className="summary-band"><div><span>当前角色</span><strong>{projectData.role}</strong></div><div><span>数据集</span><strong>{datasetRows.length}</strong></div><div><span>运行数</span><strong>{runRows.length}</strong></div></div>
    <div className="section-heading"><h2>数据集</h2><p>通过 Stage 1 Worker 生成并登记的规范化输入。</p></div>
    {datasetRows.length === 0 ? <EmptyState title="还没有数据集" body="准备 MP 离线数据集以开始真实 Stage 1 流程。" /> : <div className="table-wrap"><table><thead><tr><th>名称</th><th>来源</th><th>记录数</th><th>创建时间</th><th><span className="sr-only">打开</span></th></tr></thead><tbody>{datasetRows.map(dataset => <tr key={dataset.id}><td><strong>{dataset.label}</strong><small className="mono">{dataset.id.slice(0, 12)}</small></td><td>{dataset.kind}</td><td>{dataset.row_count.toLocaleString()}</td><td>{new Date(dataset.created_at).toLocaleString()}</td><td><Link className="icon-link" to="/datasets/$datasetId" params={{ datasetId: dataset.id }} aria-label={`打开数据集 ${dataset.label}`} title="打开数据集"><ArrowRight aria-hidden="true" /></Link></td></tr>)}</tbody></table></div>}
    <div className="section-heading"><h2>运行</h2><p>生命周期状态与科学状态分别记录。</p></div>
    {runRows.length === 0 ? <EmptyState title="还没有 Run" body="创建 Stage 1 数据任务或控制层 Demo。" /> : <div className="table-wrap"><table><thead><tr><th>Run ID</th><th>状态</th><th>Pipeline</th><th>创建时间</th><th><span className="sr-only">打开</span></th></tr></thead><tbody>{runRows.map(run => <tr key={run.id}><td className="mono">{run.id.slice(0, 12)}</td><td><StatusBadge status={run.status} /></td><td>{run.pipeline_version}</td><td>{new Date(run.created_at).toLocaleString()}</td><td><Link className="icon-link" to="/runs/$runId" params={{ runId: run.id }} aria-label={`打开 Run ${run.id}`} title="打开 Run"><ArrowRight aria-hidden="true" /></Link></td></tr>)}</tbody></table></div>}
  </section>;
}
