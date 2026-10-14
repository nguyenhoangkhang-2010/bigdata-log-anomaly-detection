"""Tạo SparkSession dùng chung cho mọi job."""
from __future__ import annotations

from typing import Any

from pyspark.sql import SparkSession


def get_spark(cfg: dict[str, Any], app_suffix: str = "", local: bool = False) -> SparkSession:
    sc = cfg["spark"]
    builder = (
        SparkSession.builder.appName(f"{sc['app_name']}{('-' + app_suffix) if app_suffix else ''}")
        .config("spark.sql.shuffle.partitions", sc["shuffle_partitions"])
        .config("spark.sql.session.timeZone", "UTC")
    )
    if local:
        builder = builder.master("local[*]")
    # khi submit qua spark-submit thì master do tham số --master quyết định
    return builder.getOrCreate()
