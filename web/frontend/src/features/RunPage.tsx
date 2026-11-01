import { useEffect, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Ban, Boxes, Download, Play, RefreshCw } from "lucide-react";
import {
  API_BASE_URL,
  cancelRun,
  cancelTask,
  getArtifacts,
  getCompositionPreview,
  getCondensationPreview,
  getProject,
  getRun,
  getTask,
  getTasks,
  retryTask,
  startRun
} from "../api/client";
import { ErrorState, LoadingState } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";

type TimelineEvent = {
  id: number;
  kind: string;
  created_at: string;
  payload: Record<string, unknown>;
};

function text(value: unknown, fallback = "-") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function number(value: unknown) {
  return typeof value === "number" ? value.toLocaleString() : text(value);
}

export function RunPage() {
  const { runId } = useParams({ from: "/runs/$runId" });
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => getRun(runId) });
  const project = useQuery({
    queryKey: ["project", run.data?.project_id],
    queryFn: () => getProject(run.data!.project_id),
    enabled: Boolean(run.data?.project_id)
  });
  const tasks = useQuery({ queryKey: ["tasks", runId], queryFn: () => getTasks(runId) });
  const artifacts = useQuery({
    queryKey: ["artifacts", runId],
    queryFn: () => getArtifacts(runId)
  });
  const taskDetails = useQueries({
    queries: (tasks.data ?? []).map(task => ({
      queryKey: ["task", task.id],
      queryFn: () => getTask(task.id)
    }))
  });
  const isCompositionRun = run.data?.pipeline_version === "stage-1a-composition-v1";
  const isCondensationRun = run.data?.pipeline_version === "stage-2-condensation-v1";
  const compositionPreview = useQuery({
    queryKey: ["composition-preview", runId],
    queryFn: () => getCompositionPreview(runId),
    enabled: isCompositionRun && run.data?.status === "SUCCEEDED"
  });
  const condensationPreview = useQuery({
    queryKey: ["condensation-preview", runId],
    queryFn: () => getCondensationPreview(runId),
    enabled: isCondensationRun
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["run", runId] });
    queryClient.invalidateQueries({ queryKey: ["tasks", runId] });
    queryClient.invalidateQueries({ queryKey: ["artifacts", runId] });
    queryClient.invalidateQueries({ queryKey: ["composition-preview", runId] });
    queryClient.invalidateQueries({ queryKey: ["condensation-preview", runId] });
    taskDetails.forEach(detail => detail.refetch());
  };

  useEffect(() => {
    const stream = new EventSource(`${API_BASE_URL}/api/v1/runs/${runId}/events`);
    stream.onmessage = event => {
      const parsed = JSON.parse(event.data) as TimelineEvent;
      setEvents(current => current.some(item => item.id === parsed.id)
        ? current
        : [...current, parsed]);
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", runId] });
      queryClient.invalidateQueries({ queryKey: ["artifacts", runId] });
      queryClient.invalidateQueries({ queryKey: ["composition-preview", runId] });
      queryClient.invalidateQueries({ queryKey: ["condensation-preview", runId] });
      queryClient.invalidateQueries({ queryKey: ["task"] });
    };
    [
      "run.created",
      "run.status_changed",
      "task.queued",
      "task.status_changed",
      "task.retried",
      "artifact.published",
      "dataset.registered",
      "stage.output_registered",
      "stage.progress",
      "run.cancel_requested",
      "task.cancel_requested"
    ].forEach(kind => stream.addEventListener(kind, stream.onmessage as EventListener));
    return () => stream.close();
  }, [queryClient, runId]);

  const start = useMutation({ mutationFn: () => startRun(runId), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: () => cancelRun(runId), onSuccess: refresh });
  const retry = useMutation({ mutationFn: retryTask, onSuccess: refresh });
  const cancelOne = useMutation({ mutationFn: cancelTask, onSuccess: refresh });

  if (run.isLoading || tasks.isLoading || artifacts.isLoading || (run.data && project.isLoading)) {
    return <LoadingState />;
  }
  if (run.isError) return <ErrorState error={run.error} />;
  if (tasks.isError) return <ErrorState error={tasks.error} />;
  if (artifacts.isError) return <ErrorState error={artifacts.error} />;
  if (project.isError) return <ErrorState error={project.error} />;
  if (!run.data || !tasks.data || !artifacts.data || !project.data) return <LoadingState />;

  const runData = run.data;
  const taskRows = tasks.data;
  const artifactRows = artifacts.data;
  const canWrite = project.data.role !== "viewer";
  const actionError = start.error ?? cancel.error ?? retry.error ?? cancelOne.error;
  const isWBMRun = runData.pipeline_version === "stage-1-wbm-upload-v1";
  const isDatasetRun = runData.pipeline_version === "stage-1-mp-offline-v1" || isWBMRun;
  const scientificRuntime = runData.configuration.scientific_runtime as
    Record<string, unknown> | undefined;
  const candidateArtifact = artifactRows.find(
    artifact => artifact.kind === "composition-candidates"
  );

  return <section className="page">
    <header className="page-header">
      <div>
        <p className="eyebrow">RUN {runData.id.slice(0, 8)}</p>
        <h1>{text(runData.configuration.message, "未命名 Run")}</h1>
        <div className="status-line">
          <StatusBadge status={runData.status} />
          <span>科学状态：{taskRows[0]?.scientific_status ?? "尚无结果"}</span>
        </div>
      </div>
      {canWrite && <div className="header-actions">
        {isCompositionRun && runData.status === "SUCCEEDED" && <Link
          className="primary-button"
          to="/runs/$runId/condensation/new"
          params={{ runId }}
        ><Boxes aria-hidden="true" />生成结构描述</Link>}
        {runData.status === "DRAFT" && <button
          className="primary-button"
          onClick={() => start.mutate()}
          disabled={start.isPending}
        ><Play aria-hidden="true" />{start.isPending ? "启动中…" : "启动"}</button>}
        {["DRAFT", "QUEUED", "RUNNING"].includes(runData.status) && <button
          className="secondary-button"
          onClick={() => cancel.mutate()}
          disabled={cancel.isPending}
        ><Ban aria-hidden="true" />{cancel.isPending ? "取消中…" : "取消"}</button>}
      </div>}
    </header>

    {actionError && <p className="action-error" role="alert">{actionError.message}</p>}

    {isDatasetRun && <div className="configuration-strip">
      <div>
        <span>Pipeline</span>
        <strong>{isWBMRun ? "Stage 1 · WBM upload" : "Stage 1 · MP offline"}</strong>
        <small>Core {text(scientificRuntime?.version)} · {text(scientificRuntime?.revision, "unrecorded")}</small>
      </div>
      <div><span>数据集</span><strong>{text(runData.configuration.dataset_label)}</strong></div>
      <div><span>最大 e_hull</span><strong>{text(runData.configuration.max_e_hull)} eV/atom</strong></div>
    </div>}

    {isCompositionRun && <div
      className="configuration-strip composition-configuration"
      aria-label="组成筛选冻结配置"
    >
      <div>
        <span>Pipeline</span>
        <strong>Stage 1a · Composition</strong>
        <small>Core {text(scientificRuntime?.version)} · {text(scientificRuntime?.revision, "unrecorded")}</small>
      </div>
      <div>
        <span>输入 Dataset</span>
        <strong><Link
          to="/datasets/$datasetId"
          params={{ datasetId: text(runData.configuration.dataset_id) }}
        >{text(runData.configuration.dataset_label)}</Link></strong>
        <small className="mono">SHA {text(runData.configuration.dataset_artifact_sha256).slice(0, 12)}…</small>
      </div>
      <div>
        <span>组成类型</span>
        <strong>{runData.configuration.nelems === 3 ? "三元" : "二元"}</strong>
        <small>{text(runData.configuration.nelems)} 种元素</small>
      </div>
      <div><span>最大带隙</span><strong>{text(runData.configuration.max_bandgap)} eV</strong></div>
      <div><span>最大 e_hull</span><strong>{text(runData.configuration.max_e_hull)} eV/atom</strong></div>
      <div>
        <span>分组门槛</span>
        <strong>≥ {text(runData.configuration.min_group_size)} 个成员</strong>
        <small>≥ {text(runData.configuration.min_x_elements)} 种 X 元素</small>
      </div>
    </div>}

    {isCondensationRun && <div
      className="configuration-strip composition-configuration"
      aria-label="结构描述冻结配置"
    >
      <div>
        <span>Pipeline</span>
        <strong>Stage 2 · Condensation</strong>
        <small>Core {text(scientificRuntime?.version)} · {text(scientificRuntime?.revision, "unrecorded")}</small>
      </div>
      <div>
        <span>来源组成 Run</span>
        <strong><Link
          to="/runs/$runId"
          params={{ runId: text(runData.configuration.composition_run_id) }}
        >{text(runData.configuration.composition_run_id).slice(0, 12)}</Link></strong>
        <small className="mono">SHA {text(runData.configuration.candidate_artifact_sha256).slice(0, 12)}…</small>
      </div>
      <div>
        <span>冻结 Dataset</span>
        <strong><Link
          to="/datasets/$datasetId"
          params={{ datasetId: text(runData.configuration.dataset_id) }}
        >{text(runData.configuration.dataset_label)}</Link></strong>
        <small className="mono">SHA {text(runData.configuration.dataset_artifact_sha256).slice(0, 12)}…</small>
      </div>
      <div><span>候选材料</span><strong>{number(runData.configuration.candidate_count)}</strong></div>
      <div><span>每批材料</span><strong>{number(runData.configuration.batch_size)}</strong></div>
      <div><span>恢复策略</span><strong>按材料检查点续跑</strong><small>重试跳过已完成 JSON</small></div>
    </div>}

    <div className="run-grid">
      <div className="run-main">
        <div className="section-heading">
          <h2>Task</h2><p aria-live="polite">数据库权威状态，经 SSE 更新。</p>
        </div>
        <div className="table-wrap"><table><thead><tr>
          <th>阶段</th><th>生命周期</th><th>科学状态</th><th>Attempt</th><th>操作</th>
        </tr></thead><tbody>
          {taskRows.length === 0
            ? <tr><td colSpan={5}>启动 Run 后创建 Task。</td></tr>
            : taskRows.map((task, index) => {
              const detail = taskDetails[index]?.data;
              return <tr key={task.id}>
                <td><strong>{task.task_type}</strong><small className="mono">{task.id.slice(0, 12)}</small></td>
                <td><StatusBadge status={task.status} /></td>
                <td>{task.scientific_status ?? "-"}</td>
                <td>{detail?.attempts.map(attempt => <span className="attempt" key={attempt.id}>
                  #{attempt.number} {attempt.status}
                  {attempt.error_code && <small>{attempt.error_code}</small>}
                </span>) ?? "-"}</td>
                <td><div className="row-actions">
                  {canWrite && task.status === "FAILED" && <button
                    className="icon-button"
                    onClick={() => retry.mutate(task.id)}
                    disabled={retry.isPending}
                    aria-label="重试 Task"
                    title="重试"
                  ><RefreshCw aria-hidden="true" /></button>}
                  {canWrite && ["QUEUED", "RUNNING"].includes(task.status) && <button
                    className="icon-button"
                    onClick={() => cancelOne.mutate(task.id)}
                    disabled={cancelOne.isPending}
                    aria-label="取消 Task"
                    title="取消"
                  ><Ban aria-hidden="true" /></button>}
                </div></td>
              </tr>;
            })}
        </tbody></table></div>

        {isCompositionRun && <section aria-labelledby="candidate-preview-heading">
          <div className="section-heading">
            <h2 id="candidate-preview-heading">候选预览</h2>
            <p>最多显示前 20 条；完整 CSV 仍是权威制品。</p>
          </div>
          {runData.status !== "SUCCEEDED"
            ? <div className="preview-placeholder">
              <strong>尚无候选结果</strong>
              <span>{runData.status === "DRAFT" ? "启动 Run 后生成。" : "任务完成并校验制品后显示。"}</span>
            </div>
            : compositionPreview.isLoading
              ? <div className="preview-placeholder" aria-live="polite">
                <strong>正在读取候选预览…</strong>
              </div>
              : compositionPreview.isError
                ? <p className="action-error" role="alert">
                  候选预览暂不可用：{compositionPreview.error.message}
                </p>
                : compositionPreview.data && <>
                  <div className="preview-summary">
                    <div><span>候选总数</span><strong>{compositionPreview.data.total_rows.toLocaleString()}</strong></div>
                    <div><span>当前显示</span><strong>{compositionPreview.data.candidates.length.toLocaleString()}</strong></div>
                    {candidateArtifact && <Link
                      className="secondary-button"
                      to="/artifacts/$artifactId"
                      params={{ artifactId: candidateArtifact.id }}
                    >查看完整 CSV</Link>}
                  </div>
                  {compositionPreview.data.candidates.length === 0
                    ? <div className="preview-placeholder">
                      <strong>0 条候选</strong>
                      <span>这是合法科学结果；可返回 Dataset 调整阈值后创建新 Run。</span>
                    </div>
                    : <div className="table-wrap candidate-table"><table><thead><tr>
                      <th>模板</th><th>材料 ID</th><th>X 元素</th><th>化学式</th>
                      <th>组成</th><th>带隙</th><th>e_hull</th><th>来源</th>
                    </tr></thead><tbody>
                      {compositionPreview.data.candidates.map((candidate, index) => <tr
                        key={`${candidate.material_id}-${index}`}
                      >
                        <td><strong>{candidate.template}</strong></td>
                        <td className="mono">{candidate.material_id}</td>
                        <td>{candidate.x_element}</td>
                        <td>{candidate.formula}</td>
                        <td>{candidate.composition}</td>
                        <td>{number(candidate.band_gap)} eV</td>
                        <td>{number(candidate.e_hull)} eV/atom</td>
                        <td>{candidate.source}</td>
                      </tr>)}
                    </tbody></table></div>}
                </>}
        </section>}

        {isCondensationRun && <section aria-labelledby="condensation-progress-heading">
          <div className="section-heading">
            <h2 id="condensation-progress-heading">结构凝聚进度</h2>
            <p>逐批写检查点；单材料错误保留在失败清单。</p>
          </div>
          {condensationPreview.isLoading
            ? <div className="preview-placeholder" aria-live="polite"><strong>正在读取进度…</strong></div>
            : condensationPreview.isError
              ? <p className="action-error" role="alert">进度暂不可用：{condensationPreview.error.message}</p>
              : condensationPreview.data && <>
                <div className="condensation-summary" aria-live="polite">
                  <div><span>总数</span><strong>{number(condensationPreview.data.total)}</strong></div>
                  <div><span>已处理</span><strong>{number(condensationPreview.data.completed)}</strong></div>
                  <div><span>成功</span><strong>{number(condensationPreview.data.succeeded)}</strong></div>
                  <div><span>本次写入</span><strong>{number(condensationPreview.data.written)}</strong></div>
                  <div><span>检查点跳过</span><strong>{number(condensationPreview.data.skipped)}</strong></div>
                  <div className={condensationPreview.data.failed > 0 ? "metric-danger" : ""}><span>失败</span><strong>{number(condensationPreview.data.failed)}</strong></div>
                </div>
                <div className="progress-track" role="progressbar"
                  aria-label="结构凝聚进度"
                  aria-valuemin={0}
                  aria-valuemax={condensationPreview.data.total}
                  aria-valuenow={condensationPreview.data.completed}
                ><span style={{ width: `${condensationPreview.data.total === 0 ? 100 : Math.min(100, condensationPreview.data.completed / condensationPreview.data.total * 100)}%` }} /></div>
                <p className="progress-caption">Attempt #{condensationPreview.data.attempt} · 批次 {condensationPreview.data.batch}/{condensationPreview.data.batches}</p>
                {condensationPreview.data.failures.length > 0 && <>
                  <div className="section-heading compact-heading"><h3>失败材料</h3><p>最多显示前 20 条；完整 CSV 在制品区。</p></div>
                  <div className="table-wrap failure-table"><table><thead><tr>
                    <th>材料 ID</th><th>状态</th><th>错误</th>
                  </tr></thead><tbody>{condensationPreview.data.failures.map(failure => <tr key={failure.material_id}>
                    <td className="mono">{failure.material_id}</td><td><StatusBadge status={failure.status} /></td><td>{failure.error}</td>
                  </tr>)}</tbody></table></div>
                </>}
              </>}
        </section>}

        <div className="section-heading">
          <h2>Artifacts</h2>
          <p>{isDatasetRun
            ? "规范数据与 provenance 由 StageRunner 验证后发布。"
            : isCompositionRun
              ? "完整候选 CSV 与 provenance 均为不可变制品。"
              : isCondensationRun
                ? "ZIP、逐材料索引、失败清单、manifest 与 provenance 均为不可变制品。"
              : "demo JSON 仅验证控制层，不是科研结果。"}</p>
        </div>
        <div className="artifact-list">
          {artifactRows.length === 0
            ? <p className="muted">任务完成后显示制品。</p>
            : artifactRows.map(artifact => <div className="artifact-row" key={artifact.id}>
              <div><strong>{artifact.filename}</strong><small className="mono">SHA-256 {artifact.sha256}</small></div>
              <span>{artifact.size_bytes.toLocaleString()} B</span>
              <Link
                className="icon-link"
                to="/artifacts/$artifactId"
                params={{ artifactId: artifact.id }}
                aria-label={`查看 ${artifact.filename}`}
                title="查看制品"
              ><Download aria-hidden="true" /></Link>
            </div>)}
        </div>
      </div>

      <aside className="event-panel">
        <div className="section-heading"><h2>事件</h2><p>本次连接收到 {events.length} 条</p></div>
        <ol aria-live="polite">
          {events.length === 0
            ? <li className="muted">等待新事件</li>
            : [...events].reverse().map(event => <li key={event.id}>
              <span>{event.kind}</span>
              <time>{new Date(event.created_at).toLocaleTimeString()}</time>
              <small>Event #{event.id}</small>
            </li>)}
        </ol>
      </aside>
    </div>
  </section>;
}
