"""Job 03 - trích đặc trưng cấp block + thống kê lỗi theo cửa sổ thời gian."""
from logad.config import hdfs_uri, load_config
from logad.features import build_event_count_matrix, build_window_error_stats
from logad.spark_utils import get_spark


def main() -> None:
    cfg = load_config()
    spark = get_spark(cfg, "03-features")
    parsed = spark.read.parquet(hdfs_uri(cfg, "parsed_path"))

    features = build_event_count_matrix(parsed)
    features.write.mode("overwrite").parquet(hdfs_uri(cfg, "features_path"))

    stats = build_window_error_stats(parsed, cfg["features"]["time_window_seconds"])
    stats.write.mode("overwrite").parquet(hdfs_uri(cfg, "features_path") + "_window_stats")
    spark.stop()


if __name__ == "__main__":
    main()
