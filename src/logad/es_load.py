"""Nạp kết quả pipeline (thư mục serving do job 07 xuất) vào Elasticsearch.

Mỗi loại dữ liệu một index, tên = `<prefix>-<loại>`:

    anomalies   575k tài liệu, mỗi block một tài liệu: điểm + cờ của 3 mô hình, nhãn thật, top_events, counts
    error-stats số dòng theo (cửa sổ 60 giây, component, level)  -> biểu đồ theo thời gian, thành phần sinh lỗi
    spikes      đột biến lỗi (z-score)                          -> cảnh báo
    logs        dòng WARN/ERROR/FATAL + mọi dòng của block bị gắn cờ -> tìm kiếm log, chuỗi sự kiện của block
    events      thống kê từng mẫu sự kiện
    meta        1 tài liệu (_id = "meta"): tổng quan lần chạy, ngưỡng, chỉ số mô hình, từ vựng event, trung bình block bình thường

Đọc theo lô (pyarrow) và bulk theo lô nên bộ nhớ không phụ thuộc kích thước dữ liệu.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from . import serving
from .es_sink import write_records

KINDS = {
    "anomalies": "anomalies", "error-stats": "error_stats", "spikes": "spikes", "logs": "logs", "events": "events",
    "meta": "meta",
}


def index_name(prefix: str, kind: str) -> str:
    return f"{prefix}-{kind}"


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nan_to_none(x: Any) -> Any:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else x


def iter_blocks(path: Path, vocab: list[str], batch: int = 20_000) -> Iterator[dict[str, Any]]:
    """Từng block thành 1 tài liệu. `counts` lưu dạng {event_id: số lần} chỉ với event có xuất hiện."""
    names = np.asarray(vocab)
    for rb in pq.ParquetFile(path).iter_batches(batch_size=batch):
        t = rb.to_pandas()
        counts = np.vstack(t["counts"].to_numpy())
        for i, r in enumerate(t.itertuples(index=False)):
            nz = np.flatnonzero(counts[i])
            doc: dict[str, Any] = {
                "block_id": r.block_id, "first_ts": iso(r.first_epoch), "last_ts": iso(r.last_epoch),
                "duration_s": float(r.last_epoch - r.first_epoch), "n_lines": int(r.n_lines), "n_warn": int(r.n_warn),
                "n_error": int(r.n_error), "n_events": int(len(nz)),
                "cluster": None if _nan_to_none(r.cluster) is None else int(r.cluster),
                "label": _nan_to_none(r.label), "top_events": list(r.top_events),
                "counts": {str(names[j]): int(counts[i, j]) for j in nz},
            }
            flagged = []
            for m in serving.MODELS:
                doc[f"{m}_score"] = round(float(getattr(r, f"{m}_score")), 4)  # làm tròn như giao diện hiển thị
                doc[f"{m}_flag"] = bool(getattr(r, f"{m}_flag"))
                if doc[f"{m}_flag"]:
                    flagged.append(m)
            doc["flagged_by"] = ",".join(flagged)
            yield doc


def iter_parquet_dir(path: Path, convert, batch: int = 50_000) -> Iterator[dict[str, Any]]:
    files = sorted(path.glob("*.parquet")) if path.is_dir() else [path]
    for f in files:
        for rb in pq.ParquetFile(f).iter_batches(batch_size=batch):
            for rec in rb.to_pylist():
                yield convert(rec)


def _ts_row(r: dict[str, Any]) -> dict[str, Any]:
    """ts_epoch (giây Unix) -> ts (chuỗi ISO UTC) cho mọi bản ghi có thời gian."""
    r = dict(r)
    r["ts"] = iso(r.pop("ts_epoch"))
    return r


def normal_mean(path: Path, vocab_size: int) -> list[float]:
    """Số lần trung bình của từng event ở các block KHÔNG bị mô hình chính gắn cờ (để giải thích vì sao một block khác thường)."""
    total, n = np.zeros(vocab_size), 0
    pf = pq.ParquetFile(path)
    for rb in pf.iter_batches(batch_size=50_000, columns=["counts", f"{serving.PRIMARY}_flag"]):
        t = rb.to_pandas()
        keep = ~t[f"{serving.PRIMARY}_flag"].to_numpy(dtype=bool)
        if keep.any():
            total += np.vstack(t["counts"].to_numpy())[keep].sum(axis=0)
            n += int(keep.sum())
    return (total / max(n, 1)).tolist()


def load_serving(
    serving_dir: str | Path, es_host: str, prefix: str = "logad", client: Any = None, recreate: bool = True,
) -> dict[str, dict[str, int]]:
    d = Path(serving_dir)
    meta = json.loads((d / serving.META_FILE).read_text(encoding="utf-8"))
    vocab = meta["vocab"]
    ix = {k: index_name(prefix, k) for k in KINDS}
    kw = {"es_host": es_host, "client": client, "recreate": recreate}
    out: dict[str, dict[str, int]] = {}

    out["anomalies"] = write_records(
        iter_blocks(d / serving.BLOCKS_FILE, vocab), ix["anomalies"], kind="anomalies", id_field="block_id", **kw,
    )
    out["error-stats"] = write_records(
        iter_parquet_dir(d / serving.WINDOW_FILE, _ts_row), ix["error-stats"], kind="error_stats", **kw,
    )
    out["spikes"] = write_records(iter_parquet_dir(d / serving.SPIKES_FILE, _ts_row), ix["spikes"], kind="spikes", **kw)
    out["logs"] = write_records(iter_parquet_dir(d / serving.LINES_DIR, _ts_row), ix["logs"], kind="logs", **kw)
    out["events"] = write_records(
        iter_parquet_dir(d / serving.EVENTS_FILE, dict), ix["events"], kind="events", id_field="event_id", **kw,
    )
    doc = {**meta, "normal_mean": normal_mean(d / serving.BLOCKS_FILE, len(vocab)), "id": "meta"}
    out["meta"] = write_records([doc], ix["meta"], kind="meta", id_field="id", **kw)
    return out
