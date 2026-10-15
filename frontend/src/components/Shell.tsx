import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useHealth, useMeta } from "../api/hooks";
import { fmtShort } from "../lib/format";

export const NAV = [
  { to: "/", name: "Tổng quan" },
  { to: "/anomalies", name: "Bất thường" },
  { to: "/alerts", name: "Cảnh báo" },
  { to: "/events", name: "Sự kiện" },
  { to: "/models", name: "Mô hình" },
  { to: "/logs", name: "Nhật ký" },
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
  return <button className="theme-btn" onClick={flip} aria-label="Đổi giao diện sáng/tối">{theme === "dark" ? "Sáng" : "Tối"}</button>;
}

const SOURCE_LABEL = {
  demo: "demo · bộ nhớ",
  files: "kết quả pipeline (tệp)",
  elasticsearch: "Elasticsearch",
} as const;

export function Shell() {
  const meta = useMeta();
  const health = useHealth();
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);

  const m = meta.data;
  const apiState = health.isError ? "false" : health.data?.status === "ok" ? "true" : "pending";
  const apiText = health.isError ? "API không phản hồi" : health.data?.status === "ok" ? "API sẵn sàng" : "Đang kết nối";
  const range = m ? `${fmtShort(m.time_range.start)} → ${fmtShort(m.time_range.end)} UTC` : "…";

  return (
    <>
      {m?.is_synthetic && (
        <div className="notice" role="note">
          <i />
          Dữ liệu mô phỏng: dùng để dựng giao diện, chưa phải kết quả của pipeline Spark.
        </div>
      )}

      <header className="bar">
        <div className="bar__in">
          <NavLink to="/" className="logo" aria-label="LogAD, trang chủ">Log<span className="mark">AD</span></NavLink>
          <nav className="menu" aria-label="Điều hướng chính">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.to === "/"}>{n.name}</NavLink>)}
          </nav>
          <div className="bar__r">
            <span className="src" title={apiText}>
              <span className="dot" data-ok={apiState} />
              <span className="src__t">{m ? m.data_source : "…"}</span>
            </span>
            <ThemeButton />
          </div>
        </div>
      </header>

      <main><div className="wrap"><Outlet /></div></main>

      <footer className="foot">
        <div className="wrap">
          <dl className="foot__info">
            <div><dt>Đề tài</dt><dd>13 · Nhập môn Big Data</dd></div>
            <div><dt>Nguồn dữ liệu</dt><dd>{m ? SOURCE_LABEL[m.data_source] : "…"}</dd></div>
            <div><dt>Khoảng dữ liệu</dt><dd>{range}</dd></div>
            <div><dt>Lần chạy · phiên bản</dt><dd>{m ? `${m.pipeline_run.id} · ${m.version}` : "…"}</dd></div>
            <div><dt>Trạng thái API</dt><dd><span className="dot" data-ok={apiState} /> {apiText}</dd></div>
          </dl>
          <p className="foot__desc">{m?.dataset.description ?? ""}</p>
          <div className="foot__word" aria-hidden="true">Log<span className="mark">AD</span></div>
        </div>
      </footer>
    </>
  );
}
