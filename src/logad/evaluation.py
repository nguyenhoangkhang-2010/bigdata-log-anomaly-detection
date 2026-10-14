"""Đánh giá bộ phát hiện bất thường với nhãn LogHub (Normal/Anomaly theo block).

Nhãn CHỈ dùng để chấm điểm, không dùng khi huấn luyện (học không giám sát).
"""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from sklearn.metrics import average_precision_score

from logad.splits import take_split


def read_labels(spark: SparkSession, path: str) -> DataFrame:
    """anomaly_label.csv (BlockId,Label) -> DataFrame[block_id, label]."""
    df = spark.read.csv(path, header=True)
    return df.select(F.col("BlockId").alias("block_id"), F.col("Label").alias("label"))


def evaluate(pred_df: DataFrame, labels_df: DataFrame, positive: str = "Anomaly", split: str | None = None) -> dict:
    """Ghép dự đoán với nhãn theo block_id rồi tính ma trận nhầm lẫn, Precision, Recall, F1 và PR-AUC.

    PR-AUC (average precision) dùng điểm liên tục `anomaly_score`, nên không phụ thuộc ngưỡng; Precision/Recall/F1 tính tại
    ngưỡng đang dùng (`is_anomaly`). Dữ liệu bất thường chỉ vài phần trăm nên không dùng Accuracy.
    """
    if split is not None:  # vd. "test": chỉ chấm trên nửa mà việc chọn siêu tham số chưa nhìn thấy
        pred_df = take_split(pred_df, split)
    joined = pred_df.join(labels_df, "block_id", "inner")
    pdf = joined.select(
        F.col("anomaly_score").cast("double").alias("score"),
        F.col("is_anomaly").cast("int").alias("pred"),
        (F.col("label") == positive).cast("int").alias("y"),
    ).toPandas()

    n_pred = pred_df.count()
    n = len(pdf)
    if n == 0:
        raise ValueError("Không có block nào khớp giữa dự đoán và nhãn (kiểm tra định dạng block_id).")

    y, p = pdf["y"].to_numpy(), pdf["pred"].to_numpy()
    tp = int(((p == 1) & (y == 1)).sum())
    fp = int(((p == 1) & (y == 0)).sum())
    fn = int(((p == 0) & (y == 1)).sum())
    tn = int(((p == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    pr_auc = float(average_precision_score(y, pdf["score"].to_numpy())) if y.sum() > 0 else float("nan")
    return {
        "n_blocks": int(n_pred), "n_labeled": int(n), "label_coverage": n / n_pred if n_pred else 0.0,
        "n_positive": int(y.sum()), "positive_rate": float(y.mean()),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1, "pr_auc": pr_auc,
    }
