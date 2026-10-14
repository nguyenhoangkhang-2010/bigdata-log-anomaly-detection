"""Repository chạy trên DemoDataset (dữ liệu mô phỏng trong bộ nhớ)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import cached_property

import numpy as np

from ..demo_data import DemoDataset
from ..schemas import (
    Alert, AnomalyDetail, AnomalyItem, AnomalyPage, ComponentStat, Confusion, EventTemplate, Level, LogPage,
    Meta, MetaDataset, MetaRun, ModelEval, ModelName, ModelScore, Reason, ScoreBin, ScoreDistribution,
    Severity, Summary, TimeRange, Timeline, TimelinePoint, LogLine,
)

PRIMARY: ModelName = "kmeans"
BUCKET_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
LEVELS = ("INFO", "WARN", "ERROR", "FATAL")


class DemoRepository:
    name = "demo"

    def __init__(self, seed: int = 7, n_blocks: int = 4000) -> None:
        self.d = DemoDataset(seed=seed, n_blocks=n_blocks)
        self._timeline_cache: dict[str, Timeline] = {}
        d = self.d
        self._ts = np.array([ln.ts.timestamp() for ln in d.lines])
        self._lvl = np.array([LEVELS.index(ln.level) for ln in d.lines])

    # ------------------------------------------------------------------ meta / summary
    def meta(self) -> Meta:
        d = self.d
        return Meta(
            dataset=MetaDataset(
                name="Nhật ký HDFS (mô phỏng)",
                description="Dữ liệu mô phỏng theo hình dạng LogHub HDFS_v1, dùng khi pipeline Spark chưa chạy.",
            ),
            data_source="demo", is_synthetic=True,
            time_range=TimeRange(start=d.start, end=d.end),
            models=["kmeans", "iforest", "zscore"], primary_model=PRIMARY,
            pipeline_run=MetaRun(id="demo-0001", finished_at=d.finished_at),
            version="0.1.0",
        )

    def summary(self) -> Summary:
        d = self.d
        total = len(d.lines)
        warn = int((self._lvl == 1).sum())
        errors = int((self._lvl >= 2).sum())
        flagged = int(d.flags[PRIMARY].sum())
        return Summary(
            total_lines=total, total_blocks=len(d.block_ids), anomalous_blocks=flagged,
            anomaly_rate=flagged / len(d.block_ids), warn_lines=warn, error_lines=errors,
            error_rate=errors / total, active_alerts=len(self._all_alerts),
        )

    # ------------------------------------------------------------------ timeline / components
    def timeline(self, bucket: str) -> Timeline:
        if bucket in self._timeline_cache:
            return self._timeline_cache[bucket]
        sec = BUCKET_SECONDS[bucket]
        d = self.d
        t0 = d.start.timestamp()
        base = t0 - t0 % sec
        nb = int((d.end.timestamp() - base) // sec) + 1
        idx = ((self._ts - base) // sec).astype(int)
        per = [np.bincount(idx[self._lvl == k], minlength=nb) for k in range(4)]
        fl = np.flatnonzero(d.flags[PRIMARY])
        a_idx = np.array([int((d.first_ts[i].timestamp() - base) // sec) for i in fl], dtype=int)
        anom = np.bincount(a_idx, minlength=nb) if len(a_idx) else np.zeros(nb, dtype=int)
        pts = [
            TimelinePoint(ts=datetime.fromtimestamp(base + j * sec, tz=timezone.utc), info=int(per[0][j]),
                          warn=int(per[1][j]), error=int(per[2][j]), fatal=int(per[3][j]), anomalies=int(anom[j]))
            for j in range(nb)
        ]
        out = Timeline(bucket=bucket, points=pts)
        self._timeline_cache[bucket] = out
        return out

    def components(self, limit: int) -> list[ComponentStat]:
        agg: dict[str, list[int]] = {}
        for ln in self.d.lines:
            a = agg.setdefault(ln.component, [0, 0, 0, 0])
            a[0] += 1
            if ln.level == "WARN":
                a[1] += 1
            elif ln.level == "ERROR":
                a[2] += 1
            elif ln.level == "FATAL":
                a[3] += 1
        rows = [ComponentStat(component=c, total=a[0], warn=a[1], error=a[2], fatal=a[3]) for c, a in agg.items()]
        rows.sort(key=lambda r: (r.error + r.fatal, r.warn, r.total), reverse=True)
        return rows[:limit]

    # ------------------------------------------------------------------ alerts
    @cached_property
    def _all_alerts(self) -> list[Alert]:
        d = self.d
        alerts: list[Alert] = []

        # 1) đột biến lỗi theo component, cửa sổ 5 phút, z-score trên toàn khoảng thời gian
        sec = 300
        t0 = d.start.timestamp()
        base = t0 - t0 % sec
        nb = int((d.end.timestamp() - base) // sec) + 1
        per: dict[str, np.ndarray] = {}
        for ln in d.lines:
            if ln.level == "INFO":
                continue
            j = int((ln.ts.timestamp() - base) // sec)
            per.setdefault(ln.component, np.zeros(nb))[j] += 1
        for comp, series in per.items():
            mu, sd = series.mean(), series.std() or 1.0
            z = (series - mu) / sd
            j = 0
            while j < nb:
                if series[j] >= 5 and z[j] > 3:
                    k = j
                    while k + 1 < nb and series[k + 1] >= 5 and z[k + 1] > 3:
                        k += 1
                    pk = j + int(np.argmax(series[j:k + 1]))
                    zpk = float(z[pk])
                    alerts.append(Alert(
                        id=f"spike-{comp}-{j}", kind="error_spike",
                        severity="critical" if zpk >= 8 else "warning",
                        ts=datetime.fromtimestamp(base + j * sec, tz=timezone.utc),
                        title=f"Đột biến lỗi ở {comp}",
                        detail=f"{int(series[pk])} dòng WARN/ERROR trong 5 phút (trung bình {mu:.1f}, z = {zpk:.1f})",
                        component=comp, score=round(zpk, 2),
                    ))
                    j = k + 1
                else:
                    j += 1

        # 2) block bất thường điểm cao nhất của mô hình chính
        sc, thr = d.scores[PRIMARY], d.thr[PRIMARY]
        for i in np.argsort(-sc)[:12]:
            i = int(i)
            if sc[i] <= thr:
                break
            alerts.append(Alert(
                id=f"block-{d.block_ids[i]}", kind="anomalous_block",
                severity="critical" if sc[i] >= 1.6 * thr else "warning",
                ts=d.first_ts[i], title=f"Block bất thường {d.block_ids[i]}",
                detail=f"Điểm {sc[i]:.2f} (ngưỡng {thr:.2f}) · {d.line_count[i]} dòng · {d.error_count[i]} lỗi",
                block_id=d.block_ids[i], score=round(float(sc[i]), 3),
            ))
        alerts.sort(key=lambda a: a.ts, reverse=True)
        return alerts

    def alerts(self, severity: Severity | None, limit: int) -> list[Alert]:
        rows = [a for a in self._all_alerts if severity is None or a.severity == severity]
        return rows[:limit]

    # ------------------------------------------------------------------ anomalies
    @cached_property
    def _normal_mean(self) -> np.ndarray:
        mask = ~self.d.flags[PRIMARY]
        return self.d.counts[mask].mean(0)

    def _deviations(self, i: int) -> list[tuple[int, float]]:
        """Chỉ số cột event sắp theo mức lệch (có trọng số idf) so với block bình thường."""
        dev = self.d.counts[i] - self._normal_mean
        w = np.abs(dev) * self.d.idf
        order = np.argsort(-w)
        return [(int(j), float(dev[j])) for j in order if abs(dev[j]) >= 0.5]

    def _item(self, i: int, model: ModelName) -> AnomalyItem:
        d = self.d
        top = [d.event_ids[j] for j, _ in self._deviations(i)[:3]]
        return AnomalyItem(
            block_id=d.block_ids[i], model=model, anomaly_score=round(float(d.scores[model][i]), 4),
            is_anomaly=bool(d.flags[model][i]), cluster=int(d.clusters[i]) if model == "kmeans" else None,
            first_ts=d.first_ts[i], last_ts=d.last_ts[i], line_count=int(d.line_count[i]),
            warn_count=int(d.warn_count[i]), error_count=int(d.error_count[i]), top_events=top,
        )

    def anomalies(self, model, only_flagged, min_score, q, sort, page, page_size) -> AnomalyPage:
        d = self.d
        m = model or PRIMARY
        score = d.scores[m]
        mask = d.flags[m].copy() if only_flagged else np.ones(len(score), dtype=bool)
        if min_score is not None:
            mask &= score >= min_score
        idx = np.flatnonzero(mask)
        if q:
            idx = np.array([i for i in idx if q.lower() in d.block_ids[i].lower()], dtype=int)
        first = np.array([d.first_ts[i].timestamp() for i in idx])
        keys = {
            "score_desc": -score[idx], "score_asc": score[idx],
            "time_desc": -first, "time_asc": first, "lines_desc": -d.line_count[idx].astype(float),
        }
        idx = idx[np.argsort(keys[sort], kind="stable")] if len(idx) else idx
        total = len(idx)
        sl = idx[(page - 1) * page_size: page * page_size]
        return AnomalyPage(items=[self._item(int(i), m) for i in sl], total=total, page=page, page_size=page_size)

    def anomaly_detail(self, block_id: str, model: ModelName | None) -> AnomalyDetail | None:
        d = self.d
        i = d.index.get(block_id)
        if i is None:
            return None
        m = model or PRIMARY
        reasons = []
        for j, dev in self._deviations(i)[:5]:
            eid = d.event_ids[j]
            obs, exp = int(d.counts[i, j]), float(self._normal_mean[j])
            if obs == 0:
                note = f"Không xuất hiện, block bình thường có ~{exp:.1f} lần (thiếu bước)"
            elif exp < 0.05:
                note = "Hiếm gặp ở block bình thường"
            elif dev > 0:
                note = f"Nhiều hơn bình thường (~{exp:.1f} lần)"
            else:
                note = f"Ít hơn bình thường (~{exp:.1f} lần)"
            reasons.append(Reason(event_id=eid, template=d.events[eid][0], observed=obs, expected=round(exp, 2), note=note))
        return AnomalyDetail(
            item=self._item(i, m), threshold=round(d.thr[m], 4), label="Anomaly" if d.y[i] else "Normal",
            scores=[ModelScore(model=k, score=round(float(d.scores[k][i]), 4), is_anomaly=bool(d.flags[k][i]))
                    for k in ("kmeans", "iforest", "zscore")],
            reasons=reasons, timeline=[d.lines[li] for li in d.block_lines[i]],
        )

    # ------------------------------------------------------------------ events
    def events(self, sort: str, limit: int) -> list[EventTemplate]:
        d = self.d
        flagged = d.flags[PRIMARY]
        total_occ = d.counts.sum(0)
        anom_occ = d.counts[flagged].sum(0)
        base = anom_occ.sum() / total_occ.sum()
        rows = []
        for j, eid in enumerate(d.event_ids):
            tpl, level, _ = d.events[eid]
            ratio = float(anom_occ[j] / total_occ[j]) if total_occ[j] else 0.0
            rows.append(EventTemplate(
                event_id=eid, template=tpl, level=level, count=int(total_occ[j]),
                block_count=int((d.counts[:, j] > 0).sum()), anomaly_ratio=round(ratio, 4),
                lift=round(ratio / base, 2) if base else 0.0,
            ))
        rows.sort(key=(lambda r: r.count) if sort == "count_desc" else (lambda r: r.lift), reverse=True)
        return rows[:limit]

    # ------------------------------------------------------------------ models
    def models(self) -> list[ModelEval]:
        out = []
        for r in self.d.eval_rows:
            out.append(ModelEval(**{**r, "confusion": Confusion(**r["confusion"])}))
        return out

    def score_distribution(self, model: ModelName, bins: int) -> ScoreDistribution | None:
        d = self.d
        if model not in d.scores:
            return None
        s = d.scores[model]
        lo, hi = float(s.min()), float(np.quantile(s, 0.998))
        hi = hi if hi > lo else lo + 1.0
        edges = np.linspace(lo, hi, bins + 1)
        pos = np.clip(np.digitize(s, edges) - 1, 0, bins - 1)
        normal = np.bincount(pos[~d.y], minlength=bins)
        anom = np.bincount(pos[d.y], minlength=bins)
        return ScoreDistribution(
            model=model, threshold=round(d.thr[model], 4),
            bins=[ScoreBin(lower=float(edges[b]), upper=float(edges[b + 1]), normal=int(normal[b]), anomaly=int(anom[b]))
                  for b in range(bins)],
        )

    # ------------------------------------------------------------------ logs
    def logs(self, q, level, component, block_id, start, end, page, page_size) -> LogPage:
        ql = q.lower() if q else None
        hit: list[LogLine] = []
        for ln in reversed(self.d.lines):  # mới nhất trước
            if level and ln.level != level:
                continue
            if component and ln.component != component:
                continue
            if block_id and ln.block_id != block_id:
                continue
            if start and ln.ts < start:
                continue
            if end and ln.ts > end:
                continue
            if ql and ql not in ln.content.lower():
                continue
            hit.append(ln)
        total = len(hit)
        return LogPage(items=hit[(page - 1) * page_size: page * page_size], total=total, page=page, page_size=page_size)
