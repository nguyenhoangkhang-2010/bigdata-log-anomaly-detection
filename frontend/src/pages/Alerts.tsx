import { useState } from "react";
import type { S } from "../api/client";
import { useAlerts, useComponents } from "../api/hooks";
import { AlertList } from "../components/AlertList";
import { Async, PageHead, Section, Segmented } from "../components/ui";
import { fmtInt } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";

type Filter = S["Severity"] | "all";

/** Chia số đếm thành 5 bậc theo thang log để ô nhiệt không bị một giá trị lớn nuốt hết. */
function step(v: number, max: number): 0 | 1 | 2 | 3 | 4 | 5 {
  if (v <= 0) return 0;
  const r = Math.log10(v + 1) / Math.log10(max + 1);
  return Math.min(5, Math.max(1, Math.ceil(r * 5))) as 1 | 2 | 3 | 4 | 5;
}

export default function Alerts() {
  useDocumentTitle("Cảnh báo");
  const [sev, setSev] = useState<Filter>("all");
  const alerts = useAlerts(sev === "all" ? undefined : sev, 100);
  const comps = useComponents(50);

  return (
    <>
      <PageHead
        no="03" section="Cảnh báo"
        title={<>Khi nào hệ thống <em>lên tiếng</em></>}
        lede="Hai nguồn cảnh báo: đột biến số dòng lỗi của một component so với mức nền của chính nó, và các block có điểm bất thường cao nhất."
      />

      <Section
        title="Cảnh báo" label="Theo thời gian"
        note="Sắp xếp mới nhất trước."
        tools={
          <Segmented<Filter> label="Mức độ" value={sev} onChange={setSev} options={[
            { value: "all", label: "Tất cả" },
            { value: "critical", label: "Nghiêm trọng" },
            { value: "warning", label: "Cảnh báo" },
          ]} />
        }
      >
        <Async q={alerts}>{(d) => <AlertList alerts={d} />}</Async>
      </Section>

      <Section title="Ma trận lỗi" label="Component × mức độ"
               note="Màu đậm hơn nghĩa là nhiều dòng hơn (thang log). INFO không hiển thị.">
        <Async q={comps}>
          {(rows) => {
            const max = Math.max(...rows.flatMap((r) => [r.warn, r.error, r.fatal]), 1);
            return (
              <div className="tbl-wrap">
                <table className="tbl matrix">
                  <thead><tr><th>Component</th><th className="r">WARN</th><th className="r">ERROR</th><th className="r">FATAL</th><th className="r">Tổng dòng</th></tr></thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.component}>
                        <td className="id" style={{ overflowWrap: "anywhere" }}>{r.component}</td>
                        {[r.warn, r.error, r.fatal].map((v, i) => (
                          <td key={i} className="cell num" data-s={step(v, max)}>{fmtInt(v)}</td>
                        ))}
                        <td className="r mono num muted" style={{ fontSize: 13 }}>{fmtInt(r.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }}
        </Async>
      </Section>
    </>
  );
}
