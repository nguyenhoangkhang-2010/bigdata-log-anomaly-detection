import { useState } from "react";
import type { S } from "../api/client";
import { useMeta, useModels, useScoreDistribution } from "../api/hooks";
import { Histogram } from "../components/Histogram";
import { Async, PageTitle, Section, Segmented } from "../components/ui";
import { fmtInt, fmtNum, fmtPct } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";

const KIND: Record<S["ModelEval"]["kind"], string> = {
  distributed: "phân tán", "single-node": "một máy", statistical: "thống kê",
};

function Best({ on, children }: { on: boolean; children: React.ReactNode }) {
  return <span className={on ? "mark" : undefined}>{children}</span>;
}

function Confusion({ c }: { c: S["Confusion"] }) {
  return (
    <div className="confusion" role="table" aria-label="Ma trận nhầm lẫn">
      <div className="h" />
      <div className="h">Dự đoán bất thường</div>
      <div className="h">Dự đoán bình thường</div>
      <div className="h">Thật bất thường</div>
      <div className="v good">{fmtInt(c.tp)}</div>
      <div className="v bad">{fmtInt(c.fn)}</div>
      <div className="h">Thật bình thường</div>
      <div className="v bad">{fmtInt(c.fp)}</div>
      <div className="v good">{fmtInt(c.tn)}</div>
    </div>
  );
}

const KV = { display: "grid", gridTemplateColumns: "140px 1fr", gap: 12, padding: "11px 0", borderBottom: "1px solid var(--rule)" } as const;

export default function Models() {
  useDocumentTitle("Mô hình");
  const meta = useMeta();
  const models = useModels();
  const [sel, setSel] = useState<S["ModelName"]>("kmeans");
  const dist = useScoreDistribution(sel, 40);
  const cur = models.data?.find((m) => m.name === sel);

  return (
    <>
      <PageTitle
        title="Mô hình"
        lede={<>Các mô hình học không giám sát; nhãn Normal/Anomaly của LogHub chỉ dùng để chọn k của KMeans (nửa val) và chấm điểm trên nửa test còn lại, nên số liệu dưới đây là của nửa test. Dữ liệu bất thường chiếm vài phần trăm nên Precision, Recall và PR-AUC đáng tin hơn Accuracy.
          {meta.data?.is_synthetic && <> <span className="mark">Số liệu dưới đây tính trên dữ liệu mô phỏng</span>: chỉ minh họa cách đọc, không phản ánh chất lượng thật.</>}</>}
      />

      <Section title="So sánh mô hình" note="Ô vàng: giá trị tốt nhất của cột. Bấm một hàng để xem chi tiết bên dưới.">
        <Async q={models}>
          {(rows) => {
            const best = (k: "precision" | "recall" | "f1" | "pr_auc") => Math.max(...rows.map((r) => r[k]));
            return (
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead><tr><th>Mô hình</th><th className="r">Precision</th><th className="r">Recall</th><th className="r">F1</th><th className="r">PR-AUC</th><th className="r">Thời gian</th></tr></thead>
                  <tbody>
                    {rows.map((m) => (
                      <tr key={m.name} data-link="true" className={m.name === sel ? "is-sel" : undefined} onClick={() => setSel(m.name)}>
                        <td>
                          <div className="name">{m.label}</div>
                          <div className="cap">{KIND[m.kind]}</div>
                        </td>
                        {(["precision", "recall", "f1", "pr_auc"] as const).map((k) => (
                          <td key={k} className="r"><span className="big"><Best on={m[k] === best(k)}>{fmtNum(m[k], 3)}</Best></span></td>
                        ))}
                        <td className="r mono num" style={{ fontSize: 13 }}>{fmtNum(m.train_seconds, 2)} s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }}
        </Async>
      </Section>

      <Section
        title="Chi tiết mô hình"
        tools={<Segmented label="Mô hình" value={sel} onChange={setSel} options={[
          { value: "kmeans", label: "KMeans" }, { value: "iforest", label: "IForest" }, { value: "zscore", label: "Z-score" },
        ]} />}
      >
        {cur && (
          <div style={{ display: "grid", gap: 44 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 44, alignItems: "start" }}>
              <div>
                <h3 className="field__l" style={{ marginBottom: 12, font: "700 13px/1 var(--sans)" }}>Ma trận nhầm lẫn</h3>
                <Confusion c={cur.confusion} />
                <p className="mono" style={{ marginTop: 14, maxWidth: "46ch", fontSize: 12.5, color: "var(--ink-3)" }}>
                  Bỏ sót {fmtInt(cur.confusion.fn)} block bất thường; báo nhầm {fmtInt(cur.confusion.fp)} block bình thường
                  ({fmtPct(cur.confusion.fp / (cur.confusion.fp + cur.confusion.tn), 2)} số block bình thường).
                </p>
              </div>
              <div>
                <h3 style={{ marginBottom: 6, font: "700 13px/1 var(--sans)" }}>Tham số</h3>
                <dl style={{ borderTop: "3px solid var(--ink)", marginTop: 10 }}>
                  {Object.entries(cur.params).map(([k, v]) => (
                    <div key={k} style={KV}><dt style={{ font: "600 13px/1.4 var(--sans)", color: "var(--ink-2)" }}>{k}</dt><dd className="mono" style={{ fontSize: 13 }}>{String(v)}</dd></div>
                  ))}
                  <div style={KV}><dt style={{ font: "600 13px/1.4 var(--sans)", color: "var(--ink-2)" }}>ngưỡng điểm</dt><dd className="mono" style={{ fontSize: 13 }}>{fmtNum(cur.threshold, 3)}</dd></div>
                </dl>
              </div>
            </div>
            <div>
              <h3 style={{ marginBottom: 16, font: "700 13px/1 var(--sans)" }}>Phân bố điểm</h3>
              <Async q={dist}>{(d) => <Histogram dist={d} />}</Async>
            </div>
          </div>
        )}
      </Section>
    </>
  );
}
