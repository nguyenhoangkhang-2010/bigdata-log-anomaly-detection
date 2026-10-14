"""Job 05 - đánh giá từng mô hình bằng nhãn LogHub, in bảng so sánh và ghi metrics.json."""
from _common import run_standalone

from logad.config import resolve_paths
from logad.evaluation import evaluate, read_labels
from logad.splits import TEST
from logad.storage import load_json, load_parquet, save_json

MODELS = ("kmeans", "iforest", "zscore")


def run(spark, cfg) -> dict:
    paths = resolve_paths(cfg)
    if not paths.labels:
        print("[05] Chưa có file nhãn (anomaly_label.csv) nên bỏ qua đánh giá.")
        print("     Nhãn nằm trong HDFS_v1.zip: preprocessed/anomaly_label.csv (đặt LOGAD_LABELS=<đường dẫn> nếu để chỗ khác).")
        return {}

    labels = read_labels(spark, paths.labels)
    positive = cfg["evaluation"]["label_positive"]
    try:
        training = load_json(spark, f"{paths.results_root}/training.json")
    except Exception:
        training = {}

    results: dict = {}
    full: dict = {}
    print("[05] Chỉ số trên nửa TEST (siêu tham số k chọn ở nửa val, chưa nhìn thấy nửa này)")
    print(f"     {'mô hình':<10} {'precision':>9} {'recall':>7} {'F1':>7} {'PR-AUC':>7}   tp/fp/fn/tn")
    for name in MODELS:
        pred = load_parquet(spark, paths.results(name))
        m = evaluate(pred, labels, positive, split=TEST)
        m["train_seconds"] = training.get(name, {}).get("train_seconds")
        results[name] = m
        full[name] = evaluate(pred, labels, positive)
        print(f"     {name:<10} {m['precision']:>9.3f} {m['recall']:>7.3f} {m['f1']:>7.3f} {m['pr_auc']:>7.3f}   "
              f"{m['tp']}/{m['fp']}/{m['fn']}/{m['tn']}")
    first = results[MODELS[0]]
    print(f"     test: {first['n_labeled']:,} block có nhãn · {first['n_positive']:,} bất thường ({first['positive_rate']:.2%})")
    save_json(spark, {"split": TEST, "models": results, "all_blocks": full, "training": training}, paths.metrics)
    print(f"     -> {paths.metrics}")
    return results


if __name__ == "__main__":
    run_standalone("05-evaluate", run)
