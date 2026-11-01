import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowRight, Plus, X } from "lucide-react";
import { createProject, getProjects } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";

export function ProjectsPage() {
  const [dialog, setDialog] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const create = useMutation({
    mutationFn: () => createProject({ name: name.trim(), description: description.trim() }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["projects"] }); setDialog(false); setName(""); setDescription(""); }
  });
  const projectRows = projects.data ?? [];
  return <section className="page">
    <header className="page-header"><div><p className="eyebrow">CONTROL PLANE</p><h1>项目</h1><p>隔离运行、权限与科研制品的顶层工作区。</p></div><button className="primary-button" onClick={() => setDialog(true)}><Plus aria-hidden="true" />新建项目</button></header>
    {projects.isLoading ? <LoadingState /> : projects.isError ? <ErrorState error={projects.error} /> : projectRows.length === 0 ? <EmptyState title="还没有项目" body="创建第一个项目来运行控制层示例。" /> :
      <div className="table-wrap"><table><thead><tr><th>项目</th><th>Owner</th><th>角色</th><th>最近 Run</th><th>更新时间</th><th><span className="sr-only">操作</span></th></tr></thead><tbody>{projectRows.map(project => <tr key={project.id}><td><strong>{project.name}</strong><small>{project.description || "无描述"}</small></td><td>{project.owner_display_name ?? "-"}</td><td>{project.role}</td><td>{project.latest_run_id && project.latest_run_status ? <Link className="status-link" to="/runs/$runId" params={{ runId: project.latest_run_id }} aria-label={`打开最近 Run ${project.latest_run_id}`}><StatusBadge status={project.latest_run_status} /></Link> : <span className="muted">尚无 Run</span>}</td><td>{new Date(project.updated_at).toLocaleString()}</td><td><Link className="icon-link" to="/projects/$projectId" params={{ projectId: project.id }} aria-label={`打开项目 ${project.name}`} title="打开项目"><ArrowRight /></Link></td></tr>)}</tbody></table></div>}
    {dialog && <div className="modal-layer" role="presentation"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="new-project-title"><header><h2 id="new-project-title">新建项目</h2><button className="icon-button" onClick={() => setDialog(false)} aria-label="关闭" title="关闭"><X /></button></header><form onSubmit={event => { event.preventDefault(); create.mutate(); }}><label htmlFor="project-name">项目名称</label><input id="project-name" value={name} onChange={event => setName(event.target.value)} required maxLength={200} autoFocus /><label htmlFor="project-description">描述</label><textarea id="project-description" value={description} onChange={event => setDescription(event.target.value)} maxLength={4000} rows={4} />{create.isError && <p className="field-error" role="alert">{create.error.message}</p>}<footer><button type="button" className="secondary-button" onClick={() => setDialog(false)}>取消</button><button className="primary-button" disabled={!name.trim() || create.isPending}>{create.isPending ? "创建中" : "创建"}</button></footer></form></div></div>}
  </section>;
}
