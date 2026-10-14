"""Job 04 - phát hiện bất thường: KMeans (chính, Spark MLlib) + Isolation Forest và z-score (baseline)."""
import time

from _common import run_standalone

from logad.config import resolve_paths
from logad.evaluation import read_labels
from logad.models import isolation_forest_baseline as iforest
from logad.models import kmeans_detector, zscore_detector
from logad.storage import arrays_to_vectors, load_json, load_parquet, save_json, save_parquet


def run(spark, cfg) -> dict:
    paths = resolve_paths(cfg)
    mc = cfg["models"]
    meta = load_json(spark, paths.features + "_meta.json")
    features = arrays_to_vectors(load_parquet(spark, paths.features), "counts", "features").cache()
    n = features.count()
    training: dict = {"n_blocks": n}

    # ---- KMeans (mô hình chính, phân tán) ----
    km = mc["kmeans"]
    t = time.perf_counter()
    labels = read_labels(spark, paths.labels) if (paths.labels and km.get("tune_k_on_labels", True)) else None
    k, k_table = kmeans_detector.select_k(
        features, km["k_candidates"], km["seed"], km.get("max_iter", 30), km.get("silhouette_sample", 100_000),
        labels_df=labels, positive=cfg["evaluation"]["label_positive"],
        threshold_percentile=km["threshold_percentile"], k_default=km.get("k_default", 4),
    )
    scored, info = kmeans_detector.fit_and_score(
        features, k, km["seed"], km["threshold_percentile"], km.get("max_iter", 30),
    )
    save_parquet(scored, paths.results("kmeans"))
    info["k_selection"] = k_table
    info["train_seconds"] = round(time.perf_counter() - t, 2)
    # "gói mô hình": đủ để chấm điểm dữ liệu mới (từ vựng event + idf + tâm cụm + ngưỡng), không cần Spark ML model
    save_json(spark, {**meta, **{x: info[x] for x in ("k", "centers", "threshold")}}, f"{paths.models_dir}/kmeans.json")
    training["kmeans"] = {x: info[x] for x in ("k", "threshold", "cluster_sizes", "train_seconds", "k_selection")}
    how = "PR-AUC trên nửa val" if labels is not None else "k_default (chưa có nhãn)"
    print(f"[04] KMeans: k = {k} (chọn theo {how})")
    for r in k_table:
        val = f"{r['val_pr_auc']:.3f}" if r.get("val_pr_auc") is not None else "  -  "
        sil = f"{r['silhouette']:.3f}" if r.get("silhouette") is not None else "  -  "
        print(f"       k={r['k']:<3} val PR-AUC {val}   silhouette {sil}")
    print(f"     cụm: {info['cluster_sizes']} · ngưỡng = {info['threshold']:.4f} · {info['train_seconds']}s")

    # ---- Isolation Forest (baseline đơn máy, scikit-learn) ----
    ic = mc["isolation_forest"]
    t = time.perf_counter()
    pdf = features.select("block_id", "counts", "n_lines", "n_events", "n_warn", "n_error", "duration_s").toPandas()
    pdf["counts"] = pdf["counts"].apply(lambda v: v.toArray())
    out, iinfo = iforest.fit_and_score(pdf, ic["n_estimators"], ic["contamination"], ic["seed"])
    save_parquet(spark.createDataFrame(out), paths.results("iforest"))
    iinfo["train_seconds"] = round(time.perf_counter() - t, 2)
    training["iforest"] = iinfo
    print(f"     Isolation Forest: {int(out['is_anomaly'].sum()):,} block bị gắn cờ · {iinfo['train_seconds']}s")

    # ---- z-score (baseline thống kê) ----
    t = time.perf_counter()
    zs, zinfo = zscore_detector.score_blocks(features, mc["zscore"]["threshold"])
    save_parquet(zs, paths.results("zscore"))
    zinfo["train_seconds"] = round(time.perf_counter() - t, 2)
    training["zscore"] = zinfo
    print(f"     z-score: ngưỡng z > {zinfo['threshold']}")

    # ---- đột biến lỗi theo thời gian (cho cảnh báo trên dashboard) ----
    spikes = zscore_detector.detect_error_spikes(
        load_parquet(spark, paths.window_stats), cfg["features"]["time_window_seconds"], mc["zscore"]["threshold"],
    )
    save_parquet(spikes, f"{paths.results_root}/spikes")
    print(f"     đột biến lỗi theo thời gian: {spikes.count():,} (cửa sổ, component)")

    save_json(spark, training, f"{paths.results_root}/training.json")
    return training


if __name__ == "__main__":
    run_standalone("04-detect", run)
