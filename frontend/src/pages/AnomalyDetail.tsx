import { Link, useParams, useSearchParams } from "react-router-dom";
import type { S } from "../api/client";
import { useAnomaly, useModels } from "../api/hooks";
import { Async, LevelMark, PageTitle, ScoreMeter, Section } from "../components/ui";
import { fmtClockSec, fmtInt, fmtNum, fmtOffset, fmtStamp } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";

const NAME: Record<S["ModelName"], string> = { kmeans: "KMeans", iforest: "Isolation Forest", zscore: "Z-score" };
const TICK_H: Record<S["Level"], number> = { INFO: 14, WARN: 28, ERROR: 42, FATAL: 54 };
const TICK_FILL: Record<S["Level"], string> = {
  INFO: "var(--gray)", WARN: "var(--blue)", ERROR: "var(--ink)", FATAL: "var(--yellow)",
};

function duration(a: string, b: string) {
  const s = Math.round((new Date(b).getTime() - new Date(a).getTime()) / 1000);
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} ph ${s % 60} s`;
}

/** Dải thời gian: mỗi dòng log là một vạch đặt theo thời điểm, cao và đậm theo mức độ. */
function TimeStrip({ lines }: { lines: S["LogLine"][] }) {
  const t0 = new Date(lines[0].ts).getTime();
  const span = Math.max(1, new Date(lines[lines.length - 1].ts).getTime() - t0);
  return (
    <figure>
      <svg width="100%" height="64" role="img" aria-label={`${lines.length} dòng log theo thời gian`}>
        <rect x="0" y="58" width="100%" height="4" style={{ fill: "var(--ink)" }} />
        {lines.map((ln, i) => {
          const x = ((new Date(ln.ts).getTime() - t0) / span) * 100;
          const h = TICK_H[ln.level];
          return (
            <rect key={i} x={`calc(${x}% - 3px)`} y={58 - h} width="6" height={h}
                  style={{ fill: TICK_FILL[ln.level], stroke: ln.level === "FATAL" ? "var(--ink)" : "none", strokeWidth: 1.5 }} />
          );
        })}
      </svg>
      <figcaption className="legend" style={{ justifyContent: "space-between", marginTop: 8 }}>
        <span className="mono">+0 s</span><span>vạch cao và đậm hơn = mức nặng hơn</span>
        <span className="mono">+{duration(lines[0].ts, lines[lines.length - 1].ts)}</span>
      </figcaption>
    </figure>
  );
}

export default function AnomalyDetail() {
  const { blockId = "" } = useParams();
  const [sp] = useSearchParams();
  const model = (sp.get("model") as S["ModelName"] | null) ?? undefined;
  useDocumentTitle(blockId);
  const q = useAnomaly(blockId, model);
  const models = useModels();

  return (
    <>
      <Link className="btn back" to={`/anomalies${model ? `?model=${model}` : ""}`}>← Danh sách bất thường</Link>
      <Async q={q}>
        {(d) => {
          const it = d.item;
          const thrOf = (m: S["ModelName"]) => models.data?.find((x) => x.name === m)?.threshold ?? d.threshold;
          return (
            <>
              <PageTitle
                isId title={it.block_id}
                lede={it.is_anomaly
                  ? <>{NAME[it.model]} gắn cờ block này với điểm <span className="mark">{fmtNum(it.anomaly_score, 3)}</span>, vượt ngưỡng {fmtNum(d.threshold, 3)}.</>
                  : <>{NAME[it.model]} không gắn cờ block này: điểm {fmtNum(it.anomaly_score, 3)} thấp hơn ngưỡng {fmtNum(d.threshold, 3)}.</>}
              />
              <dl className="kv">
                <div><dt>Nhãn thật (LogHub)</dt><dd className={d.label === "Anomaly" ? "hl" : undefined}>{d.label === "Anomaly" ? "Bất thường" : "Bình thường"}</dd></div>
                <div><dt>Số dòng</dt><dd>{fmtInt(it.line_count)}</dd></div>
                <div><dt>WARN · ERROR</dt><dd>{it.warn_count} · {it.error_count}</dd></div>
                <div><dt>Kéo dài</dt><dd>{duration(it.first_ts, it.last_ts)}</dd></div>
                <div><dt>Bắt đầu (UTC)</dt><dd className="m">{fmtStamp(it.first_ts)}</dd></div>
              </dl>

              <Section title="Điểm theo từng mô hình" note="Cùng một block, ba cách nhìn khác nhau. Nhãn thật chỉ để đối chiếu, không dùng khi huấn luyện.">
                <div className="tbl-wrap">
                  <table className="tbl">
                    <thead><tr><th>Mô hình</th><th>Điểm · ngưỡng</th><th className="r">Điểm</th><th>Kết luận</th></tr></thead>
                    <tbody>
                      {d.scores.map((s) => {
                        const t = thrOf(s.model);
                        return (
                          <tr key={s.model}>
                            <td className="name">{NAME[s.model]}</td>
                            <td><ScoreMeter score={s.score} threshold={t} max={Math.max(t * 1.8, s.score)} /></td>
                            <td className="r mono num">{fmtNum(s.score, 3)}</td>
                            <td><span className="pill" data-on={s.is_anomaly}>{s.is_anomaly ? "Bất thường" : "Bình thường"}</span></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Section>

              <Section title="Vì sao khác thường" note="So số lần xuất hiện của mỗi sự kiện với trung bình các block không bị gắn cờ.">
                {d.reasons.length === 0 ? <p className="state">Block này gần như trùng với nếp thường.</p> : (
                  <div className="tbl-wrap">
                    <table className="tbl">
                      <thead><tr><th>Sự kiện</th><th className="r">Có</th><th className="r">Thường</th><th>Nhận xét</th></tr></thead>
                      <tbody>
                        {d.reasons.map((r) => (
                          <tr key={r.event_id}>
                            <td><div className="id" style={{ overflowWrap: "anywhere" }}>{r.template}</div><div className="cap">{r.event_id}</div></td>
                            <td className="r mono num">{r.observed}</td>
                            <td className="r mono num">{fmtNum(r.expected, 1)}</td>
                            <td style={{ fontSize: 14 }}>{r.note}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Section>

              <Section title="Dải thời gian">
                <TimeStrip lines={d.timeline} />
              </Section>

              <Section title="Chuỗi sự kiện" note={`${fmtInt(d.timeline.length)} dòng, từ lúc cấp phát block. Dòng lỗi được tô vàng.`}>
                <ul className="seq">
                  {d.timeline.map((ln, i) => (
                    <li data-l={ln.level} key={i}>
                      <span className="seq__t num">{fmtOffset(ln.ts, it.first_ts)}<small>{fmtClockSec(ln.ts)}</small></span>
                      <LevelMark level={ln.level} />
                      <span style={{ overflowWrap: "anywhere" }}>{ln.content}<span className="logline__comp">{ln.component}</span></span>
                    </li>
                  ))}
                </ul>
              </Section>
            </>
          );
        }}
      </Async>
    </>
  );
}
