import type { ReactNode } from "react";
import { ApiError, type S } from "../api/client";

export function PageHead({
  no, section, title, lede,
}: { no: string; section: string; title: ReactNode; lede?: ReactNode }) {
  return (
    <header className="head">
      <div className="head__kicker">
        <span className="label">Nº {no} / 06</span>
        <span className="label">{section}</span>
      </div>
      <h1>{title}</h1>
      {lede && <p className="head__lede">{lede}</p>}
    </header>
  );
}

export function Section({
  label, title, note, tools, children,
}: { label?: string; title: string; note?: ReactNode; tools?: ReactNode; children: ReactNode }) {
  return (
    <section className="sec">
      <div className="sec__label">
        {label && <span className="label">{label}</span>}
        <h2 className="sec__title">{title}</h2>
        {note && <p className="sec__note">{note}</p>}
      </div>
      <div className="sec__body">
        {tools && <div className="sec__tools">{tools}</div>}
        {children}
      </div>
    </section>
  );
}

export function Segmented<T extends string>({
  value, options, onChange, label,
}: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function LevelMark({ level }: { level: S["Level"] }) {
  return (
    <span className="lv" data-l={level}>
      <i />
      {level}
    </span>
  );
}

/** Thước đo điểm bất thường so với ngưỡng (vạch đỏ). */
export function ScoreMeter({ score, threshold, max }: { score: number; threshold: number; max: number }) {
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  return (
    <span className="meter" role="img" aria-label={`điểm ${score.toFixed(3)}, ngưỡng ${threshold.toFixed(3)}`}>
      <span className="meter__track" />
      <span className="meter__fill" data-over={score > threshold} style={{ width: pct(score) }} />
      <span className="meter__thr" style={{ left: pct(threshold) }} />
    </span>
  );
}

export function Pager({
  page, pageSize, total, onPage,
}: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const last = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav className="pager" aria-label="Phân trang">
      <span className="label num">
        {from}–{to} / {total.toLocaleString("vi-VN")}
      </span>
      <span className="pager__btns">
        <button className="btn" disabled={page <= 1} onClick={() => onPage(page - 1)}>← Trước</button>
        <button className="btn" disabled={page >= last} onClick={() => onPage(page + 1)}>Sau →</button>
      </span>
    </nav>
  );
}

export function Loading() {
  return <div className="skeleton" role="status" aria-label="Đang tải" />;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="state">{children}</p>;
}

export function ErrorState({ error }: { error: unknown }) {
  const e = error instanceof ApiError ? error : null;
  return (
    <p className="state state--error" role="alert">
      {e?.message ?? "Đã có lỗi khi tải dữ liệu."}
      {e?.detail && <small>{e.detail}</small>}
    </p>
  );
}

/** Gói trạng thái của một truy vấn: đang tải / lỗi / có dữ liệu. */
export function Async<T>({
  q, children,
}: { q: { data?: T; error: unknown; isPending: boolean }; children: (d: T) => ReactNode }) {
  if (q.error && q.data === undefined) return <ErrorState error={q.error} />;
  if (q.data === undefined) return <Loading />;
  return <>{children(q.data)}</>;
}
