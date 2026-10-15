"""Job 07 - gom kết quả pipeline thành các tệp nhỏ gọn cho backend/giao diện đọc (xem src/logad/serving.py).

Chạy được ở cả hai chế độ: dữ liệu trung gian đọc từ HDFS hoặc thư mục local, kết quả luôn ghi ra thư mục cục bộ `paths.serving`. Backend dùng `LOGAD_DATA_SOURCE=files` để đọc thư mục này,
không cần Elasticsearch.
"""
from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from _common import run_standalone
from pyspark.sql import functions as F

from logad import serving
from logad.config import resolve_paths
from logad.evaluation import read_labels
from logad.storage import load_json, load_parquet


def _epoch(col: str, alias: str):
    return F.unix_timestamp(col).alias(alias)


def build_blocks(spark, paths) -> tuple[pd.DataFrame, np.ndarray, dict]:
    """Bảng block: đặc trưng vô hướng + điểm/cờ của 3 mô hình + nhãn thật. Trả về (bảng, ma trận counts, meta features)."""
    meta = load_json(spark, paths.features + "_meta.json")
    feats = load_parquet(spark, paths.features).select(
        "block_id", "counts", _epoch("first_ts", "first_epoch"), _epoch("last_ts", "last_epoch"), "n_lines", "n_warn", "n_error",
    ).toPandas()
    counts = np.vstack(feats.pop("counts").to_numpy()).astype(np.float32)

    for m in serving.MODELS:
        cols = ["block_id", F.col("anomaly_score").alias(f"{m}_score"), (F.col("is_anomaly") == 1).alias(f"{m}_flag")]
        if m == serving.PRIMARY:
            cols.append("cluster")
        feats = feats.merge(load_parquet(spark, paths.results(m)).select(*cols).toPandas(), on="block_id", how="left")
        feats[f"{m}_flag"] = feats[f"{m}_flag"].fillna(False).astype(bool)
        feats[f"{m}_score"] = feats[f"{m}_score"].fillna(0.0)

    feats["label"] = None
    if paths.labels:
        lab = read_labels(spark, paths.labels).toPandas().drop_duplicates("block_id")
        feats = feats.drop(columns="label").merge(lab, on="block_id", how="left")
    return feats, counts, meta


def write_blocks(blocks: pd.DataFrame, counts: np.ndarray, top_events: list[list[str]], out: Path) -> None:
    table = pa.Table.from_pandas(blocks.assign(top_events=top_events), preserve_index=False)
    flat = pa.array(counts.ravel(), type=pa.float32())
    table = table.append_column("counts", pa.FixedSizeListArray.from_arrays(flat, counts.shape[1]))
    pq.write_table(table, out / serving.BLOCKS_FILE)


def build_events(spark, paths, counts: np.ndarray, flagged: np.ndarray, vocab: list[str]) -> pd.DataFrame:
    """Thống kê event + mẫu template và mức log (level hay gặp nhất) của từng event."""
    info = (
        load_parquet(spark, paths.parsed).groupBy("event_id", "level", "template").count().toPandas()
        .sort_values("count", ascending=False).drop_duplicates("event_id")[["event_id", "template", "level"]]
    )
    stats = pd.DataFrame(serving.event_stats(counts, flagged, vocab))
    return stats.merge(info, on="event_id", how="left")


def build_lines(spark, paths, blocks: pd.DataFrame):
    """Dòng WARN/ERROR/FATAL + mọi dòng của block bị KMeans hoặc Isolation Forest gắn cờ."""
    ids = blocks.loc[blocks["kmeans_flag"] | blocks["iforest_flag"], ["block_id"]]
    flagged = spark.createDataFrame(ids)
    parsed = load_parquet(spark, paths.parsed)
    keep = parsed.where(F.col("level") != "INFO").unionByName(parsed.join(F.broadcast(flagged), "block_id", "left_semi"))
    return keep.dropDuplicates(["ts", "component", "content", "block_id"]).select(
        _epoch("ts", "ts_epoch"), "level", "component", "block_id", "event_id", "template", "content", "block_pos",
    )


def run(spark, cfg) -> dict:
    paths = resolve_paths(cfg)
    spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
    out = Path(paths.serving)  # luôn là thư mục cục bộ, dù dữ liệu trung gian nằm trên HDFS
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    blocks, counts, fmeta = build_blocks(spark, paths)
    vocab = fmeta["vocab"]
    idf = np.asarray(fmeta["idf"] if fmeta.get("idf") else np.ones(len(vocab)), dtype=np.float64)
    flagged = blocks[f"{serving.PRIMARY}_flag"].to_numpy()
    tops = serving.top_deviating_events(counts, idf, ~flagged, vocab)
    write_blocks(blocks, counts, tops, out)

    events = build_events(spark, paths, counts, flagged, vocab)
    events.to_parquet(out / serving.EVENTS_FILE, index=False)

    ws = load_parquet(spark, paths.window_stats).select(_epoch("ts", "ts_epoch"), "component", "level", "n").toPandas()
    ws.to_parquet(out / serving.WINDOW_FILE, index=False)
    spikes = load_parquet(spark, f"{paths.results_root}/spikes").select(
        _epoch("ts", "ts_epoch"), "component", "n", "mean", "z",
    ).toPandas()
    spikes.to_parquet(out / serving.SPIKES_FILE, index=False)

    lines = build_lines(spark, paths, blocks).toPandas()  # ~760 nghìn dòng: gom về driver rồi ghi 1 tệp, chạy giống nhau ở local và cụm
    (out / serving.LINES_DIR).mkdir()
    lines.to_parquet(out / serving.LINES_DIR / "part-0.parquet", index=False)

    training = load_json(spark, f"{paths.results_root}/training.json")
    try:
        evaluation = load_json(spark, paths.metrics)
    except Exception:  # chưa có nhãn nên job 05 không tạo metrics
        evaluation = None
    n_lines = int(ws["n"].sum())
    meta = {
        "run_id": datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S"),
        "finished_at_epoch": int(time.time()),
        "version": "0.1.0",
        "dataset": {
            "raw": Path(paths.raw).name,
            "is_synthetic": "synthetic" in str(paths.raw).lower(),
            "sample_lines": cfg["dataset"].get("sample_lines"),
            "has_labels": bool(paths.labels),
        },
        "totals": {"lines": n_lines, "blocks": int(len(blocks)), "labeled_blocks": int(blocks["label"].notna().sum())},
        "time_range": {"start_epoch": int(ws["ts_epoch"].min()), "end_epoch": int(ws["ts_epoch"].max())},
        "window_seconds": cfg["features"]["time_window_seconds"],
        "vocab": vocab,
        "idf": idf.tolist(),
        "training": training,
        "params": cfg["models"],
        "evaluation": evaluation,
    }
    (out / serving.META_FILE).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[07] Xuất tệp phục vụ -> {out}")
    print(f"     {n_lines:,} dòng · {len(blocks):,} block · {len(events)} event · {len(spikes):,} đột biến · "
          f"{int(flagged.sum()):,} block bị KMeans gắn cờ")
    return {"lines": n_lines, "blocks": len(blocks)}


if __name__ == "__main__":
    run_standalone("07-serving", run)
