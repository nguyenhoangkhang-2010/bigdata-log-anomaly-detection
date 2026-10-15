"""Repository đọc từ Elasticsearch - nơi lưu kết quả thật của pipeline (job 06 ghi, xem src/logad/es_load.py).

Bản đồ index -> endpoint (tên index = `<prefix>-<loại>`, mặc định prefix `logad`):

    meta         -> /meta, /overview/summary (tổng), /models, ngưỡng, từ vựng event + trung bình block bình thường
    error-stats  -> /overview/timeline, /overview/components, số dòng WARN/ERROR của /overview/summary
    spikes       -> cảnh báo đột biến (/alerts)
    anomalies    -> /anomalies, /anomalies/{block_id}, cảnh báo block, /models/{m}/score-distribution, /anomalies/export
    logs         -> /logs, chuỗi sự kiện trong chi tiết block
    events       -> /events

Mọi truy vấn nặng (đếm, gộp theo thời gian, phân bố điểm) chạy trong Elasticsearch; backend chỉ giữ meta và danh sách cảnh báo.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from ..schemas import (
    Alert, AnomalyDetail, AnomalyItem, AnomalyPage, ComponentStat, EventTemplate, LogLine, LogPage, Meta, ModelEval,
    ModelName, ModelScore, ScoreBin, ScoreDistribution, Severity, Summary, Timeline, TimelinePoint,
)
from . import common as c
from .common import BUCKET_SECONDS, MODEL_ORDER, PRIMARY, dt, level_of

SORTS = {
    "score_desc": lambda m: [{f"{m}_score": "desc"}, {"block_id": "asc"}],
    "score_asc": lambda m: [{f"{m}_score": "asc"}, {"block_id": "asc"}],
    "time_desc": lambda m: [{"first_ts": "desc"}, {"block_id": "asc"}],
    "time_asc": lambda m: [{"first_ts": "asc"}, {"block_id": "asc"}],
    "lines_desc": lambda m: [{"n_lines": "desc"}, {"block_id": "asc"}],
}


def _wildcard_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")


def _epoch(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


class ElasticsearchRepository:
    name = "elasticsearch"

    def __init__(self, url: str, prefix: str = "logad", client: Any = None) -> None:
        from elasticsearch import Elasticsearch, NotFoundError

        self.es = client or Elasticsearch(url, request_timeout=60)
        self.ix = {k: f"{prefix}-{k}" for k in ("anomalies", "error-stats", "spikes", "logs", "events", "meta")}
        try:
            self.m: dict[str, Any] = self.es.get(index=self.ix["meta"], id="meta")["_source"]
        except NotFoundError as e:
            raise RuntimeError(
                f"Elasticsearch chưa có dữ liệu ({self.ix['meta']}). Nạp bằng: python scripts/run_local_pipeline.py --only 06"
            ) from e
        self.vocab: list[str] = self.m["vocab"]
        self.pos = {e: i for i, e in enumerate(self.vocab)}
        self.idf = np.asarray(self.m["idf"], dtype=np.float64)
        self.normal_mean = np.asarray(self.m["normal_mean"], dtype=np.float64)
        self.has_labels = bool(self.m["dataset"]["has_labels"]) and self.m["totals"]["labeled_blocks"] > 0
        self._templates: dict[str, str] | None = None
        self._timeline_cache: dict[str, Timeline] = {}
        self._summary: Summary | None = None
        self._alerts = self._build_alerts()

    # ------------------------------------------------------------------ nội bộ
    def _search(self, index: str, **kw: Any) -> dict[str, Any]:
        return self.es.search(index=self.ix[index], **kw)

    def _template_map(self) -> dict[str, str]:
        if self._templates is None:
            hits = self._search("events", size=1000, query={"match_all": {}})["hits"]["hits"]
            self._templates = {h["_source"]["event_id"]: h["_source"].get("template") or "" for h in hits}
        return self._templates

    # ------------------------------------------------------------------ meta / summary
    def meta(self) -> Meta:
        return c.build_meta(self.m, "elasticsearch")

    def summary(self) -> Summary:
        if self._summary is None:
            r = self._search("error-stats", size=0, aggs={
                "lv": {"terms": {"field": "level", "size": 10}, "aggs": {"n": {"sum": {"field": "n"}}}},
            })
            per = {b["key"]: int(b["n"]["value"]) for b in r["aggregations"]["lv"]["buckets"]}
            total, blocks = int(self.m["totals"]["lines"]), int(self.m["totals"]["blocks"])
            flagged = self.es.count(index=self.ix["anomalies"], query={"term": {f"{PRIMARY}_flag": True}})["count"]
            errors = per.get("ERROR", 0) + per.get("FATAL", 0)
            self._summary = Summary(
                total_lines=total, total_blocks=blocks, anomalous_blocks=flagged,
                anomaly_rate=flagged / blocks if blocks else 0.0, warn_lines=per.get("WARN", 0), error_lines=errors,
                error_rate=errors / total if total else 0.0, active_alerts=len(self._alerts),
            )
        return self._summary

    # ------------------------------------------------------------------ timeline / components
    def timeline(self, bucket: str) -> Timeline:
        if bucket in self._timeline_cache:
            return self._timeline_cache[bucket]
        sec = BUCKET_SECONDS[bucket]
        interval = f"{sec}s"
        r = self._search("error-stats", size=0, aggs={"t": {
            "date_histogram": {"field": "ts", "fixed_interval": interval, "min_doc_count": 1},
            "aggs": {"lv": {"terms": {"field": "level", "size": 10}, "aggs": {"n": {"sum": {"field": "n"}}}}},
        }})
        per: dict[int, dict[str, int]] = {}
        for b in r["aggregations"]["t"]["buckets"]:
            per[int(b["key"] // 1000)] = {x["key"]: int(x["n"]["value"]) for x in b["lv"]["buckets"]}
        a = self._search("anomalies", size=0, query={"term": {f"{PRIMARY}_flag": True}}, aggs={"t": {
            "date_histogram": {"field": "first_ts", "fixed_interval": interval, "min_doc_count": 1},
        }})
        anom = {int(b["key"] // 1000): b["doc_count"] for b in a["aggregations"]["t"]["buckets"]}

        keys = list(per) + list(anom)
        base, top = min(keys), max(keys)
        pts = []
        for ts in range(base, top + sec, sec):
            lv = per.get(ts, {})
            pts.append(TimelinePoint(
                ts=dt(ts), info=lv.get("INFO", 0), warn=lv.get("WARN", 0), error=lv.get("ERROR", 0),
                fatal=lv.get("FATAL", 0), anomalies=anom.get(ts, 0),
            ))
        out = Timeline(bucket=bucket, points=pts)  # type: ignore[arg-type]
        self._timeline_cache[bucket] = out
        return out

    def components(self, limit: int) -> list[ComponentStat]:
        r = self._search("error-stats", size=0, aggs={"c": {
            "terms": {"field": "component", "size": 500},
            "aggs": {"lv": {"terms": {"field": "level", "size": 10}, "aggs": {"n": {"sum": {"field": "n"}}}}},
        }})
        rows = []
        for b in r["aggregations"]["c"]["buckets"]:
            lv = {x["key"]: int(x["n"]["value"]) for x in b["lv"]["buckets"]}
            rows.append(ComponentStat(
                component=b["key"], total=sum(lv.values()), warn=lv.get("WARN", 0), error=lv.get("ERROR", 0),
                fatal=lv.get("FATAL", 0),
            ))
        rows.sort(key=lambda r: (r.error + r.fatal, r.warn, r.total), reverse=True)
        return rows[:limit]

    # ------------------------------------------------------------------ alerts
    def _build_alerts(self) -> list[Alert]:
        win = int(self.m.get("window_seconds", 60))
        sp = self._search("spikes", size=c.MAX_SPIKE_ALERTS, sort=[{"z": "desc"}], query={"match_all": {}})["hits"]["hits"]
        alerts = [c.spike_alert(s["component"], _epoch(s["ts"]), s["n"], float(s["mean"]), float(s["z"]), win)
                  for s in (h["_source"] for h in sp)]
        thr = c.threshold_of(self.m, PRIMARY)
        top = self._search(
            "anomalies", size=c.MAX_BLOCK_ALERTS, query={"term": {f"{PRIMARY}_flag": True}},
            sort=[{f"{PRIMARY}_score": "desc"}, {"block_id": "asc"}],
        )["hits"]["hits"]
        for h in top:
            s = h["_source"]
            alerts.append(c.block_alert(
                s["block_id"], float(s[f"{PRIMARY}_score"]), thr, _epoch(s["first_ts"]), int(s["n_lines"]), int(s["n_error"]),
            ))
        alerts.sort(key=lambda a: a.ts, reverse=True)
        return alerts

    def alerts(self, severity: Severity | None, limit: int) -> list[Alert]:
        return [a for a in self._alerts if severity is None or a.severity == severity][:limit]

    # ------------------------------------------------------------------ anomalies
    def _item(self, s: dict[str, Any], model: ModelName) -> AnomalyItem:
        return AnomalyItem(
            block_id=s["block_id"], model=model, anomaly_score=round(float(s[f"{model}_score"]), 4),
            is_anomaly=bool(s[f"{model}_flag"]), cluster=s.get("cluster") if model == "kmeans" else None,
            first_ts=dt(_epoch(s["first_ts"])), last_ts=dt(_epoch(s["last_ts"])), line_count=int(s["n_lines"]),
            warn_count=int(s["n_warn"]), error_count=int(s["n_error"]), top_events=list(s.get("top_events") or []),
        )

    def anomalies(self, model, only_flagged, min_score, q, sort, page, page_size) -> AnomalyPage:
        m = model or PRIMARY
        flt: list[dict[str, Any]] = []
        if only_flagged:
            flt.append({"term": {f"{m}_flag": True}})
        if min_score is not None:
            flt.append({"range": {f"{m}_score": {"gte": min_score}}})  # điểm đã làm tròn 4 chữ số lúc nạp, giống hiển thị
        if q:
            flt.append({"wildcard": {"block_id": {"value": f"*{_wildcard_escape(q)}*", "case_insensitive": True}}})
        r = self._search(
            "anomalies", query={"bool": {"filter": flt}}, sort=SORTS[sort](m), from_=(page - 1) * page_size,
            size=page_size, track_total_hits=True,
        )
        items = [self._item(h["_source"], m) for h in r["hits"]["hits"]]
        return AnomalyPage(items=items, total=int(r["hits"]["total"]["value"]), page=page, page_size=page_size)

    def _line(self, s: dict[str, Any]) -> LogLine:
        return LogLine(
            ts=dt(_epoch(s["ts"])), level=level_of(s["level"]), component=s["component"],  # type: ignore[arg-type]
            block_id=s.get("block_id"), content=s["content"], template=s.get("template") or "", event_id=s["event_id"],
        )

    def anomaly_detail(self, block_id: str, model: ModelName | None) -> AnomalyDetail | None:
        from elasticsearch import NotFoundError

        try:
            s = self.es.get(index=self.ix["anomalies"], id=block_id)["_source"]
        except NotFoundError:
            return None
        m = model or PRIMARY
        counts = np.zeros(len(self.vocab))
        for eid, n in (s.get("counts") or {}).items():
            if eid in self.pos:
                counts[self.pos[eid]] = n
        lines = self._search(
            "logs", query={"term": {"block_id": block_id}}, sort=[{"ts": "asc"}], size=2000,
        )["hits"]["hits"]
        lab = s.get("label")
        return AnomalyDetail(
            item=self._item(s, m), threshold=round(c.threshold_of(self.m, m), 4),
            label=lab if lab in ("Normal", "Anomaly") else None,
            scores=[ModelScore(model=k, score=round(float(s[f"{k}_score"]), 4), is_anomaly=bool(s[f"{k}_flag"]))
                    for k in MODEL_ORDER],
            reasons=c.build_reasons(counts, self.normal_mean, self.idf, self.vocab, self._template_map()),
            timeline=[self._line(h["_source"]) for h in lines],
        )

    # ------------------------------------------------------------------ events / models
    def events(self, sort: str, limit: int) -> list[EventTemplate]:
        field = "count" if sort == "count_desc" else "lift"
        hits = self._search("events", query={"match_all": {}}, sort=[{field: "desc"}], size=limit)["hits"]["hits"]
        return [
            EventTemplate(
                event_id=s["event_id"], template=s.get("template") or "", level=level_of(s.get("level") or "INFO"),  # type: ignore[arg-type]
                count=int(s["count"]), block_count=int(s["block_count"]), anomaly_ratio=float(s["anomaly_ratio"]),
                lift=float(s["lift"]),
            )
            for s in (h["_source"] for h in hits)
        ]

    def models(self) -> list[ModelEval]:
        return c.build_model_evals(self.m)

    def score_distribution(self, model: ModelName, bins: int) -> ScoreDistribution | None:
        if model not in MODEL_ORDER:
            return None
        field = f"{model}_score"
        st = self._search("anomalies", size=0, aggs={
            "lo": {"min": {"field": field}}, "p": {"percentiles": {"field": field, "percents": [99.8]}},
        })["aggregations"]
        lo, hi = float(st["lo"]["value"]), float(next(iter(st["p"]["values"].values())))
        hi = hi if hi > lo else lo + 1.0
        edges = np.linspace(lo, hi, bins + 1)
        ranges = [{"to": float(edges[1])}]
        ranges += [{"from": float(edges[i]), "to": float(edges[i + 1])} for i in range(1, bins - 1)]
        ranges.append({"from": float(edges[bins - 1])})  # điểm vượt p99,8 gộp vào cột cuối, như bản tệp
        anomaly = {"term": {"label": "Anomaly"}} if self.has_labels else {"term": {f"{model}_flag": True}}
        r = self._search("anomalies", size=0, aggs={"h": {
            "range": {"field": field, "ranges": ranges}, "aggs": {"an": {"filter": anomaly}},
        }})["aggregations"]["h"]["buckets"]
        return ScoreDistribution(
            model=model, threshold=round(c.threshold_of(self.m, model), 4),
            bins=[
                ScoreBin(
                    lower=float(edges[i]), upper=float(edges[i + 1]), normal=b["doc_count"] - b["an"]["doc_count"],
                    anomaly=b["an"]["doc_count"],
                )
                for i, b in enumerate(r)
            ],
        )

    # ------------------------------------------------------------------ logs
    def logs(self, q, level, component, block_id, start: datetime | None, end: datetime | None, page, page_size) -> LogPage:
        flt: list[dict[str, Any]] = []
        if block_id:
            flt.append({"term": {"block_id": block_id}})
        else:  # dòng chứa nhiều block được lưu nhiều bản (mỗi block một bản): chỉ lấy một bản
            flt.append({"bool": {
                "should": [{"bool": {"must_not": {"exists": {"field": "block_pos"}}}}, {"term": {"block_pos": 0}}],
                "minimum_should_match": 1,
            }})
        if level:
            flt.append({"term": {"level": level}})
        if component:
            flt.append({"term": {"component": component}})
        rng: dict[str, str] = {}
        if start:
            rng["gte"] = c.aware(start).strftime("%Y-%m-%dT%H:%M:%SZ")
        if end:
            rng["lte"] = c.aware(end).strftime("%Y-%m-%dT%H:%M:%SZ")
        if rng:
            flt.append({"range": {"ts": rng}})
        must = [{"match_phrase": {"content": q}}] if q else []
        r = self._search(
            "logs", query={"bool": {"filter": flt, "must": must}}, sort=[{"ts": "desc"}],
            from_=(page - 1) * page_size, size=page_size, track_total_hits=True,
        )
        return LogPage(
            items=[self._line(h["_source"]) for h in r["hits"]["hits"]], total=int(r["hits"]["total"]["value"]),
            page=page, page_size=page_size,
        )

