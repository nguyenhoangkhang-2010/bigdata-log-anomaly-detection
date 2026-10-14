"""Ghi kết quả vào Elasticsearch để API/Kibana đọc.

Dùng `elasticsearch.helpers.bulk` từ driver (không cần jar es-hadoop, không cần `--packages`), đủ cho cỡ dữ liệu của đồ án
(vài trăm nghìn tài liệu). Dữ liệu được kéo dần về driver bằng `toLocalIterator`, không nạp hết vào bộ nhớ.

Thời gian được đổi sang chuỗi ISO UTC NGAY TRONG Spark (phiên đặt UTC): nếu để Python tự đổi thì datetime bị hiểu theo múi giờ
của máy và lệch giờ.
"""
from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import TimestampNTZType, TimestampType

_NUM = {"type": "float"}
_KW = {"type": "keyword"}
_DATE = {"type": "date"}

# Ánh xạ tường minh cho từng loại index (không để Elasticsearch tự đoán kiểu).
MAPPINGS: dict[str, dict[str, Any]] = {
    "anomalies": {"properties": {
        "block_id": _KW, "first_ts": _DATE, "last_ts": _DATE, "duration_s": _NUM,
        "n_lines": {"type": "integer"}, "n_events": {"type": "integer"}, "n_warn": {"type": "integer"}, "n_error": {"type": "integer"},
        "cluster": {"type": "integer"}, "label": _KW,
        "kmeans_score": _NUM, "kmeans_flag": {"type": "boolean"},
        "iforest_score": _NUM, "iforest_flag": {"type": "boolean"},
        "zscore_score": _NUM, "zscore_flag": {"type": "boolean"},
        "flagged_by": _KW,
    }},
    "error_stats": {"properties": {"ts": _DATE, "component": _KW, "level": _KW, "n": {"type": "integer"}}},
    "spikes": {"properties": {"ts": _DATE, "component": _KW, "n": {"type": "integer"}, "mean": _NUM, "z": _NUM}},
    "logs": {"properties": {
        "ts": _DATE, "level": _KW, "component": _KW, "block_id": _KW, "event_id": _KW, "template": _KW,
        "content": {"type": "text"}, "pid": {"type": "integer"},
    }},
    "models": {"properties": {
        "name": _KW, "split": _KW, "precision": _NUM, "recall": _NUM, "f1": _NUM, "pr_auc": _NUM, "train_seconds": _NUM,
        "tp": {"type": "integer"}, "fp": {"type": "integer"}, "fn": {"type": "integer"}, "tn": {"type": "integer"},
        "n_blocks": {"type": "integer"}, "n_labeled": {"type": "integer"}, "n_positive": {"type": "integer"},
    }},
}


def _clean(v: Any) -> Any:
    """Giá trị Python an toàn cho JSON: NaN/Inf -> None, numpy -> số thường."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):  # numpy scalar
        return _clean(v.item())
    return v


def timestamps_to_iso(df: DataFrame) -> DataFrame:
    """Đổi mọi cột thời gian thành chuỗi ISO-8601 UTC (ví dụ 2008-11-09T20:36:15Z)."""
    for f in df.schema.fields:
        if isinstance(f.dataType, (TimestampType, TimestampNTZType)):
            df = df.withColumn(f.name, F.date_format(F.col(f.name), "yyyy-MM-dd'T'HH:mm:ss'Z'"))
    return df


def iter_actions(df: DataFrame, index: str, id_col: str | None = None) -> Iterator[dict[str, Any]]:
    for row in timestamps_to_iso(df).toLocalIterator():
        doc = {k: _clean(v) for k, v in row.asDict(recursive=True).items()}
        action: dict[str, Any] = {"_index": index, "_source": doc}
        if id_col and doc.get(id_col) is not None:
            action["_id"] = str(doc[id_col])
        yield action


def ensure_index(es: Any, index: str, kind: str, recreate: bool = True) -> None:
    """Tạo index với ánh xạ tường minh. recreate=True: xóa index cũ cùng tên (chạy lại pipeline không bị nhân đôi dữ liệu)."""
    if recreate and es.indices.exists(index=index):
        es.indices.delete(index=index)
    if not es.indices.exists(index=index):
        es.indices.create(index=index, mappings=MAPPINGS[kind], settings={"number_of_shards": 1, "number_of_replicas": 0})


def write_df(
    df: DataFrame, index: str, es_host: str, kind: str, id_col: str | None = None,
    recreate: bool = True, batch: int = 2000, client: Any = None,
) -> dict[str, int]:
    """Ghi DataFrame vào index `index`. `kind` chọn ánh xạ (anomalies | error_stats | spikes | logs | models).

    Trả về {"indexed": số tài liệu ghi được, "errors": số lỗi}. `client` cho phép truyền Elasticsearch giả khi kiểm thử.
    """
    if kind not in MAPPINGS:
        raise ValueError(f"kind phải là một trong {sorted(MAPPINGS)}, nhận {kind!r}")
    from elasticsearch import Elasticsearch, helpers

    es = client or Elasticsearch(es_host, request_timeout=120)
    ensure_index(es, index, kind, recreate=recreate)
    ok, errors = helpers.bulk(es, iter_actions(df, index, id_col), chunk_size=batch, raise_on_error=False, stats_only=False)
    es.indices.refresh(index=index)
    return {"indexed": int(ok), "errors": len(errors) if isinstance(errors, list) else int(errors)}
