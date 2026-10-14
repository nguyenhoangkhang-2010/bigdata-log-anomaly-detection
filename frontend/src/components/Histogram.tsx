import { useState } from "react";
import type { S } from "../api/client";
import { fmtInt, fmtNum } from "../lib/format";
import { useWidth } from "../lib/hooks";

const ML = 44, MR = 8, MT = 26, H = 200, H_AXIS = 30;

/** Phân bố điểm bất thường, tách theo nhãn thật. Trục tung căn bậc hai để thấy cả phần đuôi hiếm. */
export function Histogram({ dist }: { dist: S["ScoreDistribution"] }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const bins = dist.bins;
  const nb = bins.length;
  const lo = bins[0].lower, hi = bins[nb - 1].upper;
  const plotW = w - ML - MR;
  const bw = plotW / nb;
  const maxV = Math.max(...bins.map((b) => b.normal + b.anomaly), 1);
  const ys = (v: number) => (Math.sqrt(v) / Math.sqrt(maxV)) * H;
  const base = MT + H;
  const xOf = (v: number) => ML + ((v - lo) / (hi - lo)) * plotW;
  const thrX = Math.min(w - MR, Math.max(ML, xOf(dist.threshold)));
  // thang căn bậc hai dồn giá trị nhỏ sát đáy: chỉ giữ vạch cách nhau >= 16px
  const yTicks = [1, 10, 100, 1000, 10000]
    .filter((t) => t <= maxV)
    .filter((t, i, a) => ys(t) >= 16 && (i === 0 || ys(t) - ys(a[i - 1]) >= 16 || ys(a[i - 1]) < 16));
  const xTicks = Array.from({ length: 6 }, (_, i) => lo + ((hi - lo) * i) / 5);
  const sel = hover !== null ? bins[hover] : null;

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const r = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    setHover(Math.min(nb - 1, Math.max(0, Math.floor((e.clientX - r.left - ML) / bw))));
  };

  return (
    <figure>
      <div className="legend" aria-hidden="true" style={{ marginBottom: 18 }}>
        <span><svg width="14" height="14"><rect width="14" height="14" className="bar-normal" /></svg> block bình thường (nhãn thật)</span>
        <span><svg width="14" height="14"><rect x="1" y="1" width="12" height="12" className="bar-anomaly" /></svg> block bất thường (nhãn thật)</span>
        <span><svg width="22" height="14"><line x1="11" x2="11" y1="0" y2="14" className="thr-line" /></svg> ngưỡng</span>
      </div>
      <div className="chart" ref={ref}>
        <svg viewBox={`0 0 ${w} ${base + H_AXIS}`} height={base + H_AXIS} role="img"
             aria-label={`Phân bố điểm của mô hình ${dist.model}, ngưỡng ${dist.threshold}`}>
          <g className="ax">
            <line className="base" x1={ML} x2={w - MR} y1={base} y2={base} />
            {yTicks.map((t) => (
              <g key={t}>
                <line x1={ML} x2={w - MR} y1={base - ys(t)} y2={base - ys(t)} />
                <text x={ML - 8} y={base - ys(t) + 4} textAnchor="end">{fmtInt(t)}</text>
              </g>
            ))}
            <text x={ML - 8} y={base + 4} textAnchor="end">0</text>
          </g>
          <text x={ML} y={MT - 12}>Số block · thang căn bậc hai</text>
          {bins.map((b, i) => {
            const hN = ys(b.normal), hT = ys(b.normal + b.anomaly);
            const bwi = Math.max(1.5, bw - 1.5);
            return (
              <g key={i} opacity={hover === null || hover === i ? 1 : 0.55}>
                {b.normal > 0 && <rect className="bar-normal grow" x={ML + i * bw} y={base - hN} width={bwi} height={hN} style={{ animationDelay: `${i * 8}ms` }} />}
                {b.anomaly > 0 && <rect className="bar-anomaly grow" x={ML + i * bw} y={base - hT} width={bwi} height={hT - hN} style={{ animationDelay: `${i * 8}ms` }} />}
              </g>
            );
          })}
          <line className="thr-line" x1={thrX} x2={thrX} y1={MT - 4} y2={base} />
          <text className="thr-text" x={thrX + (thrX > w - 120 ? -8 : 8)} y={MT + 8} textAnchor={thrX > w - 120 ? "end" : "start"}>
            ngưỡng {fmtNum(dist.threshold, 3)}
          </text>
          {xTicks.map((t, i) => (
            <g key={i}>
              <line className="tick" x1={xOf(t)} x2={xOf(t)} y1={base} y2={base + 6} />
              <text x={xOf(t)} y={base + 21} textAnchor={i === 0 ? "start" : i === 5 ? "end" : "middle"}>{fmtNum(t, 2)}</text>
            </g>
          ))}
          <rect className="hit" x={ML} y={MT} width={plotW} height={H} onMouseMove={onMove} onMouseLeave={() => setHover(null)} />
        </svg>
      </div>
      <figcaption className="readout" aria-live="polite">
        {sel ? (
          <>
            <b className="num">điểm {fmtNum(sel.lower, 3)} – {fmtNum(sel.upper, 3)}</b>
            <span>bình thường <b className="num">{fmtInt(sel.normal)}</b></span>
            <span className={sel.anomaly ? "hot" : undefined}>bất thường <b className="num">{fmtInt(sel.anomaly)}</b></span>
          </>
        ) : (
          <span className="t">Rê chuột để xem từng khoảng điểm. Block nằm bên phải vạch xanh bị hệ thống gắn cờ.</span>
        )}
      </figcaption>
    </figure>
  );
}
