import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { Database } from "lucide-react";
import { createMPOfflineDatasetRun } from "../api/client";

export function NewDatasetPage() {
  const { projectId } = useParams({ from: "/projects/$projectId/datasets/new" });
  const navigate = useNavigate();
  const [label, setLabel] = useState("MP stable materials");
  const [maxEHull, setMaxEHull] = useState("0.01");
  const parsedMaxEHull = Number(maxEHull);
  const validThreshold = Number.isFinite(parsedMaxEHull) && parsedMaxEHull >= 0 && parsedMaxEHull <= 1;
  const mutation = useMutation({
    mutationFn: () => createMPOfflineDatasetRun(projectId, {
      dataset_label: label.trim(),
      max_e_hull: parsedMaxEHull
    }),
    onSuccess: run => navigate({ to: "/runs/$runId", params: { runId: run.id } })
  });

  return <section className="page narrow-page">
    <header className="page-header"><div><p className="eyebrow">STAGE 1 · DATASET</p><h1>准备 Materials Project 数据集</h1><p>从管理员配置的只读离线快照生成规范化数据与可审计 provenance。</p></div></header>
    <form className="form-surface" onSubmit={event => { event.preventDefault(); mutation.mutate(); }}>
      <div className="form-symbol"><Database aria-hidden="true" /></div>
      <div className="source-summary" aria-label="数据源说明"><span>数据源</span><strong>服务端 MP 离线快照</strong><small>浏览器不会接收或保存服务器文件路径；最终记录快照 SHA-256。</small></div>
      <label htmlFor="dataset-label">数据集名称</label>
      <input id="dataset-label" value={label} onChange={event => setLabel(event.target.value)} required maxLength={200} />
      <label htmlFor="max-e-hull">最大能量高于凸包值</label>
      <div className="unit-input"><input id="max-e-hull" type="number" value={maxEHull} onChange={event => setMaxEHull(event.target.value)} required min="0" max="1" step="0.001" inputMode="decimal" aria-describedby="max-e-hull-help" /><span>eV/atom</span></div>
      <small id="max-e-hull-help" className="form-help">保留 0 ≤ e_hull ≤ 此值且未被 deprecated 的材料；默认 0.01 eV/atom。</small>
      {mutation.isError && <p className="field-error" role="alert">{mutation.error.message}</p>}
      <button className="primary-button" disabled={!label.trim() || !validThreshold || mutation.isPending}>{mutation.isPending ? "创建中" : "创建 Stage 1 草稿"}</button>
    </form>
  </section>;
}
