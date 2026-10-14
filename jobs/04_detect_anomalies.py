"""Job 04 - chạy các bộ phát hiện bất thường: KMeans (chính), Isolation Forest + z-score (baseline)."""
from logad.config import hdfs_uri, load_config
from logad.models import kmeans_detector
from logad.spark_utils import get_spark


def main() -> None:
    cfg = load_config()
    spark = get_spark(cfg, "04-detect")
    features = spark.read.parquet(hdfs_uri(cfg, "features_path"))

    km = cfg["models"]["kmeans"]
    k = kmeans_detector.select_k(features, km["k_candidates"], km["seed"])
    scored = kmeans_detector.fit_and_score(features, k, km["seed"], km["threshold_percentile"])
    scored.write.mode("overwrite").parquet(hdfs_uri(cfg, "results_path") + "/kmeans")

    # TODO: Isolation Forest (pandas) -> results/iforest ; z-score spike -> results/zscore
    spark.stop()


if __name__ == "__main__":
    main()
