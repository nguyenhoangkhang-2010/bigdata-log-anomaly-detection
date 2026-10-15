"""Dựng thư mục serving (định dạng do job 07 ghi, xem src/logad/serving.py) từ DemoDataset, để kiểm thử FilesRepository
mà không cần chạy Spark. Chỉ là dữ liệu mô phỏng cho test."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app.demo_data import DemoDataset

MODELS = ("kmeans", "iforest", "zscore")


def build_serving_dir(out: Path, d: DemoDataset) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    n, vocab = len(d.block_ids), list(d.event_ids)
    counts = d.counts.astype(np.float32)

    blocks = pd.DataFrame({
        "block_id": d.block_ids,
        "first_epoch": [t.timestamp() for t in d.first_ts], "last_epoch": [t.timestamp() for t in d.last_ts],
        "n_lines": d.line_count, "n_warn": d.warn_count, "n_error": d.error_count,
        "cluster": d.clusters, "label": np.where(d.y, "Anomaly", "Normal"),
        "top_events": [list(vocab[j] for j in np.argsort(-np.abs(counts[i]))[:2]) for i in range(n)],
    })
    for m in MODELS:
        blocks[f"{m}_score"] = d.scores[m]
        blocks[f"{m}_flag"] = d.flags[m]
    table = pa.Table.from_pandas(blocks, preserve_index=False)
    flat = pa.array(counts.ravel(), type=pa.float32())
    table = table.append_column("counts", pa.FixedSizeListArray.from_arrays(flat, counts.shape[1]))
    pq.write_table(table, out / "blocks.parquet")

    total = counts.sum(0)
    flagged = counts[d.flags["kmeans"]].sum(0)
    base = flagged.sum() / total.sum()
    pd.DataFrame([
        {"event_id": e, "template": d.events[e][0], "level": d.events[e][1], "count": int(total[j]),
         "block_count": int((counts[:, j] > 0).sum()), "anomaly_ratio": float(flagged[j] / total[j]),
         "lift": float(flagged[j] / total[j] / base)}
        for j, e in enumerate(vocab)
    ]).to_parquet(out / "events.parquet", index=False)

    ws = pd.DataFrame({
        "ts_epoch": [int(ln.ts.timestamp()) // 60 * 60 for ln in d.lines],
        "component": [ln.component for ln in d.lines], "level": [ln.level for ln in d.lines], "n": 1,
    }).groupby(["ts_epoch", "component", "level"], as_index=False)["n"].sum()
    ws.to_parquet(out / "window_stats.parquet", index=False)

    err = ws[ws["level"] != "INFO"].sort_values("n", ascending=False).head(5)
    pd.DataFrame({"ts_epoch": err["ts_epoch"], "component": err["component"], "n": err["n"],
                  "mean": 0.2, "z": [10.0, 9.0, 5.0, 4.0, 3.5][: len(err)]}).to_parquet(out / "spikes.parquet", index=False)

    flagged_ids = set(np.array(d.block_ids)[d.flags["kmeans"] | d.flags["iforest"]])
    rows = [
        {"ts_epoch": int(ln.ts.timestamp()), "level": ln.level, "component": ln.component, "block_id": ln.block_id,
         "event_id": ln.event_id, "template": ln.template, "content": ln.content, "block_pos": 0}
        for ln in d.lines if ln.level != "INFO" or ln.block_id in flagged_ids
    ]
    (out / "lines").mkdir(exist_ok=True)
    pd.DataFrame(rows).to_parquet(out / "lines" / "part-0.parquet", index=False)

    ev = {r["name"]: r for r in d.eval_rows}
    models_eval = {
        k: {**{x: ev[k][x] for x in ("precision", "recall", "f1", "pr_auc")}, **ev[k]["confusion"]} for k in MODELS
    }
    meta = {
        "run_id": "run-test", "finished_at_epoch": int(d.finished_at.timestamp()), "version": "0.1.0",
        "dataset": {"raw": "synthetic.log", "is_synthetic": True, "sample_lines": None, "has_labels": True},
        "totals": {"lines": len(d.lines), "blocks": n, "labeled_blocks": n},
        "time_range": {"start_epoch": int(ws["ts_epoch"].min()), "end_epoch": int(ws["ts_epoch"].max())},
        "window_seconds": 60, "vocab": vocab, "idf": [float(x) for x in d.idf],
        "training": {
            "kmeans": {"k": 6, "threshold": d.thr["kmeans"], "train_seconds": 1.0},
            "iforest": {"threshold": d.thr["iforest"], "train_seconds": 1.0},
            "zscore": {"threshold": 3.0, "train_seconds": 0.1},
        },
        "params": {
            "kmeans": {"threshold_percentile": 97, "seed": 42},
            "isolation_forest": {"n_estimators": 100, "contamination": 0.03, "seed": 42},
            "zscore": {"threshold": 3.0},
        },
        "evaluation": {"split": "test", "models": models_eval},
    }
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return out
