import { useState } from "react";
import { Link } from "react-router-dom";
import type { S } from "../api/client";
import { useAlerts, useComponents, useSummary, useTimeline } from "../api/hooks";
import { AlertList } from "../components/AlertList";
import { TimelineChart } from "../components/TimelineChart";
import { Async, LevelSwatch, PageTitle, Section, Segmented } from "../components/ui";
import { fmtInt, fmtPct } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";

const BUCKETS: { value: S["Bucket"]; label: string }[] = [
  { value: "1m", label: "1 phút" },
  { value: "5m", label: "5 phút" },
  { value: "15m", label: "15 phút" },
  { value: "1h", label: "1 giờ" },
];

function ComponentBars({ rows }: { rows: S["ComponentStat"][] }) {
  const max = Math.max(...rows.map((r) => r.warn + r.error + r.fatal), 1);
  return (
    <ul className="bars">
      {rows.map((r) => {
        const bad = r.warn + r.error + r.fatal;
        const p = (v: number) => (v / max) * 100;
        return (
          <li key={r.component}>
            <span className="bars__name">{r.component}</span>
            <svg width="100%" height="22" role="img" aria-label={`${r.warn} WARN, ${r.error} ERROR, ${r.fatal} FATAL`}>
              <rect className="b-warn" x="0%" y="0" width={`${p(r.warn)}%`} height="22" />
              <rect className="b-error" x={`${p(r.warn)}%`} y="0" width={`${p(r.error)}%`} height="22" />
              <rect className="b-fatal" x={`${p(r.warn + r.error)}%`} y="1" width={`${p(r.fatal)}%`} height="20" />
            </svg>
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
      <PageTitle
        title="Tổng quan"
        lede={s && (
          <>Trong {fmtInt(s.total_lines)} dòng nhật ký, mô hình chính gắn cờ <span className="mark">{fmtPct(s.anomaly_rate)}</span> số block là bất thường; {fmtInt(s.error_lines)} dòng mang mức ERROR hoặc FATAL.</>
        )}
      />

      <Async q={summary}>
        {(d) => (
          <div className="band">
            <div className="fld fld--ink">
              <span className="fld__k">Block bị gắn cờ</span>
              <span className="fld__v">{fmtInt(d.anomalous_blocks)}</span>
              <span className="fld__s">{fmtPct(d.anomaly_rate)} trên {fmtInt(d.total_blocks)} block</span>
            </div>
            <div className="fld fld--blue">
              <span className="fld__k">Dòng ERROR + FATAL</span>
              <span className="fld__v">{fmtInt(d.error_lines)}</span>
              <span className="fld__s">{fmtPct(d.error_rate, 2)} tổng số dòng · {fmtInt(d.warn_lines)} WARN</span>
            </div>
            <div className="fld fld--yellow">
              <span className="fld__k">Cảnh báo</span>
              <span className="fld__v">{fmtInt(d.active_alerts)}</span>
              <span className="fld__s">đột biến lỗi và block điểm cao</span>
            </div>
            <div className="fld fld--soft">
              <span className="fld__k">Dòng nhật ký</span>
              <span className="fld__v fld__v--long">{fmtInt(d.total_lines)}</span>
              <span className="fld__s">{fmtInt(d.total_blocks)} block</span>
            </div>
          </div>
        )}
      </Async>

      <div className="cols">
        <Section
          title="Lỗi theo thời gian"
          tools={<Segmented label="Độ dài khoảng" value={bucket} options={BUCKETS} onChange={setBucket} />}
        >
          <Async q={timeline}>{(d) => <TimelineChart points={d.points} />}</Async>
        </Section>

        <Section title="Cảnh báo gần đây" tools={<Link className="btn" to="/alerts">Tất cả →</Link>}>
          <Async q={alerts}>{(d) => <AlertList alerts={d} />}</Async>
        </Section>
      </div>

      <Section title="Thành phần sinh lỗi" note="Số dòng WARN, ERROR, FATAL theo component của HDFS.">
        <Async q={comps}>{(d) => <ComponentBars rows={d} />}</Async>
        <div className="legend" aria-hidden="true" style={{ marginTop: 16 }}>
          <span><LevelSwatch level="WARN" /> WARN</span>
          <span><LevelSwatch level="ERROR" /> ERROR</span>
          <span><LevelSwatch level="FATAL" /> FATAL</span>
        </div>
      </Section>
    </>
  );
}
