"""Mô hình chính: KMeans (Spark MLlib), điểm bất thường = khoảng cách Euclid tới tâm cụm gần nhất.

Ý tưởng: phần lớn block bình thường tạo vài cụm lớn, chặt; block bất thường nằm xa mọi tâm cụm
hoặc rơi vào cụm rất nhỏ. Ngưỡng = percentile của điểm (cfg models.kmeans.threshold_percentile).

Huấn luyện và chấm điểm tách riêng: `score_with_centers` chỉ cần tâm cụm đã lưu (JSON), không cần Spark ML model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.functions import vector_to_array
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from sklearn.metrics import average_precision_score

from logad.splits import VAL, take_split


def select_k(
    features_df: DataFrame,
    k_candidates: list[int],
    seed: int,
    max_iter: int = 30,
    sample: int = 100_000,
    labels_df: DataFrame | None = None,
    positive: str = "Anomaly",
    threshold_percentile: float = 97.0,
    k_default: int = 4,
) -> tuple[int, list[dict]]:
    """Chọn k. Trả về (k, bảng kết quả từng k).

    - Có nhãn (`labels_df`): mỗi k được huấn luyện KHÔNG giám sát trên mọi block, rồi chấm PR-AUC trên nửa `val`
      (xem logad.splits). Chọn k có PR-AUC cao nhất (hòa thì lấy k nhỏ hơn).
    - Không có nhãn: dùng `k_default`. KHÔNG chọn theo silhouette: silhouette thiên về k lớn, mà k lớn làm mỗi kiểu bất thường
      tự lập một cụm nên điểm khoảng cách ≈ 0 và bị bỏ sót (đã kiểm chứng trên dữ liệu mô phỏng: k nhỏ F1 ≈ 0,95, k lớn ≈ 0,4).

    Bảng kết quả luôn có silhouette (trên mẫu tối đa `sample` block) và chi phí huấn luyện để đưa vào báo cáo.
    """
    n = features_df.count()
    sampled = features_df.select("features")
    if n > sample:
        sampled = sampled.sample(False, sample / n, seed)
    sampled = sampled.cache()
    evaluator = ClusteringEvaluator(
        featuresCol="features", predictionCol="prediction", metricName="silhouette", distanceMeasure="squaredEuclidean",
    )
    val_labels = None
    if labels_df is not None:
        val_labels = take_split(labels_df.withColumnRenamed("label", "_label"), VAL).select(
            "block_id", (F.col("_label") == positive).cast("int").alias("y"),
        ).cache()

    results: list[dict] = []
    for k in sorted(set(k_candidates)):
        if k < 2 or k >= n:
            continue
        model = KMeans(k=k, seed=seed, maxIter=max_iter, featuresCol="features").fit(features_df.select("features"))
        row: dict = {"k": int(k), "training_cost": float(model.summary.trainingCost)}
        pred = model.transform(sampled)
        row["silhouette"] = float(evaluator.evaluate(pred)) if pred.select("prediction").distinct().count() >= 2 else None
        if val_labels is not None:
            scored, _ = score_with_centers(features_df, np.array(model.clusterCenters()), percentile=threshold_percentile)
            pdf = scored.join(val_labels, "block_id").select("anomaly_score", "y").toPandas()
            row["val_pr_auc"] = float(average_precision_score(pdf["y"], pdf["anomaly_score"])) if pdf["y"].sum() else None
        results.append(row)
    sampled.unpersist()
    if val_labels is not None:
        val_labels.unpersist()
    if not results:
        raise ValueError("Không huấn luyện được k nào (dữ liệu quá ít).")

    if val_labels is not None and any(r.get("val_pr_auc") is not None for r in results):
        best = max((r for r in results if r.get("val_pr_auc") is not None), key=lambda r: (r["val_pr_auc"], -r["k"]))
        return int(best["k"]), results
    k = k_default if any(r["k"] == k_default for r in results) else results[0]["k"]
    return int(k), results


def _assign_udf(spark: SparkSession, centers: np.ndarray):
    bc = spark.sparkContext.broadcast(centers)

    @F.pandas_udf("array<double>")
    def assign(feat: pd.Series) -> pd.Series:
        x = np.vstack(feat.to_numpy())
        c = bc.value
        d = np.sqrt(((x[:, None, :] - c[None, :, :]) ** 2).sum(axis=-1))  # (n, k)
        j = d.argmin(axis=1)
        return pd.Series(list(np.column_stack([j, d[np.arange(len(j)), j]])))

    return assign


def score_with_centers(
    features_df: DataFrame, centers: np.ndarray, threshold: float | None = None, percentile: float | None = None,
) -> tuple[DataFrame, float]:
    """Gán mỗi block vào tâm gần nhất và tính điểm = khoảng cách tới tâm đó.

    Truyền `threshold` (khi suy luận bằng ngưỡng đã lưu) HOẶC `percentile` (khi huấn luyện: ngưỡng = percentile của điểm).
    Trả về (DataFrame[block_id, cluster, anomaly_score, is_anomaly], ngưỡng).
    """
    if (threshold is None) == (percentile is None):
        raise ValueError("Chỉ truyền đúng một trong hai: threshold hoặc percentile")
    spark = features_df.sparkSession
    assign = _assign_udf(spark, np.asarray(centers, dtype=float))
    df = features_df.select("block_id", vector_to_array("features").alias("_f"))
    df = df.withColumn("_a", assign("_f")).select(
        "block_id", F.col("_a")[0].cast("int").alias("cluster"), F.col("_a")[1].alias("anomaly_score"),
    )
    if threshold is None:
        threshold = float(df.approxQuantile("anomaly_score", [percentile / 100.0], 0.0005)[0])
    return df.withColumn("is_anomaly", (F.col("anomaly_score") > F.lit(threshold)).cast("int")), float(threshold)


def fit_and_score(
    features_df: DataFrame, k: int, seed: int, threshold_percentile: float, max_iter: int = 30,
) -> tuple[DataFrame, dict]:
    """Huấn luyện KMeans(k) rồi chấm điểm mọi block.

    Trả về (scored_df, info). `info` đủ để lưu thành mô hình và chấm điểm lại sau này:
    {k, seed, threshold, threshold_percentile, centers, cluster_sizes, training_cost}
    """
    model = KMeans(k=k, seed=seed, maxIter=max_iter, featuresCol="features").fit(features_df)
    centers = np.array(model.clusterCenters())
    scored, threshold = score_with_centers(features_df, centers, percentile=threshold_percentile)
    scored = scored.cache()
    sizes = {int(r["cluster"]): int(r["n"]) for r in scored.groupBy("cluster").agg(F.count("*").alias("n")).collect()}
    info = {
        "k": int(k), "seed": int(seed), "threshold": threshold, "threshold_percentile": float(threshold_percentile),
        "centers": centers.tolist(), "cluster_sizes": dict(sorted(sizes.items())),
        "training_cost": float(model.summary.trainingCost),
    }
    return scored, info
