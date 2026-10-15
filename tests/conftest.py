import os
import sys

import pytest


@pytest.fixture(scope="session")
def spark():
    """SparkSession local dùng chung cho các test Spark (khởi động ~10 giây, chỉ một lần). Bỏ qua nếu thiếu pyspark/Java."""
    pyspark = pytest.importorskip("pyspark")  # noqa: F841
    if os.name == "nt":
        os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
        os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    from pyspark.sql import SparkSession

    try:
        s = (
            SparkSession.builder.master("local[2]").appName("logad-tests")
            .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "2")
            .config("spark.sql.session.timeZone", "UTC").getOrCreate()
        )
    except Exception as e:  # thiếu Java, v.v.
        pytest.skip(f"không khởi động được Spark local: {e}")
    yield s
    s.stop()
