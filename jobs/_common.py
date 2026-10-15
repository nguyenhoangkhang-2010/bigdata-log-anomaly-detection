"""Phần dùng chung của các job: nạp cấu hình, tạo SparkSession, chạy một job như một chương trình độc lập."""
from __future__ import annotations

from collections.abc import Callable

from logad.config import Paths, load_config, resolve_paths
from logad.spark_utils import get_spark


def run_standalone(name: str, run: Callable) -> None:
    """Dùng cho `spark-submit jobs/0X_*.py`: tự tạo SparkSession, chạy, rồi đóng."""
    cfg = load_config()
    paths: Paths = resolve_paths(cfg)
    spark = get_spark(cfg, name, local=paths.is_local)
    try:
        run(spark, cfg)
    finally:
        spark.stop()
