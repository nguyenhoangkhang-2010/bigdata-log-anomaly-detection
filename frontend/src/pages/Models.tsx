import { useState } from "react";
import type { S } from "../api/client";
import { useMeta, useModels, useScoreDistribution } from "../api/hooks";
import { Histogram } from "../components/Histogram";
import { Async, PageHead, Section, Segmented } from "../components/ui";
import { fmtInt, fmtNum, fmtPct } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";

const KIND: Record<S["ModelEval"]["kind"], string> = {
  distributed: "phân tán", "single-node": "một máy", statistical: "thống kê",
};

function Best({ on, children }: { on: boolean; children: React.ReactNode }) {
  return <span style={on ? { borderBottom: "3px solid var(--ink)" } : undefined}>{children}</span>;
}

function Confusion({ c }: { c: S["Confusion"] }) {
  return (
    <div className="confusion" role="table" aria-label="Ma trận nhầm lẫn">
      <div className="h" />
      <div className="h">Dự đoán bất thường</div>
      <div className="h">Dự đoán bình thường</div>
      <div className="h" style={{ borderBottom: "1px solid var(--rule)" }}>Thật bất thường</div>
      <div className="v good">{fmtInt(c.tp)}</div>
      <div className="v bad">{fmtInt(c.fn)}</div>
      <div className="h" style={{ borderBottom: "1px solid var(--rule)" }}>Thật bình thường</div>
      <div className="v bad">{fmtInt(c.fp)}</div>
      <div className="v good">{fmtInt(c.tn)}</div>
    </div>
  );
}

export default function Models() {
  useDocumentTitle("Mô hình");
  const meta = useMeta();
  const models = useModels();
  const [sel, setSel] = useState<S["ModelName"]>("kmeans");
  const dist = useScoreDistribution(sel, 40);
  const cur = models.data?.find((m) => m.name === sel);

  return (
    <>
      <PageHead
        no="05" section="Mô hình"
        title={<>Ba cách phát hiện, <em>một</em> thước đo</>}
        lede="Nhãn Normal/Anomaly của LogHub chỉ dùng để chấm điểm sau cùng, không đưa vào huấn luyện. Dữ liệu bất thường chiếm vài phần trăm nên Precision, Recall và PR-AUC đáng tin hơn Accuracy."
      />
      {meta.data?.is_synthetic && (
        <p className="state" style={{ paddingTop: 0 }}>
          Các chỉ số dưới đây tính trên dữ liệu mô phỏng nên chỉ minh họa cách đọc, không phản ánh chất lượng thật của mô hình.
        </p>
      )}

      <Section title="So sánh" label="Chỉ số đánh giá">
        <Async q={models}>
          {(rows) => {
            const best = (k: "precision" | "recall" | "f1" | "pr_auc") => Math.max(...rows.map((r) => r[k]));
            return (
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead><tr><th>Mô hình</th><th className="r">Precision</th><th className="r">Recall</th><th className="r">F1</th><th className="r">PR-AUC</th><th className="r">Thời gian</th></tr></thead>
                  <tbody>
                    {rows.map((m) => (
                      <tr key={m.name} data-link="true" onClick={() => setSel(m.name)} style={m.name === sel ? { background: "var(--paper-2)" } : undefined}>
                        <td>
                          <div className="serif" style={{ fontSize: 20 }}>{m.label}</div>
                          <div className="cap">{KIND[m.kind]}</div>
                        </td>
                        {(["precision", "recall", "f1", "pr_auc"] as const).map((k) => (
                          <td key={k} className="r big"><Best on={m[k] === best(k)}>{fmtNum(m[k], 3)}</Best></td>
                        ))}
                        <td className="r mono num muted" style={{ fontSize: 13 }}>{fmtNum(m.train_seconds, 2)} s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="cap" style={{ marginTop: 12 }}>Gạch chân đậm: giá trị tốt nhất của cột. Bấm một hàng để xem chi tiết bên dưới.</p>
              </div>
            );
          }}
        </Async>
      </Section>

      <Section
        title="Chi tiết" label="Mô hình đang xem"
        tools={<Segmented label="Mô hình" value={sel} onChange={setSel} options={[
          { value: "kmeans", label: "KMeans" }, { value: "iforest", label: "Isolation Forest" }, { value: "zscore", label: "Z-score" },
        ]} />}
      >
        {cur && (
          <div style={{ display: "grid", gap: 40 }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 40, alignItems: "start" }}>
              <div>
                <span className="label">Ma trận nhầm lẫn</span>
                <div style={{ marginTop: 12 }}><Confusion c={cur.confusion} /></div>
                <p className="cap" style={{ marginTop: 12, maxWidth: "44ch" }}>
                  Bỏ sót {fmtInt(cur.confusion.fn)} block bất thường; báo nhầm {fmtInt(cur.confusion.fp)} block bình thường
                  ({fmtPct(cur.confusion.fp / (cur.confusion.fp + cur.confusion.tn), 2)} số block bình thường).
                </p>
              </div>
              <div>
                <span className="label">Tham số</span>
                <dl style={{ marginTop: 12 }}>
                  {Object.entries(cur.params).map(([k, v]) => (
                    <div key={k} style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: 12, padding: "9px 0", borderBottom: "1px solid var(--rule)" }}>
                      <dt className="cap">{k}</dt><dd className="mono" style={{ fontSize: 13 }}>{String(v)}</dd>
                    </div>
                  ))}
                  <div style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: 12, padding: "9px 0", borderBottom: "1px solid var(--rule)" }}>
                    <dt className="cap">ngưỡng điểm</dt><dd className="mono" style={{ fontSize: 13 }}>{fmtNum(cur.threshold, 3)}</dd>
                  </div>
                </dl>
              </div>
            </div>
            <div>
              <span className="label" style={{ display: "block", marginBottom: 14 }}>Phân bố điểm</span>
              <Async q={dist}>{(d) => <Histogram dist={d} />}</Async>
            </div>
          </div>
        )}
      </Section>
    </>
  );
}
