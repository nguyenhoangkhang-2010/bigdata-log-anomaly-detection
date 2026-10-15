"""Chia block thành hai nửa cố định: `val` (chọn siêu tham số) và `test` (báo cáo kết quả cuối).

Chia theo băm của block_id nên ổn định giữa các lần chạy và giống nhau ở mọi mô hình; không phụ thuộc thứ tự dữ liệu.
Các mô hình vẫn học KHÔNG giám sát trên toàn bộ block; nhãn chỉ được dùng để chọn k ở nửa `val`,
còn các chỉ số báo cáo luôn tính ở nửa `test` mà việc chọn k chưa từng nhìn thấy.
"""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

VAL, TEST = "val", "test"


def with_split(df: DataFrame, key: str = "block_id") -> DataFrame:
    """Thêm cột `split` ('val' hoặc 'test')."""
    return df.withColumn("split", F.when(F.abs(F.hash(key)) % 2 == 0, F.lit(VAL)).otherwise(F.lit(TEST)))


def take_split(df: DataFrame, name: str, key: str = "block_id") -> DataFrame:
    return with_split(df, key).where(F.col("split") == name).drop("split")
