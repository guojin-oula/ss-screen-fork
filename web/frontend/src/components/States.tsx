import { AlertCircle, Inbox } from "lucide-react";

export function LoadingState({ label = "正在加载" }: { label?: string }) {
  return <div className="state-panel skeleton" role="status" aria-live="polite">{label}</div>;
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return <div className="state-panel"><Inbox aria-hidden="true" /><strong>{title}</strong><p>{body}</p></div>;
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "无法加载数据。";
  return <div className="state-panel state-error" role="alert"><AlertCircle aria-hidden="true" /><strong>请求失败</strong><p>{message}</p></div>;
}

