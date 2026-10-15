import { useState } from "react";
import { useEvents } from "../api/hooks";
import { Async, LevelMark, PageTitle, Section, Segmented } from "../components/ui";
import { fmtInt, fmtNum, fmtPct } from "../lib/format";
import { useDocumentTitle } from "../lib/hooks";

type Sort = "lift_desc" | "count_desc";

export default function Events() {
  useDocumentTitle("Sự kiện");
  const [sort, setSort] = useState<Sort>("lift_desc");
  const q = useEvents(sort, 50);

  return (
    <>
      <PageTitle
        title="Sự kiện"
        lede={<>Mỗi dòng log được rút về một mẫu bằng cách che block, địa chỉ IP và số. <span className="mark">Độ nghiêng</span> cho biết mẫu đó xuất hiện trong block bất thường nhiều gấp bao nhiêu lần mức chung; lớn hơn 1 là nghiêng về phía bất thường.</>}
      />
      <Section
        title="Các mẫu sự kiện"
        tools={<Segmented<Sort> label="Sắp xếp" value={sort} onChange={setSort} options={[
          { value: "lift_desc", label: "Theo độ nghiêng" },
          { value: "count_desc", label: "Theo tần suất" },
        ]} />}
      >
        <Async q={q}>
          {(rows) => (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead><tr><th>Mẫu sự kiện</th><th>Mức</th><th className="r">Lần</th><th className="r">Block</th><th>Trong block bất thường</th><th className="r">Độ nghiêng</th></tr></thead>
                <tbody>
                  {rows.map((e) => (
                    <tr key={e.event_id}>
                      <td style={{ maxWidth: 520 }}>
                        <div className="id" style={{ overflowWrap: "anywhere" }}>{e.template}</div>
                        <div className="cap">{e.event_id}</div>
                      </td>
                      <td><LevelMark level={e.level} /></td>
                      <td className="r mono num">{fmtInt(e.count)}</td>
                      <td className="r mono num">{fmtInt(e.block_count)}</td>
                      <td>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                          <span className="meter" style={{ width: 96 }}>
                            <span className="meter__base" style={{ width: `${e.anomaly_ratio * 100}%` }} />
                          </span>
                          <span className="mono num" style={{ fontSize: 13, fontWeight: 700 }}>{fmtPct(e.anomaly_ratio, 0)}</span>
                        </span>
                      </td>
                      <td className="r"><span className={`big ${e.lift >= 2 ? "mark" : ""}`}>×{fmtNum(e.lift, 1)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Async>
      </Section>
    </>
  );
}
