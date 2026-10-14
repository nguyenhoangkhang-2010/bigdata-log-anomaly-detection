"""Job 06 - đẩy kết quả vào Elasticsearch (block + điểm của 3 mô hình, thống kê lỗi, đột biến, dòng WARN/ERROR, metrics).

Cần Elasticsearch đang chạy: `docker compose --profile search up -d`. Đặt ES_HOST nếu không dùng địa chỉ trong cấu hình.
"""
import os

from _common import run_standalone
from pyspark.sql import functions as F

from logad.config import resolve_paths
from logad.es_sink import write_df
from logad.evaluation import read_labels
from logad.storage import load_json, load_parquet

MODELS = ("kmeans", "iforest", "zscore")


def build_anomaly_docs(spark, paths, labels=None):
    """Mỗi block một tài liệu: đặc trưng vô hướng + điểm/cờ của cả ba mô hình + nhãn thật (nếu có)."""
    feats = load_parquet(spark, paths.features).select(
        "block_id", "n_lines", "n_events", "n_warn", "n_error", "duration_s", "first_ts", "last_ts",
    )
    df = feats
    for m in MODELS:
        r = load_parquet(spark, paths.results(m)).select(
            "block_id", F.col("anomaly_score").alias(f"{m}_score"), (F.col("is_anomaly") == 1).alias(f"{m}_flag"),
            *([F.col("cluster")] if m == "kmeans" else []),
        )
        df = df.join(r, "block_id", "left")
    flags = [F.when(F.col(f"{m}_flag"), F.lit(m)) for m in MODELS]
    df = df.withColumn("flagged_by", F.concat_ws(",", *flags))
    if labels is not None:
        df = df.join(labels, "block_id", "left")
    return df


def run(spark, cfg) -> dict:
    paths = resolve_paths(cfg)
    es = cfg["elasticsearch"]
    host = os.environ.get("ES_HOST", es["host"])
    labels = read_labels(spark, paths.labels) if paths.labels else None
    out: dict = {}

    anomalies = build_anomaly_docs(spark, paths, labels)
    if not es.get("index_all_blocks", True):
        anomalies = anomalies.where("flagged_by != ''")
    out["anomalies"] = write_df(anomalies, es["index_anomalies"], host, "anomalies", id_col="block_id")

    out["error_stats"] = write_df(load_parquet(spark, paths.window_stats), es["index_error_stats"], host, "error_stats")
    out["spikes"] = write_df(load_parquet(spark, f"{paths.results_root}/spikes"), es["index_spikes"], host, "spikes")

    logs = load_parquet(spark, paths.parsed).where("level != 'INFO'").select(
        "ts", "level", "component", "block_id", "event_id", "template", "content", "pid",
    ).dropDuplicates(["ts", "component", "content"])  # dòng có nhiều block bị explode: chỉ giữ một bản
    out["logs"] = write_df(logs, es["index_logs"], host, "logs")

    try:
        metrics = load_json(spark, paths.metrics)
        rows = [{"name": k, "split": metrics.get("split"), **{x: v for x, v in m.items() if not isinstance(v, (dict, list))}}
                for k, m in metrics["models"].items()]
        out["models"] = write_df(spark.createDataFrame(rows), es["index_models"], host, "models", id_col="name")
    except Exception as e:  # chưa chạy bước 05 (không có nhãn): bỏ qua
        print(f"     (bỏ qua index metrics: {type(e).__name__})")

    print(f"[06] Elasticsearch {host}")
    for name, r in out.items():
        print(f"     {name:<12} {r['indexed']:>9,} tài liệu · {r['errors']} lỗi")
    return out


if __name__ == "__main__":
    run_standalone("06-index", run)
