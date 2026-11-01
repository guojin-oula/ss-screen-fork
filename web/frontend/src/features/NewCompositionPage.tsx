import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { Filter } from "lucide-react";
import { createCompositionRun, getDataset } from "../api/client";
import { ErrorState, LoadingState } from "../components/States";

export function NewCompositionPage() {
  const { datasetId } = useParams({ from: "/datasets/$datasetId/composition/new" });
  const navigate = useNavigate();
  const dataset = useQuery({ queryKey: ["dataset", datasetId], queryFn: () => getDataset(datasetId) });
  const [nelems, setNelems] = useState("2");
  const [maxBandgap, setMaxBandgap] = useState("1.0");
  const [maxEHull, setMaxEHull] = useState("0.01");
  const [minGroupSize, setMinGroupSize] = useState("2");
  const [minXElements, setMinXElements] = useState("2");
  const values = [maxBandgap, maxEHull, minGroupSize, minXElements].map(Number);
  const valid = values.every(Number.isFinite) && values.every(value => value >= 0)
    && Number(minGroupSize) >= 2 && Number(minXElements) >= 2
    && Number(minXElements) <= Number(minGroupSize);
  const mutation = useMutation({
    mutationFn: () => createCompositionRun(dataset.data!.project_id, {
      dataset_id: datasetId,
      nelems: Number(nelems),
      max_bandgap: Number(maxBandgap),
      max_e_hull: Number(maxEHull),
      min_group_size: Number(minGroupSize),
      min_x_elements: Number(minXElements)
    }),
    onSuccess: run => navigate({ to: "/runs/$runId", params: { runId: run.id } })
  });
  if (dataset.isLoading) return <LoadingState />;
  if (dataset.isError) return <ErrorState error={dataset.error} />;
  if (!dataset.data) return <LoadingState />;

  return <section className="page narrow-page">
    <header className="page-header"><div><p className="eyebrow">STAGE 1A · COMPOSITION</p><h1>筛选组成模板</h1><p>从不可变 Dataset 制品生成二元或三元候选，不修改来源数据。</p></div></header>
    <form className="form-surface" onSubmit={event => { event.preventDefault(); mutation.mutate(); }}>
      <div className="form-symbol"><Filter aria-hidden="true" /></div>
      <div className="source-summary"><span>输入 Dataset</span><strong>{dataset.data.label}</strong><small>{dataset.data.kind} · {dataset.data.row_count.toLocaleString()} 条记录 · SHA-256 在 Run 中冻结</small></div>
      <label htmlFor="composition-nelems">组成类型</label>
      <select id="composition-nelems" value={nelems} onChange={event => setNelems(event.target.value)}><option value="2">二元（2 种元素）</option><option value="3">三元（3 种元素）</option></select>
      <label htmlFor="composition-max-gap">最大带隙</label>
      <div className="unit-input"><input id="composition-max-gap" type="number" min="0" max="20" step="0.01" value={maxBandgap} onChange={event => setMaxBandgap(event.target.value)} required /><span>eV</span></div>
      <label htmlFor="composition-max-hull">最大能量高于凸包值</label>
      <div className="unit-input"><input id="composition-max-hull" type="number" min="0" max="1" step="0.001" value={maxEHull} onChange={event => setMaxEHull(event.target.value)} required /><span>eV/atom</span></div>
      <details className="advanced-fields"><summary>高级分组条件</summary><div><label htmlFor="composition-min-group">模板最少成员数</label><input id="composition-min-group" type="number" min="2" max="1000" value={minGroupSize} onChange={event => setMinGroupSize(event.target.value)} required /><label htmlFor="composition-min-x">最少不同 X 元素数</label><input id="composition-min-x" type="number" min="2" max="1000" value={minXElements} onChange={event => setMinXElements(event.target.value)} required /></div></details>
      <small className="form-help">服务端会应用版本化默认排除元素列表，并把完整参数、输入 Artifact ID/SHA 和科学核心身份写入 provenance。</small>
      {mutation.isError && <p className="field-error" role="alert">{mutation.error.message}</p>}
      <button className="primary-button" disabled={!valid || mutation.isPending}>{mutation.isPending ? "创建中…" : "创建组成筛选草稿"}</button>
    </form>
  </section>;
}
