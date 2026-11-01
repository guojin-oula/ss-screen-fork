import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { Download, FileJson, ShieldCheck } from "lucide-react";
import { artifactDownloadUrl, getArtifact } from "../api/client";
import { ErrorState, LoadingState } from "../components/States";

export function ArtifactPage() {
  const { artifactId } = useParams({ from: "/artifacts/$artifactId" });
  const artifact = useQuery({ queryKey: ["artifact", artifactId], queryFn: () => getArtifact(artifactId) });
  if (artifact.isLoading) return <LoadingState />;
  if (artifact.isError) return <ErrorState error={artifact.error} />;
  if (!artifact.data) return <LoadingState />;
  const data = artifact.data;
  const isDemo = data.kind === "control-plane-demo-json";
  const notice = isDemo
    ? "此 JSON 只验证 Web 控制层、队列、审计与下载链，不代表材料筛选或其他科研结论。"
    : data.content_type === "application/x-pandas-pickle"
      ? "此 DataFrame 由 StageRunner 生成；pickle 只能在可信的 SS-Screen Python 环境中加载，并应先核对 SHA-256。"
      : data.kind === "composition-candidates"
        ? "此 CSV 是组成筛选的完整候选表；Run 页面只显示受限预览，下载后仍应按本页 SHA-256 校验。"
        : data.kind === "condensed-structures-archive"
          ? "此 ZIP 包含逐材料 Robocrys 凝聚 JSON；应与同一 Attempt 的 index、失败清单和 provenance 一起使用。"
          : data.kind.startsWith("condensation-")
            ? "此制品属于 Stage 2 结构凝聚输出；逐材料状态与错误是科学结果的一部分，并可按本页 SHA-256 复核。"
        : "此 provenance 记录输入身份、参数边界和软件版本，可用于复核本次运行。";
  return <section className="page narrow-page"><header className="page-header"><div><p className="eyebrow">ARTIFACT</p><h1>{data.filename}</h1><p>不可变制品元数据，可由 SHA-256 验证下载内容。</p></div><a className="primary-button" href={artifactDownloadUrl(artifactId)}><Download aria-hidden="true" />下载</a></header><dl className="metadata-list"><div><dt><FileJson aria-hidden="true" />类型</dt><dd>{data.kind}<small>{data.content_type}</small></dd></div><div><dt><ShieldCheck aria-hidden="true" />SHA-256</dt><dd className="mono hash">{data.sha256}</dd></div><div><dt>大小</dt><dd>{data.size_bytes} B</dd></div><div><dt>Schema</dt><dd>{data.schema_version}</dd></div><div><dt>Attempt</dt><dd className="mono">{data.attempt_id}</dd></div><div><dt>创建时间</dt><dd>{new Date(data.created_at).toLocaleString()}</dd></div></dl><p className="notice">{notice}</p></section>;
}
