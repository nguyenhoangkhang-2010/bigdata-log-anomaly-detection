from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from pyspark.ml.linalg import Vectors, VectorUDT
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

from logad.evaluation import evaluate
from logad.models import isolation_forest_baseline as iforest
from logad.models import kmeans_detector, zscore_detector
from logad.splits import TEST, VAL, take_split, with_split


FEATURES_SCHEMA = StructType([
    StructField("block_id", StringType()), StructField("features", VectorUDT()),
    StructField("n_lines", IntegerType()), StructField("n_events", IntegerType()),
    StructField("n_warn", IntegerType()), StructField("n_error", IntegerType()), StructField("duration_s", DoubleType()),
])


def features_df(spark, vectors, extra=None):
    rows = [(f"b{i}", Vectors.dense(v), *(extra[i] if extra else (1, 1, 0, 0, 0.0))) for i, v in enumerate(vectors)]
    return spark.createDataFrame(rows, FEATURES_SCHEMA)


# ───────────── KMeans ─────────────
def two_blobs_and_outlier(spark):
    rng = np.random.default_rng(0)
    a = rng.normal([1, 0], 0.01, size=(60, 2))
    b = rng.normal([0, 1], 0.01, size=(60, 2))
    return features_df(spark, [*a.tolist(), *b.tolist(), [0.8, 0.8]])


def test_kmeans_outlier_gets_highest_score(spark):
    df = two_blobs_and_outlier(spark)
    scored, info = kmeans_detector.fit_and_score(df, k=2, seed=1, threshold_percentile=97)
    top = scored.orderBy("anomaly_score", ascending=False).first()
    assert top["block_id"] == "b120" and top["is_anomaly"] == 1
    assert info["k"] == 2 and sorted(info["cluster_sizes"].values()) == [60, 61] or sorted(info["cluster_sizes"].values()) == [61, 60]
    assert scored.where("is_anomaly = 1").count() <= 5  # ~3% của 121 block


def test_score_with_saved_centers_reproduces_training_scores(spark):
    df = two_blobs_and_outlier(spark)
    scored, info = kmeans_detector.fit_and_score(df, k=2, seed=1, threshold_percentile=97)
    again, thr = kmeans_detector.score_with_centers(df, np.array(info["centers"]), threshold=info["threshold"])
    a = {r["block_id"]: r["anomaly_score"] for r in scored.collect()}
    b = {r["block_id"]: r["anomaly_score"] for r in again.collect()}
    assert thr == info["threshold"]
    assert all(a[k] == pytest.approx(b[k]) for k in a)


def test_score_with_centers_needs_exactly_one_threshold_arg(spark):
    df = two_blobs_and_outlier(spark)
    centers = np.array([[1.0, 0.0], [0.0, 1.0]])
    with pytest.raises(ValueError):
        kmeans_detector.score_with_centers(df, centers)
    with pytest.raises(ValueError):
        kmeans_detector.score_with_centers(df, centers, threshold=0.1, percentile=97)


def test_select_k_without_labels_uses_default_not_silhouette(spark):
    df = two_blobs_and_outlier(spark)
    k, table = kmeans_detector.select_k(df, [2, 3, 4], seed=1, k_default=3)
    assert k == 3
    assert [r["k"] for r in table] == [2, 3, 4] and all("silhouette" in r for r in table)


def test_select_k_with_labels_picks_best_val_pr_auc(spark):
    df = two_blobs_and_outlier(spark)
    ids = [r["block_id"] for r in df.select("block_id").collect()]
    labels = spark.createDataFrame([(i, "Anomaly" if i == "b120" else "Normal") for i in ids], "block_id string, label string")
    k, table = kmeans_detector.select_k(df, [2, 3, 4], seed=1, labels_df=labels, k_default=4)
    assert all("val_pr_auc" in r for r in table)
    assert k in (2, 3, 4)


# ───────────── z-score ─────────────
def test_zscore_blocks_flags_error_heavy_block(spark):
    extra = [(5, 3, 0, 0, 0.0)] * 40 + [(5, 3, 1, 1, 0.0)] * 5 + [(50, 3, 20, 30, 0.0)]
    df = features_df(spark, [[1.0]] * 46, extra)
    out, info = zscore_detector.score_blocks(df, threshold=3.0)
    flagged = [r["block_id"] for r in out.where("is_anomaly = 1").collect()]
    assert flagged == ["b45"]
    assert info["std"] > 0


def test_detect_error_spikes(spark):
    base = datetime(2008, 11, 9, 20, 0, 0)
    rows = []
    for i in range(60):  # 60 cửa sổ 60s; component A lỗi nền 1 dòng/cửa sổ, đột biến 30 dòng ở cửa sổ 40
        n = 30 if i == 40 else 1
        rows.append((base + timedelta(minutes=i), "dfs.A", "ERROR", n))
        rows.append((base + timedelta(minutes=i), "dfs.A", "INFO", 100))
    df = spark.createDataFrame(rows, "ts timestamp, component string, level string, n long")
    out = zscore_detector.detect_error_spikes(df, window_seconds=60, threshold=3.0).collect()
    assert len(out) == 1 and out[0]["n"] == 30 and out[0]["ts"] == base + timedelta(minutes=40)


# ───────────── Isolation Forest ─────────────
def test_isolation_forest_scores_outlier_higher():
    rng = np.random.default_rng(0)
    counts = [rng.poisson([3, 2, 0]).astype(float) for _ in range(300)] + [np.array([0.0, 0.0, 40.0])]
    pdf = pd.DataFrame({
        "block_id": [f"b{i}" for i in range(301)],
        "counts": counts,
        "n_lines": [sum(c) for c in counts],
        "n_events": [int((c > 0).sum()) for c in counts],
        "n_warn": 0, "n_error": [0] * 300 + [40], "duration_s": 1.0,
    })
    out, info = iforest.fit_and_score(pdf, n_estimators=100, contamination=0.03, seed=1)
    assert out.sort_values("anomaly_score").iloc[-1]["block_id"] == "b300"
    assert out["is_anomaly"].sum() == pytest.approx(0.03 * 301, abs=2)
    assert info["threshold"] > 0


# ───────────── đánh giá ─────────────
def test_evaluate_matches_hand_computed_metrics(spark):
    pred = spark.createDataFrame(
        [("a", 0.9, 1), ("b", 0.8, 1), ("c", 0.7, 0), ("d", 0.6, 1), ("e", 0.2, 0), ("f", 0.1, 0)],
        "block_id string, anomaly_score double, is_anomaly int",
    )
    labels = spark.createDataFrame(
        [("a", "Anomaly"), ("b", "Normal"), ("c", "Anomaly"), ("d", "Anomaly"), ("e", "Normal"), ("f", "Normal")],
        "block_id string, label string",
    )
    m = evaluate(pred, labels)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 1, 1, 2)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)
    # average precision: xếp theo điểm giảm dần a(+) b(-) c(+) d(+) e f -> (1/1 + 2/3 + 3/4) / 3
    assert m["pr_auc"] == pytest.approx((1 + 2 / 3 + 3 / 4) / 3)
    assert m["label_coverage"] == 1.0 and m["n_positive"] == 3


def test_evaluate_reports_partial_label_coverage_and_rejects_no_overlap(spark):
    pred = spark.createDataFrame([("a", 0.9, 1), ("b", 0.1, 0)], "block_id string, anomaly_score double, is_anomaly int")
    some = spark.createDataFrame([("a", "Anomaly")], "block_id string, label string")
    assert evaluate(pred, some)["label_coverage"] == 0.5
    none = spark.createDataFrame([("zzz", "Anomaly")], "block_id string, label string")
    with pytest.raises(ValueError):
        evaluate(pred, none)


# ───────────── chia val/test ─────────────
def test_split_is_deterministic_disjoint_and_balanced(spark):
    ids = spark.createDataFrame([(f"blk_{i}",) for i in range(2000)], "block_id string")
    val = {r["block_id"] for r in take_split(ids, VAL).collect()}
    test = {r["block_id"] for r in take_split(ids, TEST).collect()}
    again = {r["block_id"] for r in take_split(ids, VAL).collect()}
    assert val == again
    assert not (val & test) and len(val) + len(test) == 2000
    assert 0.4 < len(val) / 2000 < 0.6
    assert set(r["split"] for r in with_split(ids).collect()) == {VAL, TEST}
