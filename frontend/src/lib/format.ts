const int = new Intl.NumberFormat("vi-VN");
const dec = (d: number) => new Intl.NumberFormat("vi-VN", { minimumFractionDigits: d, maximumFractionDigits: d });

export const fmtInt = (n: number) => int.format(Math.round(n));
export const fmtNum = (n: number, d = 2) => dec(d).format(n);
export const fmtPct = (x: number, d = 1) => `${dec(d).format(x * 100)}%`;

const parts = (iso: string) => {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return {
    dd: p(d.getUTCDate()), mm: p(d.getUTCMonth() + 1), yyyy: d.getUTCFullYear(),
    hh: p(d.getUTCHours()), mi: p(d.getUTCMinutes()), ss: p(d.getUTCSeconds()),
  };
};

/** Log HDFS gốc không có múi giờ nên toàn bộ hiển thị theo UTC. */
export const fmtDate = (iso: string) => { const t = parts(iso); return `${t.dd}/${t.mm}/${t.yyyy}`; };
export const fmtClock = (iso: string) => { const t = parts(iso); return `${t.hh}:${t.mi}`; };
export const fmtClockSec = (iso: string) => { const t = parts(iso); return `${t.hh}:${t.mi}:${t.ss}`; };
export const fmtShort = (iso: string) => { const t = parts(iso); return `${t.dd}/${t.mm} ${t.hh}:${t.mi}`; };
export const fmtStamp = (iso: string) => { const t = parts(iso); return `${t.dd}/${t.mm}/${t.yyyy} ${t.hh}:${t.mi}:${t.ss}`; };

export const fmtOffset = (iso: string, base: string) => {
  const s = (new Date(iso).getTime() - new Date(base).getTime()) / 1000;
  return s < 60 ? `+${fmtNum(s, 0)} s` : `+${Math.floor(s / 60)} ph ${fmtNum(s % 60, 0)} s`;
};

/** Làm tròn trần cho trục: 1, 2, 5 × 10^k. */
export function niceMax(v: number): number {
  if (v <= 0) return 1;
  const e = Math.pow(10, Math.floor(Math.log10(v)));
  const f = v / e;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * e;
}

export const pad2 = (n: number) => String(n).padStart(2, "0");
