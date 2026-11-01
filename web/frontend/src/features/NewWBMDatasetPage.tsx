import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { ShieldCheck, Upload } from "lucide-react";
import { createWBMUploadRun } from "../api/client";

function fileSize(file?: File) {
  if (!file) return "未选择";
  if (file.size < 1024) return `${file.size} B`;
  return `${(file.size / 1024 / 1024).toFixed(2)} MiB`;
}

export function NewWBMDatasetPage() {
  const { projectId } = useParams({ from: "/projects/$projectId/datasets/wbm/new" });
  const navigate = useNavigate();
  const [label, setLabel] = useState("WBM uploaded materials");
  const [xyzFile, setXyzFile] = useState<File>();
  const [summaryFile, setSummaryFile] = useState<File>();
  const mutation = useMutation({
    mutationFn: () => createWBMUploadRun(projectId, {
      datasetLabel: label.trim(), xyzFile: xyzFile!, summaryFile
    }),
    onSuccess: run => navigate({ to: "/runs/$runId", params: { runId: run.id } })
  });

  return <section className="page narrow-page">
    <header className="page-header"><div><p className="eyebrow">STAGE 1 · WBM UPLOAD</p><h1>上传 WBM 数据集</h1><p>文件先进入不可执行隔离区，CPU Worker 校验哈希、结构与字段后才会发布。</p></div></header>
    <form className="form-surface" onSubmit={event => { event.preventDefault(); mutation.mutate(); }}>
      <div className="form-symbol"><Upload aria-hidden="true" /></div>
      <div className="source-summary" aria-label="安全处理说明"><span>处理边界</span><strong>不可信上传 → 隔离区 → 严格校验 → Dataset</strong><small><ShieldCheck aria-hidden="true" /> 浏览器不会提交服务器路径；服务端会再次核验文件大小与 SHA-256。</small></div>
      <label htmlFor="wbm-label">数据集名称</label>
      <input id="wbm-label" value={label} onChange={event => setLabel(event.target.value)} required maxLength={200} />
      <label htmlFor="wbm-xyz">WBM 结构文件</label>
      <input id="wbm-xyz" type="file" accept=".xyz,.extxyz,chemical/x-xyz" required onChange={event => setXyzFile(event.target.files?.[0])} aria-describedby="wbm-xyz-help" />
      <small id="wbm-xyz-help" className="form-help">仅接受 .xyz / .extxyz。每条结构必须提供 WBM_gap 与 WBM_e_hull，或由下方摘要文件补齐。</small>
      <div className="file-selection"><span>{xyzFile?.name ?? "尚未选择结构文件"}</span><small>{fileSize(xyzFile)}</small></div>
      <label htmlFor="wbm-summary">摘要文件（可选）</label>
      <input id="wbm-summary" type="file" accept=".csv,.tsv,text/csv,text/tab-separated-values" onChange={event => setSummaryFile(event.target.files?.[0])} aria-describedby="wbm-summary-help" />
      <small id="wbm-summary-help" className="form-help">摘要行数必须与结构数一致；存在 material_id 或 WBM_idx 时会逐行核对。</small>
      {summaryFile && <div className="file-selection"><span>{summaryFile.name}</span><small>{fileSize(summaryFile)}</small></div>}
      {mutation.isError && <p className="field-error" role="alert">{mutation.error.message}</p>}
      <button className="primary-button" disabled={!label.trim() || !xyzFile || mutation.isPending}>{mutation.isPending ? "上传中…" : "上传并创建草稿"}</button>
    </form>
  </section>;
}
