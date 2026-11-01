import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import { FlaskConical } from "lucide-react";
import { createRun } from "../api/client";

export function NewRunPage() {
  const { projectId } = useParams({ from: "/projects/$projectId/runs/new" });
  const navigate = useNavigate();
  const [message, setMessage] = useState("SS-Screen Web control plane");
  const [simulateFailure, setSimulateFailure] = useState(false);
  const mutation = useMutation({ mutationFn: () => createRun(projectId, { message, simulate_failure: simulateFailure }), onSuccess: run => navigate({ to: "/runs/$runId", params: { runId: run.id } }) });
  return <section className="page narrow-page"><header className="page-header"><div><p className="eyebrow">NEW RUN</p><h1>控制层示例</h1><p>生成小型确定性 JSON，用于验证编排、审计和制品链。</p></div></header><form className="form-surface" onSubmit={event => { event.preventDefault(); mutation.mutate(); }}><div className="form-symbol"><FlaskConical aria-hidden="true" /></div><label htmlFor="run-message">制品消息</label><input id="run-message" value={message} onChange={event => setMessage(event.target.value)} required maxLength={500} /><label className="checkbox-row"><input type="checkbox" checked={simulateFailure} onChange={event => setSimulateFailure(event.target.checked)} /><span><strong>首次 Attempt 模拟失败</strong><small>用于验证显式重试，不代表科学计算失败。</small></span></label>{mutation.isError && <p className="field-error" role="alert">{mutation.error.message}</p>}<button className="primary-button" disabled={mutation.isPending}>{mutation.isPending ? "创建中" : "创建草稿 Run"}</button></form></section>;
}

