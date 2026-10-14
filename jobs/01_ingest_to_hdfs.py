"""Job 01 - kiểm tra dữ liệu thô đã sẵn sàng (HDFS hoặc thư mục local) và in quy mô để ghi vào báo cáo.

Việc copy file lên HDFS làm bằng lệnh `hdfs dfs -put` (scripts/hdfs_put.ps1); job này chỉ xác nhận file đọc được.
"""
from _common import run_standalone

from logad.config import resolve_paths


def run(spark, cfg) -> dict:
    paths = resolve_paths(cfg)
    raw = spark.read.text(paths.raw)
    n = raw.count()
    print(f"[01] đọc được {paths.raw}\n     {n:,} dòng log thô")
    if paths.labels:
        n_labels = spark.read.csv(paths.labels, header=True).count()
        print(f"     nhãn: {paths.labels} ({n_labels:,} block)")
    else:
        print("     (chưa có file nhãn: vẫn chạy được nhưng bước 05 sẽ bỏ qua phần đánh giá)")
    return {"raw_lines": n}


if __name__ == "__main__":
    run_standalone("01-ingest", run)
