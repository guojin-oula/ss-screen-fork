import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { Boxes, CheckCircle2 } from "lucide-react";
import {
  createCondensationRun,
  getCompositionPreview,
  getRun
} from "../api/client";
import { ErrorState, LoadingState } from "../components/States";

export function NewCondensationPage() {
  const { runId } = useParams({ from: "/runs/$runId/condensation/new" });
  const navigate = useNavigate();
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => getRun(runId) });
  const preview = useQuery({
    queryKey: ["composition-preview", runId],
    queryFn: () => getCompositionPreview(runId, 1)
  });
  const [batchSize, setBatchSize] = useState("16");
  const parsedBatchSize = Number(batchSize);
  const valid = Number.isInteger(parsedBatchSize)
    && parsedBatchSize >= 1
    && parsedBatchSize <= 100;
  const mutation = useMutation({
    mutationFn: () => createCondensationRun(run.data!.project_id, {
      composition_run_id: runId,
      batch_size: parsedBatchSize
    }),
    onSuccess: created => navigate({ to: "/runs/$runId", params: { runId: created.id } })
  });

  if (run.isLoading || preview.isLoading) return <LoadingState />;
  if (run.isError) return <ErrorState error={run.error} />;
  if (preview.isError) return <ErrorState error={preview.error} />;
  if (!run.data || !preview.data) return <LoadingState />;

  return <section className="page narrow-page">
    <header className="page-header"><div>
      <p className="eyebrow">STAGE 2 · CONDENSATION</p>
      <h1>生成结构描述</h1>
      <p>用 Robocrys 将候选结构批量凝聚为可审计的逐材料 JSON。</p>
    </div></header>
    <form className="form-surface" onSubmit={event => {
      event.preventDefault();
      mutation.mutate();
    }}>
      <div className="form-symbol"><Boxes aria-hidden="true" /></div>
      <div className="source-summary">
        <span>冻结输入</span>
        <strong>{String(run.data.configuration.message ?? "组成筛选")}</strong>
        <small><CheckCircle2 aria-hidden="true" />成功 Run · {preview.data.total_rows.toLocaleString()} 条候选 · Dataset 与候选 Artifact SHA-256 将同时冻结</small>
      </div>
      <label htmlFor="condensation-batch-size">每批材料数</label>
      <input
        id="condensation-batch-size"
        type="number"
        min="1"
        max="100"
        step="1"
        value={batchSize}
        onChange={event => setBatchSize(event.target.value)}
        required
      />
      <small className="form-help">每批完成后写入检查点并检查取消请求。Task 因基础设施故障重试时，已校验的结构会被跳过；单个材料的科学错误会进入失败清单。</small>
      {preview.data.total_rows === 0 && <p className="notice">此组成 Run 有 0 条候选。仍可创建 Stage 2，以生成完整的空结果 provenance。</p>}
      {!valid && <p className="field-error">每批材料数必须是 1–100 的整数。</p>}
      {mutation.isError && <p className="field-error" role="alert">{mutation.error.message}</p>}
      <button className="primary-button" disabled={!valid || mutation.isPending}>
        {mutation.isPending ? "创建中…" : "创建结构描述草稿"}
      </button>
    </form>
  </section>;
}
