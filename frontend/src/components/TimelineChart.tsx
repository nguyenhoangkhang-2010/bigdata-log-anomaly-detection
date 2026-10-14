import { useState } from "react";
import type { S } from "../api/client";
import { fmtClock, fmtInt, fmtShort, fmtStamp, niceMax } from "../lib/format";
import { useWidth } from "../lib/hooks";
import { LevelSwatch } from "./ui";

type P = S["TimelinePoint"];

const ML = 44, MR = 6, TOP = 26;
const H_T = 64, G1 = 16, H_A = 14, G2 = 58, H_E = 170, H_AX = 30;
const Y_A = H_T + G1;
const Y_E = Y_A + H_A + G2;
const H_TOTAL = TOP + Y_E + H_E + H_AX;

/** Tối đa 2 cụm khoảng có nhiều block bất thường bắt đầu nhất (không chồng nhau). */
export function findClusters(anom: number[]): { i0: number; i1: number; sum: number }[] {
  const n = anom.length;
  const total = anom.reduce((a, b) => a + b, 0);
  const span = Math.max(3, Math.round(n / 14));
  if (total === 0 || n < span) return [];
  const pre = [0];
  anom.forEach((v) => pre.push(pre[pre.length - 1] + v));
  const cands = Array.from({ length: n - span + 1 }, (_, i) => ({ i0: i, i1: i + span - 1, sum: pre[i + span] - pre[i] }))
    .sort((a, b) => b.sum - a.sum);
  const out: { i0: number; i1: number; sum: number }[] = [];
  for (const c of cands) {
    if (c.sum < Math.max(4, total * 0.08)) break;
    if (out.every((o) => c.i0 > o.i1 + span || c.i1 < o.i0 - span)) out.push(c);
    if (out.length === 2) break;
  }
  return out
    .map((o) => {
      let { i0, i1 } = o;
      while (i0 < i1 && !anom[i0]) i0++;
      while (i1 > i0 && !anom[i1]) i1--;
      return { i0, i1, sum: o.sum };
    })
    .sort((a, b) => a.i0 - b.i0);
}

/** Hai tầng chung trục thời gian: lưu lượng (nét đen), vạch bất thường, lỗi xếp chồng. Cụm bất thường được bút dạ vàng tô phía sau. */
export function TimelineChart({ points }: { points: P[] }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const n = points.length;
  const plotW = w - ML - MR;
  const bw = plotW / Math.max(1, n);
  const x = (i: number) => ML + i * bw;

  const total = points.map((p) => p.info + p.warn + p.error + p.fatal);
  const errs = points.map((p) => p.warn + p.error + p.fatal);
  const maxT = niceMax(Math.max(...total, 1));
  const maxE = niceMax(Math.max(...errs, 1));
  const maxA = Math.max(...points.map((p) => p.anomalies), 1);
  const yT = (v: number) => H_T - (v / maxT) * H_T;
  const yE = (v: number) => Y_E + H_E - (v / maxE) * H_E;

  let step = "";
  total.forEach((v, i) => {
    step += `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${yT(v).toFixed(1)} L${x(i + 1).toFixed(1)},${yT(v).toFixed(1)} `;
  });
  const area = `${step}L${x(n).toFixed(1)},${H_T} L${ML},${H_T} Z`;

  const nTicks = Math.max(2, Math.min(7, n, Math.floor(plotW / 120)));
  const ticks = Array.from({ length: nTicks }, (_, j) => Math.round((j * (n - 1)) / Math.max(1, nTicks - 1)));
  const peak = errs.indexOf(Math.max(...errs));
  const clusters = findClusters(points.map((p) => p.anomalies));
  const shown = hover !== null ? points[hover] : null;

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    setHover(Math.min(n - 1, Math.max(0, Math.floor((e.clientX - r.left - ML) / bw))));
  };

  const peakX = x(peak) + bw / 2;
  const peakTop = yE(errs[peak]);
  const calloutY = Math.max(Y_E - 4, peakTop - 24);

  return (
    <figure>
      <div className="legend" aria-hidden="true" style={{ marginBottom: 18 }}>
        <span><LevelSwatch level="WARN" /> WARN</span>
        <span><LevelSwatch level="ERROR" /> ERROR</span>
        <span><LevelSwatch level="FATAL" /> FATAL</span>
        <span><svg width="22" height="12" aria-hidden="true"><rect width="22" height="12" className="hlband" /></svg> cụm bất thường</span>
      </div>
      <div className="chart" ref={ref}>
        <svg viewBox={`0 0 ${w} ${H_TOTAL}`} height={H_TOTAL} role="img"
             aria-label={`Biểu đồ số dòng log và lỗi theo thời gian, ${n} khoảng`}>
          <g transform={`translate(0,${TOP})`}>
            {/* vệt bút dạ quang sau các cụm bất thường */}
            {clusters.map((o, k) => {
              const bx = x(o.i0) - 5;
              const bwid = Math.max(30, (o.i1 - o.i0 + 1) * bw + 10);
              const by = Y_A - 8;
              return (
                <g key={k}>
                  <rect className="hlband" x={bx} y={by} width={bwid} height={Y_E + H_E - by} />
                  <g className="hltag" transform={`translate(${bx},${Y_E - 54})`}>
                    <rect width="30" height="20" />
                    <text x="15" y="14.5" textAnchor="middle">A{k + 1}</text>
                  </g>
                </g>
              );
            })}

            {/* tầng 1: lưu lượng */}
            <text x={ML} y={-10}>Lưu lượng · dòng mỗi khoảng</text>
            <text x={ML - 8} y={10} textAnchor="end">{fmtInt(maxT)}</text>
            <text x={ML - 8} y={H_T + 1} textAnchor="end">0</text>
            <path d={area} className="area-info" />
            <path d={step} pathLength={1} className="line-info draw" />

            {/* tầng 2: vạch bất thường */}
            <text x={ML - 8} y={Y_A + 11} textAnchor="end">BT</text>
            {points.map((p, i) => {
              if (!p.anomalies) return null;
              const h = 4 + (H_A - 4) * (p.anomalies / maxA);
              return <rect key={i} className="mark-anom" x={x(i)} y={Y_A + H_A - h} width={Math.max(2.5, bw - 0.5)} height={h} />;
            })}

            {/* tầng 3: lỗi */}
            <text x={ML} y={Y_E - 12}>Lỗi mỗi khoảng</text>
            <g className="ax">
              {[0, 0.5, 1].map((f) => (
                <g key={f}>
                  <line x1={ML} x2={w - MR} y1={yE(maxE * f)} y2={yE(maxE * f)} className={f === 0 ? "base" : undefined} />
                  <text x={ML - 8} y={yE(maxE * f) + 4} textAnchor="end">{fmtInt(maxE * f)}</text>
                </g>
              ))}
            </g>
            {points.map((p, i) => {
              const bwi = Math.max(1.5, bw - (bw > 6 ? 2 : 0.4));
              let acc = 0;
              return (
                <g key={i}>
                  {([["warn", p.warn], ["error", p.error], ["fatal", p.fatal]] as const).map(([k, v]) => {
                    if (!v) return null;
                    const y1 = yE(acc + v), y0 = yE(acc);
                    acc += v;
                    return (
                      <rect key={k} className={`bar-${k} grow`} x={x(i)} y={y1} width={bwi} height={y0 - y1}
                            style={{ animationDelay: `${Math.min(i * 5, 320)}ms` }} />
                    );
                  })}
                </g>
              );
            })}

            {/* đỉnh lỗi */}
            {errs[peak] > 0 && (
              <g className="callout">
                <line x1={peakX} x2={peakX} y1={calloutY + 11} y2={peakTop - 1} />
                <circle cx={peakX} cy={calloutY} r="11" />
                <text x={peakX} y={calloutY + 4.2} textAnchor="middle">1</text>
              </g>
            )}

            {/* trục thời gian */}
            {ticks.map((i, j) => (
              <g key={j}>
                <line className="tick" x1={x(i) + bw / 2} x2={x(i) + bw / 2} y1={Y_E + H_E} y2={Y_E + H_E + 6} />
                <text x={x(i) + bw / 2} y={Y_E + H_E + 21} textAnchor={j === 0 ? "start" : j === ticks.length - 1 ? "end" : "middle"}>
                  {fmtShort(points[i].ts)}
                </text>
              </g>
            ))}

            {hover !== null && (
              <line className="cursor" x1={x(hover) + bw / 2} x2={x(hover) + bw / 2} y1={0} y2={Y_E + H_E} />
            )}
            <rect className="hit" x={ML} y={0} width={plotW} height={Y_E + H_E} onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
          </g>
        </svg>
      </div>

      <figcaption className="readout" aria-live="polite">
        {shown ? (
          <>
            <b className="num">{fmtStamp(shown.ts)} UTC</b>
            <span>INFO <b className="num">{fmtInt(shown.info)}</b></span>
            <span>WARN <b className="num">{fmtInt(shown.warn)}</b></span>
            <span>ERROR <b className="num">{fmtInt(shown.error)}</b></span>
            <span>FATAL <b className="num">{fmtInt(shown.fatal)}</b></span>
            <span className={shown.anomalies ? "hot" : undefined}>block bất thường <b className="num">{fmtInt(shown.anomalies)}</b></span>
          </>
        ) : (
          <>
            <span className="t">① Đỉnh lỗi</span>
            <b className="num">{fmtStamp(points[peak].ts)} UTC</b>
            <span><b className="num">{fmtInt(errs[peak])}</b> dòng WARN/ERROR/FATAL</span>
            <span className="t">· rê chuột lên biểu đồ để xem từng khoảng</span>
          </>
        )}
      </figcaption>

      {clusters.length > 0 && (
        <ul className="clusters" aria-label="Các cụm bất thường">
          {clusters.map((o, k) => (
            <li key={k}>
              <span className="tag">A{k + 1}</span>
              <span className="num">{fmtClock(points[o.i0].ts)} – {fmtClock(points[Math.min(n - 1, o.i1 + 1)].ts)}</span>
              <span>{fmtInt(o.sum)} block bất thường bắt đầu trong cụm này</span>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
