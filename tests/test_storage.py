import numpy as np
import pytest
from pyspark.errors import AnalysisException
from pyspark.ml.linalg import Vectors, VectorUDT
from pyspark.sql.types import StringType, StructField, StructType

from logad import storage


def test_parquet_roundtrip_with_vectors_and_timestamps(spark, tmp_path):
    from pyspark.sql import functions as F

    # thời gian tạo NGAY TRONG Spark (phiên đặt UTC), giống pipeline thật; không dùng datetime của Python vì nó bị hiểu theo
    # múi giờ của máy (UTC+7) nên cho kết quả lệch giờ khi so sánh
    df = spark.createDataFrame(
        [("b1", Vectors.dense([1.0, 2.0])), ("b2", Vectors.dense([0.0, 3.5]))],
        StructType([StructField("block_id", StringType()), StructField("features", VectorUDT())]),
    ).withColumn("ts", F.to_timestamp(F.lit("081109 200001"), "yyMMdd HHmmss"))
    path = str(tmp_path / "out")
    storage.save_parquet(df, path)
    back = storage.load_parquet(spark, path)
    rows = {r["block_id"]: r for r in back.collect()}
    assert rows["b1"]["features"] == [1.0, 2.0]  # vector được lưu dạng mảng số
    assert back.select(F.date_format("ts", "yyyy-MM-dd HH:mm:ss").alias("s")).first()["s"] == "2008-11-09 20:00:01"
    # đọc lại thành Vector để dùng cho Spark MLlib
    vec = storage.arrays_to_vectors(back, "features")
    assert isinstance(vec.schema["features"].dataType, VectorUDT)
    assert vec.where("block_id = 'b2'").first()["features"].toArray().tolist() == [0.0, 3.5]


def test_save_parquet_overwrites_existing_output(spark, tmp_path):
    path = str(tmp_path / "out")
    storage.save_parquet(spark.createDataFrame([(1,), (2,)], "x int"), path)
    storage.save_parquet(spark.createDataFrame([(9,)], "x int"), path)
    assert [r["x"] for r in storage.load_parquet(spark, path).collect()] == [9]


def test_json_roundtrip_handles_numpy_values(spark, tmp_path):
    path = str(tmp_path / "meta.json")
    storage.save_json(spark, {"k": np.int64(4), "centers": np.array([[1.0, 2.0]]), "name": "tiếng Việt"}, path)
    assert storage.load_json(spark, path) == {"k": 4, "centers": [[1.0, 2.0]], "name": "tiếng Việt"}


def test_missing_parquet_directory_is_a_clear_error(spark, tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises((FileNotFoundError, AnalysisException)):  # Windows / Linux
        storage.load_parquet(spark, str(tmp_path / "empty")).collect()
