import { useState } from "react";
import { Link } from "react-router-dom";
import type { S } from "../api/client";
import { useAlerts, useComponents, useSummary, useTimeline } from "../api/hooks";
import { AlertList } from "../components/AlertList";
import { TimelineChart } from "../components/TimelineChart";
import { Async, PageHead, Section, Segmented } from "../components/ui";
import { fmtInt, fmtPct } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";

const BUCKETS: { value: S["Bucket"]; label: string }[] = [
  { value: "1m", label: "1 phút" },
  { value: "5m", label: "5 phút" },
  { value: "15m", label: "15 phút" },
  { value: "1h", label: "1 giờ" },
];

function Figure({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="figure">
      <span className="label">{label}</span>
      <div className="figure__v">{value}</div>
      {sub && <p className="figure__s">{sub}</p>}
    </div>
  );
}

function ComponentBars({ rows }: { rows: S["ComponentStat"][] }) {
  const max = Math.max(...rows.map((r) => r.warn + r.error + r.fatal), 1);
  return (
    <ul className="bars">
      {rows.map((r) => {
        const bad = r.warn + r.error + r.fatal;
        const pct = (v: number) => `${(v / max) * 100}%`;
        return (
          <li key={r.component}>
            <span className="bars__name">{r.component}</span>
            <span className="bars__track" role="img" aria-label={`${r.warn} WARN, ${r.error} ERROR, ${r.fatal} FATAL`}>
              <span style={{ width: pct(r.warn), background: "var(--lvl-warn)" }} />
              <span style={{ width: pct(r.error), background: "var(--lvl-error)" }} />
              <span style={{ width: pct(r.fatal), background: "var(--lvl-fatal)" }} />
            </span>
            <span className="bars__n num">{fmtInt(bad)}</span>
          </li>
        );
      })}
    </ul>
  );
}

export default function Overview() {
  useDocumentTitle("Tổng quan");
  const [bucket, setBucket] = useState<S["Bucket"]>("15m");
  const summary = useSummary();
  const timeline = useTimeline(bucket);
  const comps = useComponents(10);
  const alerts = useAlerts(undefined, 6);
  const s = summary.data;

  return (
    <>
      <PageHead
        no="01" section="Tổng quan"
        title={s ? (
          <><span className="signal num">{fmtInt(s.anomalous_blocks)}</span> block bị gắn cờ trên tổng số {fmtInt(s.total_blocks)}</>
        ) : "Đang đọc nhật ký…"}
        lede={s && (
          <>Trong {fmtInt(s.total_lines)} dòng nhật ký, mô hình chính đánh dấu {fmtPct(s.anomaly_rate)} số block là bất thường.
            {" "}{fmtInt(s.error_lines)} dòng mang mức ERROR hoặc FATAL.</>
        )}
      />

      <Async q={summary}>
        {(d) => (
          <div className="figures">
            <Figure label="Dòng nhật ký" value={fmtInt(d.total_lines)} sub={`${fmtInt(d.total_blocks)} block`} />
            <Figure label="Block bất thường" value={fmtInt(d.anomalous_blocks)} sub={`${fmtPct(d.anomaly_rate)} tổng số block`} />
            <Figure label="Dòng ERROR · FATAL" value={fmtInt(d.error_lines)} sub={`${fmtPct(d.error_rate, 2)} tổng số dòng · ${fmtInt(d.warn_lines)} WARN`} />
            <Figure label="Cảnh báo" value={fmtInt(d.active_alerts)} sub="đột biến lỗi và block điểm cao" />
          </div>
        )}
      </Async>

      <div style={{ height: 44 }} />

      <Section
        label="Diễn biến" title="Lỗi theo thời gian"
        note="Vạch đỏ ở giữa là thời điểm một block bất thường bắt đầu."
        tools={<Segmented label="Độ dài khoảng" value={bucket} options={BUCKETS} onChange={setBucket} />}
      >
        <Async q={timeline}>{(d) => <TimelineChart points={d.points} />}</Async>
      </Section>

      <Section label="Phân bổ" title="Thành phần sinh lỗi" note="Số dòng WARN, ERROR, FATAL theo component của HDFS.">
        <Async q={comps}>{(d) => <ComponentBars rows={d} />}</Async>
        <div className="legend" aria-hidden="true" style={{ marginTop: 16 }}>
          <span><i style={{ background: "var(--lvl-warn)" }} />WARN</span>
          <span><i style={{ background: "var(--lvl-error)" }} />ERROR</span>
          <span><i style={{ background: "var(--lvl-fatal)" }} />FATAL</span>
        </div>
      </Section>

      <Section label="Cần xem" title="Cảnh báo gần đây"
               tools={<Link className="btn" to="/alerts">Tất cả cảnh báo →</Link>}>
        <Async q={alerts}>{(d) => <AlertList alerts={d} />}</Async>
      </Section>
    </>
  );
}
