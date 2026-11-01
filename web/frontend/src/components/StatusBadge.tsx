import { Ban, CheckCircle2, CircleDot, Clock3, TriangleAlert, XCircle } from "lucide-react";

const statusMeta: Record<string, { label: string; tone: string; Icon: typeof CircleDot }> = {
  DRAFT: { label: "草稿", tone: "neutral", Icon: CircleDot },
  PENDING: { label: "待依赖", tone: "neutral", Icon: Clock3 },
  READY: { label: "可执行", tone: "info", Icon: CircleDot },
  QUEUED: { label: "已排队", tone: "info", Icon: Clock3 },
  RUNNING: { label: "运行中", tone: "active", Icon: CircleDot },
  SUCCEEDED: { label: "已完成", tone: "success", Icon: CheckCircle2 },
  FAILED: { label: "失败", tone: "danger", Icon: XCircle },
  CANCEL_REQUESTED: { label: "取消请求中", tone: "warning", Icon: TriangleAlert },
  CANCELLED: { label: "已取消", tone: "neutral", Icon: Ban }
};

export function StatusBadge({ status }: { status: string }) {
  const meta = statusMeta[status] ?? { label: status, tone: "neutral", Icon: CircleDot };
  return (
    <span className={`status-badge status-${meta.tone}`}>
      <meta.Icon aria-hidden="true" size={15} />
      {meta.label}
    </span>
  );
}

