import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { S } from "../api/client";
import { useComponents, useLogs } from "../api/hooks";
import { Async, Empty, LevelMark, PageTitle, Pager, Section } from "../components/ui";
import { fmtInt, fmtStamp } from "../lib/format";
import { useDebounced, useDocumentTitle, useUrlState } from "../lib/hooks";

const DEFAULTS = { q: "", level: "", component: "", block: "", start: "", end: "", page: "1" };
const PAGE_SIZE = 40;

/** Ô datetime-local ("2008-11-09T20:30") coi là giờ UTC, vì log HDFS gốc không có múi giờ. */
const toIso = (v: string) => (v ? `${v}:00Z` : undefined);

export default function Logs() {
  useDocumentTitle("Nhật ký");
  const [f, patch] = useUrlState(DEFAULTS);
  const [qLocal, setQLocal] = useState(f.q);
  const [bLocal, setBLocal] = useState(f.block);
  const qd = useDebounced(qLocal, 300);
  const bd = useDebounced(bLocal, 300);
  useEffect(() => { if (qd !== f.q) patch({ q: qd }); }, [qd]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (bd !== f.block) patch({ block: bd }); }, [bd]); // eslint-disable-line react-hooks/exhaustive-deps

  const comps = useComponents(50);
  const page = Number(f.page) || 1;
  const logs = useLogs({
    q: f.q || undefined, level: (f.level || undefined) as S["Level"] | undefined,
    component: f.component || undefined, block_id: f.block || undefined,
    start: toIso(f.start), end: toIso(f.end), page, page_size: PAGE_SIZE,
  });

  return (
    <>
      <PageTitle
        title="Nhật ký"
        lede={<>Tìm trong toàn bộ nhật ký đã parse, mới nhất trước. Vạch trái của dòng: <span className="hl">xanh = WARN</span>, đen = ERROR, vàng = FATAL. Mốc thời gian nhập theo giờ UTC.</>}
      />
      <Section title="Tra cứu">
        <div className="filters">
          <label className="field" style={{ flex: "2 1 260px" }}>
            <span>Nội dung chứa</span>
            <input value={qLocal} onChange={(e) => setQLocal(e.target.value)} placeholder="vd. exception" />
          </label>
          <label className="field">
            <span>Mức độ</span>
            <select value={f.level} onChange={(e) => patch({ level: e.target.value })}>
              <option value="">Tất cả</option>
              {(["INFO", "WARN", "ERROR", "FATAL"] as const).map((l) => <option key={l}>{l}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Component</span>
            <select value={f.component} onChange={(e) => patch({ component: e.target.value })}>
              <option value="">Tất cả</option>
              {comps.data?.map((c) => <option key={c.component} value={c.component}>{c.component}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Block ID</span>
            <input value={bLocal} onChange={(e) => setBLocal(e.target.value)} placeholder="blk_…" />
          </label>
          <label className="field">
            <span>Từ (UTC)</span>
            <input type="datetime-local" value={f.start} onChange={(e) => patch({ start: e.target.value })} />
          </label>
          <label className="field">
            <span>Đến (UTC)</span>
            <input type="datetime-local" value={f.end} onChange={(e) => patch({ end: e.target.value })} />
          </label>
        </div>

        <Async q={logs}>
          {(d) => d.items.length === 0 ? <Empty>Không có dòng log nào khớp.</Empty> : (
            <>
              <p className="mono" style={{ marginBottom: 12, fontSize: 13, fontWeight: 700 }}>{fmtInt(d.total)} dòng · mới nhất trước</p>
              <div style={{ borderTop: "3px solid var(--ink)" }}>
                {d.items.map((ln, i) => (
                  <div className="logline" data-l={ln.level} key={`${ln.ts}-${i}`}>
                    <span className="logline__ts num">{fmtStamp(ln.ts)}</span>
                    <LevelMark level={ln.level} />
                    <span className="logline__c">
                      {ln.content}
                      <span className="logline__comp">
                        {ln.component}
                        {ln.block_id && <> · <Link to={`/anomalies/${encodeURIComponent(ln.block_id)}`} className="hl">xem block</Link></>}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
              <Pager page={d.page} pageSize={d.page_size} total={d.total} onPage={(p) => { patch({ page: String(p) }); window.scrollTo({ top: 0 }); }} />
            </>
          )}
        </Async>
      </Section>
    </>
  );
}
