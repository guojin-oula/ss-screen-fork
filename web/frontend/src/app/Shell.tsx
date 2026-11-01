import { FlaskConical, FolderKanban, Menu, PanelLeftClose, X } from "lucide-react";
import { useState } from "react";
import { Link, Outlet } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { getLive, getMe } from "../api/client";

export function Shell() {
  const [open, setOpen] = useState(false);
  const me = useQuery({ queryKey: ["me"], queryFn: getMe });
  const live = useQuery({ queryKey: ["live"], queryFn: getLive, refetchInterval: 30000 });
  return (
    <div className="app-shell">
      <button className="mobile-menu icon-button" onClick={() => setOpen(true)} aria-label="打开导航" title="打开导航"><Menu /></button>
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`} aria-label="主导航">
        <div className="brand"><FlaskConical aria-hidden="true" /><span><strong>SS-Screen</strong><small>Research operations</small></span></div>
        <button className="sidebar-close icon-button" onClick={() => setOpen(false)} aria-label="关闭导航" title="关闭导航"><X /></button>
        <nav>
          <Link to="/projects" activeProps={{ className: "active" }} onClick={() => setOpen(false)}><FolderKanban aria-hidden="true" />项目</Link>
        </nav>
        <div className="sidebar-status">
          <span className={`health-dot ${live.isSuccess ? "online" : "offline"}`} aria-hidden="true" />
          <span>{live.isSuccess ? "API 正常" : "API 未连接"}</span>
        </div>
        <div className="identity"><PanelLeftClose aria-hidden="true" /><span>{me.data?.display_name ?? "开发身份"}<small>受限本地身份</small></span></div>
      </aside>
      {open && <button className="scrim" onClick={() => setOpen(false)} aria-label="关闭导航遮罩" />}
      <main className="workspace"><Outlet /></main>
    </div>
  );
}

