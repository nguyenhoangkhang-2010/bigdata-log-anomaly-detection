"""Job 06 - đẩy log đã parse, block bất thường và thống kê lỗi vào Elasticsearch cho Kibana."""
from logad.config import hdfs_uri, load_config
from logad.es_sink import write_df
from logad.spark_utils import get_spark


def main() -> None:
    cfg = load_config()
    es = cfg["elasticsearch"]
    spark = get_spark(cfg, "06-index")

    anomalies = spark.read.parquet(hdfs_uri(cfg, "results_path") + "/kmeans").where("is_anomaly = 1")
    write_df(anomalies, es["index_anomalies"], es["host"])

    stats = spark.read.parquet(hdfs_uri(cfg, "features_path") + "_window_stats")
    write_df(stats, es["index_error_stats"], es["host"])

    # TODO: mẫu log ERROR/WARN (không đẩy toàn bộ 11M dòng) -> es["index_logs"]
    spark.stop()


if __name__ == "__main__":
    main()
