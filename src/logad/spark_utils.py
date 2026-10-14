"""Tạo SparkSession dùng chung cho mọi job."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pyspark.sql import SparkSession


def get_spark(cfg: dict[str, Any], app_suffix: str = "", local: bool = False) -> SparkSession:
    sc = cfg["spark"]
    if local and os.name == "nt":
        # Windows: Spark gọi `python` để chạy worker, nhưng lệnh đó thường trỏ vào lối tắt Microsoft Store
        # ("Python was not found") -> lỗi "Python worker failed to connect back". Trỏ về Python đang chạy.
        os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
        os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    builder = (
        SparkSession.builder.appName(f"{sc['app_name']}{('-' + app_suffix) if app_suffix else ''}")
        .config("spark.sql.shuffle.partitions", sc["shuffle_partitions"])
        .config("spark.sql.session.timeZone", "UTC")
    )
    if local:
        # local[4] thay vì local[*]: máy nhiều lõi sinh hàng chục task nhỏ cho dữ liệu nhỏ và hay gặp lỗi tệp tạm shuffle trên Windows.
        # spark.local.dir đặt trong dự án (đường ngắn, không bị trình dọn dẹp Temp của Windows xóa giữa chừng).
        tmp = Path(__file__).resolve().parents[2] / "data" / "interim" / "spark-tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        builder = (
            builder.master(f"local[{sc.get('local_cores', 4)}]")
            .config("spark.ui.enabled", "false")
            .config("spark.local.dir", str(tmp))
            .config("spark.sql.shuffle.partitions", sc.get("local_shuffle_partitions", 4))
        )
    # khi submit qua spark-submit thì master do tham số --master quyết định
    return builder.getOrCreate()
