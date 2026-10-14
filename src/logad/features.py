"""Trích đặc trưng từ log đã parse.

Hai tầng đặc trưng:
1. Theo phiên (session) = block_id  -> đầu vào cho mô hình phát hiện bất thường.
2. Theo cửa sổ thời gian            -> thống kê lỗi cho dashboard + phát hiện đột biến (z-score).
"""
from __future__ import annotations

import math

from pyspark.ml.feature import Normalizer, VectorAssembler
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

NORMALIZE_MODES = ("none", "l2", "tfidf")


def build_vocab(parsed_df: DataFrame) -> list[str]:
    """Danh sách event_id xuất hiện trong ít nhất một block (sắp theo tên để ổn định giữa các lần chạy)."""
    rows = parsed_df.where(F.col("block_id").isNotNull()).select("event_id").distinct().collect()
    return sorted(r["event_id"] for r in rows)


def build_event_count_matrix(
    parsed_df: DataFrame, vocab: list[str] | None = None, normalize: str = "tfidf", idf: list[float] | None = None,
) -> tuple[DataFrame, dict]:
    """Mỗi block -> vector đếm số lần xuất hiện của từng event (bag-of-events) + vài đặc trưng vô hướng.

    Trả về (df, meta):
      df gồm: block_id, counts (Vector đếm thô), features (Vector đã chuẩn hóa, dùng cho KMeans),
              n_lines, n_events, n_warn, n_error (ERROR + FATAL), duration_s, first_ts, last_ts
      meta = {"vocab": [...], "idf": [...], "normalize": ...}  -> lưu lại để suy luận trên dữ liệu mới

    normalize:
      none  : features = counts
      l2    : log1p(counts) rồi chuẩn hóa L2
      tfidf : log1p(counts) * idf rồi chuẩn hóa L2   (idf = ln((N+1)/(df+1)) + 1, tính trên các block)
    Truyền `vocab`/`idf` (từ meta cũ) để dùng lại đúng không gian đặc trưng khi suy luận.
    """
    if normalize not in NORMALIZE_MODES:
        raise ValueError(f"normalize phải là một trong {NORMALIZE_MODES}, nhận {normalize!r}")

    blocks = parsed_df.where(F.col("block_id").isNotNull())
    vocab = vocab if vocab is not None else build_vocab(blocks)
    if not vocab:
        raise ValueError("Không có block nào trong dữ liệu đã parse (block_id rỗng hết).")
    cols = [f"e_{e}" for e in vocab]

    # một lượt groupBy + pivot với danh sách vocab cho trước (nhanh hơn pivot tự dò giá trị)
    pivot = blocks.groupBy("block_id").pivot("event_id", vocab).count()
    pivot = pivot.toDF("block_id", *cols).na.fill(0)

    is_warn = (F.col("level") == "WARN").cast("int")
    is_err = F.col("level").isin("ERROR", "FATAL").cast("int")
    scalars = blocks.groupBy("block_id").agg(
        F.count("*").alias("n_lines"),
        F.countDistinct("event_id").alias("n_events"),
        F.sum(is_warn).alias("n_warn"),
        F.sum(is_err).alias("n_error"),
        F.min("ts").alias("first_ts"),
        F.max("ts").alias("last_ts"),
    ).withColumn("duration_s", F.unix_timestamp("last_ts") - F.unix_timestamp("first_ts"))

    df = pivot.join(scalars, "block_id")
    df = VectorAssembler(inputCols=cols, outputCol="counts").transform(df)

    if normalize == "none":
        df = df.withColumn("features", F.col("counts"))
        idf = [1.0] * len(vocab)
    else:
        if normalize == "tfidf":
            if idf is None:
                n = df.count()
                dfreq = df.agg(*[F.sum((F.col(c) > 0).cast("int")).alias(c) for c in cols]).first()
                idf = [math.log((n + 1) / (dfreq[c] + 1)) + 1 for c in cols]
        else:
            idf = [1.0] * len(vocab)
        weighted = [f"w_{c}" for c in cols]
        for c, w, k in zip(cols, weighted, idf, strict=True):
            df = df.withColumn(w, F.log1p(F.col(c)) * F.lit(float(k)))
        df = VectorAssembler(inputCols=weighted, outputCol="_weighted").transform(df)
        df = Normalizer(inputCol="_weighted", outputCol="features", p=2.0).transform(df)
        df = df.drop(*weighted, "_weighted")

    df = df.drop(*cols).select(
        "block_id", "counts", "features", "n_lines", "n_events", "n_warn", "n_error", "duration_s", "first_ts", "last_ts",
    )
    return df, {"vocab": vocab, "idf": idf, "normalize": normalize}


def build_window_error_stats(parsed_df: DataFrame, window_seconds: int = 60) -> DataFrame:
    """Số dòng theo (cửa sổ thời gian, component, mức độ). Cột: ts (đầu cửa sổ), component, level, n.

    Dùng cho dashboard (lỗi theo thời gian / theo component) và phát hiện đột biến lỗi (z-score).
    """
    return (
        parsed_df.groupBy(F.window("ts", f"{int(window_seconds)} seconds").alias("w"), "component", "level")
        .count()
        .select(F.col("w.start").alias("ts"), "component", "level", F.col("count").alias("n"))
    )
