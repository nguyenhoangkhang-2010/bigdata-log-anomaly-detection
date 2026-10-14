"""Job 01 - đưa dữ liệu thô lên HDFS.

Thực tế dùng lệnh HDFS CLI (xem scripts/hdfs_put.sh | .ps1) vì file chỉ cần copy. Job này chỉ
kiểm tra file đã có trên HDFS và in số dòng / dung lượng để ghi vào báo cáo (mô tả dữ liệu lớn: Volume).
"""
from logad.config import hdfs_uri, load_config
from logad.spark_utils import get_spark


def main() -> None:
    cfg = load_config()
    spark = get_spark(cfg, "01-ingest")
    raw = spark.read.text(hdfs_uri(cfg, "raw_path"))
    print(f"[01] số dòng log thô: {raw.count():,}")
    spark.stop()


if __name__ == "__main__":
    main()
