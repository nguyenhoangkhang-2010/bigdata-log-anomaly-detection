"""Baseline thống kê bằng z-score, ở hai cấp:

- `score_blocks`: block có số dòng WARN+ERROR cao bất thường so với các block khác.
- `detect_error_spikes`: thời điểm một component sinh lỗi đột biến so với mức nền của chính nó (cho cảnh báo trên dashboard).
"""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def score_blocks(features_df: DataFrame, threshold: float = 3.0) -> tuple[DataFrame, dict]:
    """z = (x - mean) / std với x = n_warn + n_error của block. Điểm = max(z, 0); bất thường khi z > threshold."""
    x = (F.col("n_warn") + F.col("n_error")).cast("double")
    stats = features_df.agg(F.mean(x).alias("mean"), F.stddev_pop(x).alias("std")).first()
    mean, std = float(stats["mean"]), float(stats["std"] or 0.0)
    z = (x - F.lit(mean)) / F.lit(std if std > 0 else 1.0)
    out = features_df.select(
        "block_id",
        F.greatest(z, F.lit(0.0)).alias("anomaly_score"),
        (z > F.lit(float(threshold))).cast("int").alias("is_anomaly"),
    )
    return out, {"mean": mean, "std": std, "threshold": float(threshold)}


def detect_error_spikes(
    window_stats_df: DataFrame, window_seconds: int, threshold: float = 3.0, min_count: int = 3,
) -> DataFrame:
    """Tìm các (cửa sổ, component) có số dòng WARN/ERROR/FATAL vượt mức nền.

    Mức nền tính trên TOÀN BỘ các cửa sổ trong khoảng dữ liệu (kể cả cửa sổ không có lỗi, tính là 0), nên một component
    hiếm khi lỗi sẽ có mức nền gần 0 và dễ bị nhận ra khi bắt đầu lỗi. Cột kết quả: ts, component, n, mean, z.
    """
    bounds = window_stats_df.agg(
        F.unix_timestamp(F.min("ts")).alias("lo"), F.unix_timestamp(F.max("ts")).alias("hi"),
    ).first()
    n_windows = int((bounds["hi"] - bounds["lo"]) // window_seconds) + 1

    bad = (
        window_stats_df.where(F.col("level") != "INFO")
        .groupBy("ts", "component").agg(F.sum("n").alias("n"))
    )
    base = bad.groupBy("component").agg(F.sum("n").alias("s"), F.sum(F.col("n") * F.col("n")).alias("sq"))
    base = base.select(
        "component",
        (F.col("s") / n_windows).alias("mean"),
        F.sqrt(F.greatest(F.col("sq") / n_windows - (F.col("s") / n_windows) ** 2, F.lit(1e-9))).alias("std"),
    )
    out = bad.join(base, "component").withColumn("z", (F.col("n") - F.col("mean")) / F.col("std"))
    return out.where((F.col("z") > threshold) & (F.col("n") >= min_count)).select("ts", "component", "n", "mean", "z")
