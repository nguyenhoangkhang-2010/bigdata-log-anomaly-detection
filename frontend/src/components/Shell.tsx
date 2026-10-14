import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useHealth, useMeta } from "../api/hooks";
import { fmtShort } from "../lib/format";

export const NAV = [
  { to: "/", no: "01", name: "Tổng quan" },
  { to: "/anomalies", no: "02", name: "Bất thường" },
  { to: "/alerts", no: "03", name: "Cảnh báo" },
  { to: "/events", no: "04", name: "Sự kiện" },
  { to: "/models", no: "05", name: "Mô hình" },
  { to: "/logs", no: "06", name: "Nhật ký" },
];

function effectiveTheme(): "light" | "dark" {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function ThemeButton() {
  const [theme, setTheme] = useState<"light" | "dark">(effectiveTheme);
  const flip = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("logad-theme", next); } catch { /* bỏ qua */ }
    setTheme(next);
  };
  return (
    <button className="theme-btn" onClick={flip}>
      {theme === "dark" ? "Giấy sáng" : "Mực tối"}
    </button>
  );
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="nav" aria-label="Mục lục">
      {NAV.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.to === "/"} className="nav__item" onClick={onNavigate}>
          <span className="nav__no">{n.no}</span>
          <span className="nav__name">{n.name}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <NavLink to="/" className="brand" aria-label="LogAD — trang chủ">
      <span className="brand__mark">Log<b>AD</b></span>
    </NavLink>
  );
}

export function Shell() {
  const meta = useMeta();
  const health = useHealth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); window.scrollTo(0, 0); }, [pathname]);

  const here = NAV.find((n) => (n.to === "/" ? pathname === "/" : pathname.startsWith(n.to)));
  const m = meta.data;
  const apiOk = health.data?.status === "ok";

  return (
    <div className="app">
      <aside className="side">
        <div>
          <Brand />
          <p className="label brand__tag">Phát hiện bất thường<br />từ nhật ký hệ thống</p>
        </div>
        <Nav />
        <div className="side__foot">
          <div className="side__src">
            <span className="label">Nguồn dữ liệu</span>
            <span className="v">{m ? m.dataset.name : "…"}</span>
            <span className="v muted">{m ? (m.data_source === "demo" ? "demo · trong bộ nhớ" : "Elasticsearch") : ""}</span>
          </div>
          <ThemeButton />
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <Brand />
          <button className="menu-btn" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? "Đóng" : "Mục lục"}
          </button>
        </div>
        {open && (
          <div className="sheet">
            <Nav onNavigate={() => setOpen(false)} />
            <div style={{ marginTop: 18 }}><ThemeButton /></div>
          </div>
        )}

        {m?.is_synthetic && (
          <div className="synthetic" role="note">
            <i />
            DỮ LIỆU MÔ PHỎNG — dùng để dựng giao diện, chưa phải kết quả của pipeline Spark
          </div>
        )}

        <div className="strip">
          <span className="label">{here ? `Nº ${here.no} — ${here.name}` : "LogAD"}</span>
          <span className="strip__r">
            {m && <span className="label">{fmtShort(m.time_range.start)} → {fmtShort(m.time_range.end)} UTC</span>}
            {m && <span className="label">Lần chạy {m.pipeline_run.id}</span>}
            <span className="label">
              <span className="status-dot" data-ok={health.isError ? "false" : apiOk ? "true" : "pending"} />
              {health.isError ? "API không phản hồi" : apiOk ? "API sẵn sàng" : "Đang kết nối"}
            </span>
          </span>
        </div>

        <main className="page"><div className="page__inner"><Outlet /></div></main>

        <footer className="colophon">
          <div>
            <span className="label">Dữ liệu</span>
            <p>
              {m ? m.dataset.description : "…"}
            </p>
          </div>
          <div>
            <span className="label">Đường ống</span>
            <p>Nhật ký thô → HDFS → Spark (parse, đặc trưng, KMeans) → Elasticsearch → giao diện này.</p>
          </div>
          <div>
            <span className="label">Đồ án</span>
            <p>Đề tài 13 · Nhập môn Big Data<br />Phiên bản {m?.version ?? "…"}</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
