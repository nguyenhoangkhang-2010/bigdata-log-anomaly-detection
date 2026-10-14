import { Link, useNavigate } from "react-router-dom";
import type { S } from "../api/client";
import { useAnomalies, useModels } from "../api/hooks";
import { Async, Empty, PageHead, Pager, ScoreMeter, Section, Segmented } from "../components/ui";
import { fmtInt, fmtNum, fmtShort } from "../lib/format";
import { useDebounced, useDocumentTitle, useUrlState } from "../lib/hooks";
import { useEffect, useState } from "react";

const DEFAULTS = { model: "kmeans", q: "", sort: "score_desc", flagged: "1", page: "1" };
const PAGE_SIZE = 15;
const MODELS: { value: S["ModelName"]; label: string }[] = [
  { value: "kmeans", label: "KMeans" },
  { value: "iforest", label: "Isolation Forest" },
  { value: "zscore", label: "Z-score" },
];
const SORTS = [
  { value: "score_desc", label: "Điểm cao nhất" },
  { value: "time_desc", label: "Mới nhất" },
  { value: "time_asc", label: "Cũ nhất" },
  { value: "lines_desc", label: "Nhiều dòng nhất" },
  { value: "score_asc", label: "Điểm thấp nhất" },
];

export default function Anomalies() {
  useDocumentTitle("Bất thường");
  const nav = useNavigate();
  const [f, patch] = useUrlState(DEFAULTS);
  const [qLocal, setQLocal] = useState(f.q);
  const qDebounced = useDebounced(qLocal, 300);
  useEffect(() => { if (qDebounced !== f.q) patch({ q: qDebounced }); }, [qDebounced]); // eslint-disable-line react-hooks/exhaustive-deps

  const model = f.model as S["ModelName"];
  const page = Number(f.page) || 1;
  const list = useAnomalies({
    model, q: f.q || undefined, sort: f.sort as never, only_flagged: f.flagged === "1", page, page_size: PAGE_SIZE,
  });
  const models = useModels();
  const thr = models.data?.find((m) => m.name === model)?.threshold ?? 1;
  const maxScore = Math.max(thr * 1.8, ...(list.data?.items.map((i) => i.anomaly_score) ?? [0]));

  return (
    <>
      <PageHead
        no="02" section="Bất thường"
        title={<>Những block <em>lệch</em> khỏi nếp thường</>}
        lede="Mỗi block HDFS là một phiên ghi/xóa dữ liệu. Điểm càng xa vạch ngưỡng đỏ, chuỗi sự kiện của block càng khác phần lớn các block còn lại."
      />

      <Section title="Danh sách" label="Lọc & sắp xếp">
        <div className="filters">
          <div className="field">
            <span className="label">Mô hình</span>
            <Segmented label="Mô hình" value={model} options={MODELS} onChange={(v) => patch({ model: v })} />
          </div>
          <label className="field">
            <span className="label">Tìm block</span>
            <input value={qLocal} onChange={(e) => setQLocal(e.target.value)} placeholder="vd. 6094" inputMode="search" />
          </label>
          <label className="field">
            <span className="label">Sắp xếp</span>
            <select value={f.sort} onChange={(e) => patch({ sort: e.target.value })}>
              {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={f.flagged === "1"} onChange={(e) => patch({ flagged: e.target.checked ? "1" : "0" })} />
            Chỉ block bị gắn cờ
          </label>
        </div>

        <Async q={list}>
          {(d) => d.items.length === 0 ? (
            <Empty>Không có block nào khớp bộ lọc này.</Empty>
          ) : (
            <>
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>#</th><th>Block</th><th>Điểm · ngưỡng</th>
                      {model === "kmeans" && <th>Cụm</th>}
                      <th className="r">Dòng</th><th className="r">WARN</th><th className="r">ERR</th>
                      <th>Bắt đầu (UTC)</th><th>Sự kiện nổi bật</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.items.map((it, i) => (
                      <tr key={it.block_id} data-link="true" onClick={() => nav(`/anomalies/${encodeURIComponent(it.block_id)}?model=${model}`)}>
                        <td className="cap num">{(page - 1) * PAGE_SIZE + i + 1}</td>
                        <td className="id">
                          <Link to={`/anomalies/${encodeURIComponent(it.block_id)}?model=${model}`} onClick={(e) => e.stopPropagation()}>
                            {it.block_id}
                          </Link>
                        </td>
                        <td>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
                            <ScoreMeter score={it.anomaly_score} threshold={thr} max={maxScore} />
                            <span className={`mono num ${it.is_anomaly ? "signal" : ""}`} style={{ fontSize: 13 }}>{fmtNum(it.anomaly_score, 3)}</span>
                          </span>
                        </td>
                        {model === "kmeans" && <td className="cap num">C{it.cluster}</td>}
                        <td className="r mono num">{fmtInt(it.line_count)}</td>
                        <td className="r mono num">{it.warn_count || "·"}</td>
                        <td className={`r mono num ${it.error_count ? "signal" : ""}`}>{it.error_count || "·"}</td>
                        <td className="cap num">{fmtShort(it.first_ts)}</td>
                        <td className="cap">{it.top_events.join("  ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pager page={d.page} pageSize={d.page_size} total={d.total} onPage={(p) => patch({ page: String(p) })} />
            </>
          )}
        </Async>
      </Section>
    </>
  );
}
