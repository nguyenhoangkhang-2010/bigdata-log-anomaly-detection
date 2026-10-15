"""Repository đọc KẾT QUẢ THẬT của pipeline từ các tệp nhỏ do job 07 xuất (xem src/logad/serving.py).

Không cần Elasticsearch: backend nạp thư mục serving vào bộ nhớ (pandas/numpy) rồi trả về đúng các schema của hợp đồng API.
Bật bằng LOGAD_DATA_SOURCE=files (thư mục mặc định: data/interim/logad/results/serving, đổi bằng LOGAD_SERVING_DIR).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from ..schemas import (
    Alert, AnomalyDetail, AnomalyItem, AnomalyPage, ComponentStat, EventTemplate, LogLine, LogPage, Meta, ModelEval,
    ModelName, ModelScore, ScoreBin, ScoreDistribution, Severity, Summary, Timeline, TimelinePoint,
)
from . import common as c
from .common import BUCKET_SECONDS, LEVELS, MODEL_ORDER, PRIMARY, dt, level_of


class FilesRepository:
    name = "files"

    def __init__(self, serving_dir: str | Path) -> None:
        d = Path(serving_dir)
        if not (d / "meta.json").exists():
            raise FileNotFoundError(
                f"Không thấy {d / 'meta.json'}. Chạy pipeline trước: python scripts/run_local_pipeline.py "
                "(bước 07 tạo thư mục này) hoặc đặt LOGAD_SERVING_DIR."
            )
        self.m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        self.vocab: list[str] = self.m["vocab"]
        self.idf = np.asarray(self.m["idf"], dtype=np.float64)

        table = pq.read_table(d / "blocks.parquet")
        n = table.num_rows
        flat = table.column("counts").combine_chunks().flatten().to_numpy(zero_copy_only=False)
        self.counts = flat.reshape(n, len(self.vocab)).astype(np.float64)
        self.b = table.drop_columns(["counts"]).to_pandas()
        self.block_ids = self.b["block_id"].to_numpy()
        self.index = {bid: i for i, bid in enumerate(self.block_ids)}
        self.first = self.b["first_epoch"].to_numpy(dtype=np.float64)
        self.scores = {m: self.b[f"{m}_score"].to_numpy(dtype=np.float64) for m in MODEL_ORDER}
        self.flags = {m: self.b[f"{m}_flag"].to_numpy(dtype=bool) for m in MODEL_ORDER}
        self.label = self.b["label"].to_numpy(dtype=object)
        self.has_labels = bool(self.m["dataset"]["has_labels"]) and bool(pd.notna(self.label).any())

        ev = pd.read_parquet(d / "events.parquet").fillna({"template": "", "level": "INFO"})
        self.events_df = ev
        self.template = dict(zip(ev["event_id"], ev["template"], strict=True))
        self.window = pd.read_parquet(d / "window_stats.parquet")
        self.spikes = pd.read_parquet(d / "spikes.parquet")
        lines = pd.read_parquet(d / "lines")
        self.lines = lines.sort_values("ts_epoch", kind="stable").reset_index(drop=True)
        for col in ("level", "component"):
            self.lines[col] = self.lines[col].astype("category")
        self._timeline_cache: dict[str, Timeline] = {}
        mask = ~self.flags[PRIMARY]
        self._normal_mean = self.counts[mask].mean(0) if mask.any() else self.counts.mean(0)
        self._alerts = self._build_alerts()

    # ------------------------------------------------------------------ meta / summary
    def meta(self) -> Meta:
        return c.build_meta(self.m, "files")

    def summary(self) -> Summary:
        w = self.window
        total = int(self.m["totals"]["lines"])
        warn = int(w.loc[w["level"] == "WARN", "n"].sum())
        errors = int(w.loc[w["level"].isin(["ERROR", "FATAL"]), "n"].sum())
        flagged = int(self.flags[PRIMARY].sum())
        blocks = len(self.block_ids)
        return Summary(
            total_lines=total, total_blocks=blocks, anomalous_blocks=flagged,
            anomaly_rate=flagged / blocks if blocks else 0.0, warn_lines=warn, error_lines=errors,
            error_rate=errors / total if total else 0.0, active_alerts=len(self._alerts),
        )

    # ------------------------------------------------------------------ timeline / components
    def timeline(self, bucket: str) -> Timeline:
        if bucket in self._timeline_cache:
            return self._timeline_cache[bucket]
        sec = BUCKET_SECONDS[bucket]
        w = self.window
        ts = w["ts_epoch"].to_numpy(dtype=np.int64)
        base = int(ts.min()) - int(ts.min()) % sec
        top = int(max(ts.max(), self.first.max() if len(self.first) else 0))
        nb = (top - base) // sec + 1
        idx = (ts - base) // sec
        n = w["n"].to_numpy(dtype=np.float64)
        lvl = w["level"].to_numpy()
        per = {k: np.bincount(idx[lvl == k], weights=n[lvl == k], minlength=nb) for k in LEVELS}
        fl = np.flatnonzero(self.flags[PRIMARY])
        a_idx = ((self.first[fl] - base) // sec).astype(np.int64)
        anom = np.bincount(a_idx, minlength=nb) if len(fl) else np.zeros(nb, dtype=np.int64)
        pts = [
            TimelinePoint(
                ts=dt(base + j * sec), info=int(per["INFO"][j]), warn=int(per["WARN"][j]),
                error=int(per["ERROR"][j]), fatal=int(per["FATAL"][j]), anomalies=int(anom[j]),
            )
            for j in range(nb)
        ]
        out = Timeline(bucket=bucket, points=pts)  # type: ignore[arg-type]
        self._timeline_cache[bucket] = out
        return out

    def components(self, limit: int) -> list[ComponentStat]:
        piv = self.window.pivot_table(index="component", columns="level", values="n", aggfunc="sum", fill_value=0)
        for k in LEVELS:
            if k not in piv:
                piv[k] = 0
        rows = [
            ComponentStat(
                component=str(comp), total=int(r.sum()), warn=int(r["WARN"]), error=int(r["ERROR"]), fatal=int(r["FATAL"]),
            )
            for comp, r in piv.iterrows()
        ]
        rows.sort(key=lambda r: (r.error + r.fatal, r.warn, r.total), reverse=True)
        return rows[:limit]

    # ------------------------------------------------------------------ alerts
    def _build_alerts(self) -> list[Alert]:
        win = int(self.m.get("window_seconds", 60))
        sp = self.spikes.sort_values("z", ascending=False).head(c.MAX_SPIKE_ALERTS)
        alerts = [c.spike_alert(str(r.component), r.ts_epoch, r.n, float(r.mean), float(r.z), win)
                  for r in sp.itertuples(index=False)]
        sc, thr = self.scores[PRIMARY], c.threshold_of(self.m, PRIMARY)
        flagged = np.flatnonzero(self.flags[PRIMARY])
        for i in flagged[np.argsort(-sc[flagged])][: c.MAX_BLOCK_ALERTS]:
            i = int(i)
            alerts.append(c.block_alert(
                str(self.block_ids[i]), float(sc[i]), thr, self.first[i], int(self.b["n_lines"].iat[i]),
                int(self.b["n_error"].iat[i]),
            ))
        alerts.sort(key=lambda a: a.ts, reverse=True)
        return alerts

    def alerts(self, severity: Severity | None, limit: int) -> list[Alert]:
        return [a for a in self._alerts if severity is None or a.severity == severity][:limit]

    # ------------------------------------------------------------------ anomalies
    def _item(self, i: int, model: ModelName) -> AnomalyItem:
        b = self.b
        cl = b["cluster"].iat[i]
        return AnomalyItem(
            block_id=str(self.block_ids[i]), model=model, anomaly_score=round(float(self.scores[model][i]), 4),
            is_anomaly=bool(self.flags[model][i]),
            cluster=int(cl) if model == "kmeans" and pd.notna(cl) else None,
            first_ts=dt(self.first[i]), last_ts=dt(b["last_epoch"].iat[i]), line_count=int(b["n_lines"].iat[i]),
            warn_count=int(b["n_warn"].iat[i]), error_count=int(b["n_error"].iat[i]),
            top_events=[str(e) for e in b["top_events"].iat[i]],
        )

    def anomalies(self, model, only_flagged, min_score, q, sort, page, page_size) -> AnomalyPage:
        m = model or PRIMARY
        score = self.scores[m]
        mask = self.flags[m].copy() if only_flagged else np.ones(len(score), dtype=bool)
        if min_score is not None:
            mask &= np.round(score, 4) >= min_score  # so sánh theo điểm đã làm tròn như hiển thị
        idx = np.flatnonzero(mask)
        if q:
            ql = q.lower()
            idx = np.array([i for i in idx if ql in str(self.block_ids[i]).lower()], dtype=int)
        keys = {
            "score_desc": -score[idx], "score_asc": score[idx], "time_desc": -self.first[idx], "time_asc": self.first[idx],
            "lines_desc": -self.b["n_lines"].to_numpy(dtype=np.float64)[idx],
        }
        idx = idx[np.argsort(keys[sort], kind="stable")] if len(idx) else idx
        sl = idx[(page - 1) * page_size: page * page_size]
        return AnomalyPage(items=[self._item(int(i), m) for i in sl], total=len(idx), page=page, page_size=page_size)

    def _line(self, r) -> LogLine:
        return LogLine(
            ts=dt(r.ts_epoch), level=level_of(str(r.level)), component=str(r.component),  # type: ignore[arg-type]
            block_id=None if pd.isna(r.block_id) else str(r.block_id), content=str(r.content),
            template=str(r.template), event_id=str(r.event_id),
        )

    def anomaly_detail(self, block_id: str, model: ModelName | None) -> AnomalyDetail | None:
        i = self.index.get(block_id)
        if i is None:
            return None
        m = model or PRIMARY
        lab = self.label[i]
        sel = self.lines[self.lines["block_id"] == block_id]
        return AnomalyDetail(
            item=self._item(i, m), threshold=round(c.threshold_of(self.m, m), 4),
            label=lab if lab in ("Normal", "Anomaly") else None,
            scores=[ModelScore(model=k, score=round(float(self.scores[k][i]), 4), is_anomaly=bool(self.flags[k][i]))
                    for k in MODEL_ORDER],
            reasons=c.build_reasons(self.counts[i], self._normal_mean, self.idf, self.vocab, self.template),
            timeline=[self._line(r) for r in sel.itertuples(index=False)],
        )

    # ------------------------------------------------------------------ events / models
    def events(self, sort: str, limit: int) -> list[EventTemplate]:
        df = self.events_df.sort_values("count" if sort == "count_desc" else "lift", ascending=False, kind="stable")
        return [
            EventTemplate(
                event_id=str(r.event_id), template=str(r.template), level=level_of(str(r.level)),  # type: ignore[arg-type]
                count=int(r.count), block_count=int(r.block_count), anomaly_ratio=float(r.anomaly_ratio), lift=float(r.lift),
            )
            for r in df.head(limit).itertuples(index=False)
        ]

    def models(self) -> list[ModelEval]:
        return c.build_model_evals(self.m)

    def score_distribution(self, model: ModelName, bins: int) -> ScoreDistribution | None:
        if model not in self.scores:
            return None
        s = self.scores[model]
        y = (self.label == "Anomaly") if self.has_labels else self.flags[model]
        lo, hi = float(s.min()), float(np.quantile(s, 0.998))
        hi = hi if hi > lo else lo + 1.0
        edges = np.linspace(lo, hi, bins + 1)
        pos = np.clip(np.digitize(s, edges) - 1, 0, bins - 1)
        normal = np.bincount(pos[~y], minlength=bins)
        anom = np.bincount(pos[y], minlength=bins)
        return ScoreDistribution(
            model=model, threshold=round(c.threshold_of(self.m, model), 4),
            bins=[ScoreBin(lower=float(edges[b]), upper=float(edges[b + 1]), normal=int(normal[b]), anomaly=int(anom[b]))
                  for b in range(bins)],
        )

    # ------------------------------------------------------------------ logs
    def logs(self, q, level, component, block_id, start: datetime | None, end: datetime | None, page, page_size) -> LogPage:
        df = self.lines
        mask = np.ones(len(df), dtype=bool)
        if block_id:
            mask &= (df["block_id"] == block_id).to_numpy()
        else:  # dòng chứa nhiều block được lưu nhiều bản (mỗi block một bản): chỉ lấy một bản
            mask &= (df["block_pos"].isna() | (df["block_pos"] == 0)).to_numpy()
        if level:
            mask &= (df["level"] == level).to_numpy()
        if component:
            mask &= (df["component"] == component).to_numpy()
        if start:
            mask &= df["ts_epoch"].to_numpy() >= c.aware(start).timestamp()
        if end:
            mask &= df["ts_epoch"].to_numpy() <= c.aware(end).timestamp()
        if q:
            mask &= df["content"].str.contains(q, case=False, regex=False).to_numpy()
        hit = df[mask].iloc[::-1]  # mới nhất trước
        sl = hit.iloc[(page - 1) * page_size: page * page_size]
        return LogPage(items=[self._line(r) for r in sl.itertuples(index=False)], total=len(hit), page=page, page_size=page_size)
