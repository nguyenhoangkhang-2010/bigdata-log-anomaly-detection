"""Job 05 - đánh giá từng mô hình với nhãn LogHub, in bảng so sánh Precision/Recall/F1/PR-AUC."""
from logad.config import hdfs_uri, load_config
from logad.evaluation import evaluate
from logad.spark_utils import get_spark


def main() -> None:
    cfg = load_config()
    spark = get_spark(cfg, "05-evaluate")
    labels = spark.read.csv(hdfs_uri(cfg, "labels_path"), header=True).withColumnRenamed("BlockId", "block_id")

    for name in ("kmeans", "iforest"):
        pred = spark.read.parquet(hdfs_uri(cfg, "results_path") + f"/{name}")
        print(name, evaluate(pred, labels, cfg["evaluation"]["label_positive"]))
    # TODO: ghi kết quả ra docs/ hoặc data/processed/metrics.json để đưa vào báo cáo
    spark.stop()


if __name__ == "__main__":
    main()
