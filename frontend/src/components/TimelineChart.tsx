import { useState } from "react";
import type { S } from "../api/client";
import { fmtInt, fmtShort, fmtStamp, niceMax } from "../lib/format";
import { useWidth } from "../lib/hooks";

type P = S["TimelinePoint"];
const ML = 46, MR = 6;
const H_TRAFFIC = 64, H_GAP = 10, H_ANOM = 14, H_GAP2 = 24, H_ERR = 150, H_AXIS = 26;
const Y_ANOM = H_TRAFFIC + H_GAP;
const Y_ERR = Y_ANOM + H_ANOM + H_GAP2;
const TOP = 16;
const H_TOTAL = TOP + Y_ERR + H_ERR + H_AXIS;

/** Hai tầng chung một trục thời gian: lưu lượng (tất cả dòng) và lỗi xếp chồng, giữa là vạch block bất thường. */
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
  const maxA = Math.max(...points.map((p) => p.anomalies), 1);
  const maxE = niceMax(Math.max(...errs, 1));
  const yT = (v: number) => H_TRAFFIC - (v / maxT) * H_TRAFFIC;
  const yE = (v: number) => Y_ERR + H_ERR - (v / maxE) * H_ERR;

  let step = "";
  total.forEach((v, i) => {
    step += `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${yT(v).toFixed(1)} L${x(i + 1).toFixed(1)},${yT(v).toFixed(1)} `;
  });
  const area = `${step}L${x(n).toFixed(1)},${H_TRAFFIC} L${ML},${H_TRAFFIC} Z`;

  const nTicks = Math.max(2, Math.min(7, n, Math.floor(plotW / 120)));  // thưa nhãn khi màn hẹp
  const ticks = Array.from({ length: nTicks }, (_, j) => Math.round((j * (n - 1)) / Math.max(1, nTicks - 1)));
  const peak = errs.indexOf(Math.max(...errs));
  const cur = hover ?? null;
  const shown = cur !== null ? points[cur] : null;

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    setHover(Math.min(n - 1, Math.max(0, Math.floor((e.clientX - r.left - ML) / bw))));
  };

  return (
    <figure>
      <div className="legend" aria-hidden="true" style={{ marginBottom: 14 }}>
        <span><i style={{ background: "var(--lvl-warn)" }} />WARN</span>
        <span><i style={{ background: "var(--lvl-error)" }} />ERROR</span>
        <span><i style={{ background: "var(--lvl-fatal)" }} />FATAL</span>
        <span><i style={{ background: "var(--signal)", width: 3, height: 12 }} />block bất thường bắt đầu</span>
      </div>
      <div className="chart" ref={ref}>
        <svg viewBox={`0 0 ${w} ${H_TOTAL}`} height={H_TOTAL} role="img"
             aria-label={`Biểu đồ số dòng log và lỗi theo thời gian, ${n} khoảng`}>
          <g transform={`translate(0,${TOP})`}>
          {/* lưu lượng */}
          <text x={ML - 8} y={9} textAnchor="end">{fmtInt(maxT)}</text>
          <text x={ML - 8} y={H_TRAFFIC} textAnchor="end">0</text>
          <path d={area} className="area-info" />
          <text x={ML} y={-8} style={{ fontSize: 10 }}>LƯU LƯỢNG · DÒNG / KHOẢNG</text>

          {/* bất thường */}
          <text x={ML - 8} y={Y_ANOM + 10} textAnchor="end">BT</text>
          <line className="tick" x1={ML} x2={w - MR} y1={Y_ANOM + H_ANOM} y2={Y_ANOM + H_ANOM} />
          {points.map((p, i) => p.anomalies > 0 && (
            <rect key={i} className="mark-anom" x={x(i)} width={Math.max(2, bw - 0.5)}
                  y={Y_ANOM + H_ANOM - (3 + (H_ANOM - 3) * (p.anomalies / maxA))}
                  height={3 + (H_ANOM - 3) * (p.anomalies / maxA)} />
          ))}

          {/* lỗi */}
          <g className="ax">
            {[0, 0.5, 1].map((f) => (
              <g key={f}>
                <line x1={ML} x2={w - MR} y1={yE(maxE * f)} y2={yE(maxE * f)} className={f === 0 ? "base" : undefined} />
                <text x={ML - 8} y={yE(maxE * f) + 3.5} textAnchor="end">{fmtInt(maxE * f)}</text>
              </g>
            ))}
          </g>
          <text x={ML} y={Y_ERR - 8}>LỖI · WARN + ERROR + FATAL / KHOẢNG</text>
          {points.map((p, i) => {
            const bwi = Math.max(1, bw - (bw > 6 ? 1.5 : 0.4));
            let acc = 0;
            return (
              <g key={i}>
                {([["warn", p.warn], ["error", p.error], ["fatal", p.fatal]] as const).map(([k, v]) => {
                  if (!v) return null;
                  const y1 = yE(acc + v), y0 = yE(acc);
                  acc += v;
                  return <rect key={k} className={`bar-${k} grow`} x={x(i)} y={y1} width={bwi} height={y0 - y1}
                               style={{ animationDelay: `${Math.min(i * 6, 360)}ms` }} />;
                })}
              </g>
            );
          })}

          {/* trục thời gian */}
          {ticks.map((i, j) => (
            <g key={j}>
              <line className="tick" x1={x(i) + bw / 2} x2={x(i) + bw / 2} y1={Y_ERR + H_ERR} y2={Y_ERR + H_ERR + 5} />
              <text x={x(i) + bw / 2} y={Y_ERR + H_ERR + 18}
                    textAnchor={j === 0 ? "start" : j === ticks.length - 1 ? "end" : "middle"}>
                {fmtShort(points[i].ts)}
              </text>
            </g>
          ))}

          {cur !== null && (
            <line className="cursor" x1={x(cur) + bw / 2} x2={x(cur) + bw / 2} y1={0} y2={Y_ERR + H_ERR} />
          )}
          <rect className="hit" x={ML} y={0} width={plotW} height={Y_ERR + H_ERR}
                onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
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
            <span className={shown.anomalies ? "signal" : undefined}>
              block bất thường <b className="num">{fmtInt(shown.anomalies)}</b>
            </span>
          </>
        ) : (
          <>
            <span className="t">Đỉnh lỗi</span>
            <b className="num">{fmtStamp(points[peak].ts)} UTC</b>
            <span><b className="num">{fmtInt(errs[peak])}</b> dòng WARN/ERROR/FATAL</span>
            <span className="t">· rê chuột lên biểu đồ để xem từng khoảng</span>
          </>
        )}
      </figcaption>
    </figure>
  );
}
