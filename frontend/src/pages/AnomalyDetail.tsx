import { Link, useParams, useSearchParams } from "react-router-dom";
import type { S } from "../api/client";
import { useAnomaly, useModels } from "../api/hooks";
import { Async, LevelMark, PageHead, ScoreMeter, Section } from "../components/ui";
import { fmtClockSec, fmtInt, fmtNum, fmtOffset, fmtStamp } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";

const NAME: Record<S["ModelName"], string> = { kmeans: "KMeans", iforest: "Isolation Forest", zscore: "Z-score" };

function duration(a: string, b: string) {
  const s = Math.round((new Date(b).getTime() - new Date(a).getTime()) / 1000);
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} ph ${s % 60} s`;
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
              <PageHead
                no="02" section="Bất thường · chi tiết"
                title={<span className="mono" style={{ fontSize: "clamp(24px, 3.6vw, 44px)", letterSpacing: "-0.02em", overflowWrap: "anywhere" }}>{it.block_id}</span>}
                lede={it.is_anomaly
                  ? <>{NAME[it.model]} gắn cờ block này với điểm {fmtNum(it.anomaly_score, 3)}, vượt ngưỡng {fmtNum(d.threshold, 3)}.</>
                  : <>{NAME[it.model]} không gắn cờ block này: điểm {fmtNum(it.anomaly_score, 3)} thấp hơn ngưỡng {fmtNum(d.threshold, 3)}.</>}
              />

              <dl className="kv" style={{ marginBottom: 44 }}>
                <div><dt className="label">Nhãn thật (LogHub)</dt><dd className={d.label === "Anomaly" ? "signal" : undefined}>{d.label === "Anomaly" ? "Bất thường" : "Bình thường"}</dd></div>
                <div><dt className="label">Số dòng</dt><dd>{fmtInt(it.line_count)}</dd></div>
                <div><dt className="label">WARN · ERROR</dt><dd>{it.warn_count} · <span className={it.error_count ? "signal" : undefined}>{it.error_count}</span></dd></div>
                <div><dt className="label">Kéo dài</dt><dd>{duration(it.first_ts, it.last_ts)}</dd></div>
                <div><dt className="label">Bắt đầu (UTC)</dt><dd className="m">{fmtStamp(it.first_ts)}</dd></div>
              </dl>

              <Section label="So sánh" title="Điểm theo từng mô hình" note="Cùng một block, ba cách nhìn khác nhau.">
                <div className="tbl-wrap">
                  <table className="tbl">
                    <thead><tr><th>Mô hình</th><th>Điểm · ngưỡng</th><th className="r">Điểm</th><th>Kết luận</th></tr></thead>
                    <tbody>
                      {d.scores.map((s) => {
                        const t = thrOf(s.model);
                        return (
                          <tr key={s.model}>
                            <td className="serif" style={{ fontSize: 18 }}>{NAME[s.model]}</td>
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

              <Section label="Giải thích" title="Vì sao khác thường"
                       note="So số lần xuất hiện của mỗi sự kiện với trung bình các block không bị gắn cờ.">
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
                            <td className="muted" style={{ fontSize: 13.5 }}>{r.note}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Section>

              <Section label="Dòng thời gian" title="Chuỗi sự kiện" note={`${fmtInt(d.timeline.length)} dòng, từ lúc cấp phát block.`}>
                <div>
                  {d.timeline.map((ln, i) => (
                    <div className="logline" data-l={ln.level} key={i}>
                      <span className="logline__ts num">
                        {fmtOffset(ln.ts, it.first_ts)}
                        <span className="logline__comp">{fmtClockSec(ln.ts)}</span>
                      </span>
                      <LevelMark level={ln.level} />
                      <span className="logline__c">{ln.content}<span className="logline__comp">{ln.component}</span></span>
                    </div>
                  ))}
                </div>
              </Section>
            </>
          );
        }}
      </Async>
    </>
  );
}
