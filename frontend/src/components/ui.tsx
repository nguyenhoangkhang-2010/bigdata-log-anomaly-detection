import type { ReactNode } from "react";
import { ApiError, type S } from "../api/client";

/** Tiêu đề trang: tên đậm bản rộng bên trái, một đoạn dẫn bên phải, gạch đen dày bên dưới. */
export function PageTitle({ title, lede, isId }: { title: ReactNode; lede?: ReactNode; isId?: boolean }) {
  return (
    <header className="pt">
      <h1 className={isId ? "is-id" : undefined}>{title}</h1>
      {lede && <p>{lede}</p>}
    </header>
  );
}

export function Section({
  title, note, tools, children,
}: { title: string; note?: ReactNode; tools?: ReactNode; children: ReactNode }) {
  return (
    <section className="sec" aria-label={title}>
      <div className="sec__head">
        <h2>{title}</h2>
        {tools && <div className="sec__tools">{tools}</div>}
      </div>
      {note && <p className="sec__note">{note}</p>}
      {children}
    </section>
  );
}

export function Segmented<T extends string>({
  value, options, onChange, label,
}: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function LevelSwatch({ level, size = 12 }: { level: S["Level"]; size?: number }) {
  return (
    <svg className="sw" width={size} height={size} viewBox="0 0 12 12" aria-hidden="true">
      <rect className={`sw-${level}`} x="0.8" y="0.8" width="10.4" height="10.4" />
    </svg>
  );
}

export function LevelMark({ level }: { level: S["Level"] }) {
  return (
    <span className="lv" data-l={level}>
      <LevelSwatch level={level} />
      {level}
    </span>
  );
}

/** Thước điểm: phần đen tới ngưỡng, phần VƯỢT ngưỡng tô vàng; vạch xanh là ngưỡng. */
export function ScoreMeter({ score, threshold, max }: { score: number; threshold: number; max: number }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  const over = score > threshold;
  return (
    <span className="meter" role="img" aria-label={`điểm ${score.toFixed(3)}, ngưỡng ${threshold.toFixed(3)}`}>
      <span className="meter__base" style={{ width: pct(Math.min(score, threshold)) }} />
      {over && <span className="meter__over" style={{ left: pct(threshold), width: `calc(${pct(score)} - ${pct(threshold)})` }} />}
      <span className="meter__thr" style={{ left: pct(threshold) }} />
    </span>
  );
}

/** Cơ cấu dòng của một block theo tỉ lệ: INFO xám · WARN xanh · ERROR đen. */
export function LineMix({ total, warn, error, width = 110 }: { total: number; warn: number; error: number; width?: number }) {
  const info = Math.max(0, total - warn - error);
  const w = (v: number) => (total ? (v / total) * width : 0);
  const parts = [["m-info", info], ["m-warn", warn], ["m-error", error]] as const;
  let x = 0;
  return (
    <svg className="mix" width={width} height="14" viewBox={`0 0 ${width} 14`} role="img"
         aria-label={`${info} INFO, ${warn} WARN, ${error} lỗi`}>
      {parts.map(([cls, v]) => {
        if (!v) return null;
        const r = <rect key={cls} className={cls} x={x} y="0" width={Math.max(2, w(v) - 1)} height="14" />;
        x += w(v);
        return r;
      })}
    </svg>
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
      <span className="pager__n num">{from}–{to} / {total.toLocaleString("vi-VN")}</span>
      <span className="pager__btns">
        <button className="btn btn--line" disabled={page <= 1} onClick={() => onPage(page - 1)}>← Trước</button>
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
