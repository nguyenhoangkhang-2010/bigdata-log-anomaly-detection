"""Đọc/ghi dữ liệu trung gian của pipeline.

- Cụm Docker / Linux: ghi parquet bằng Spark như bình thường (HDFS hoặc thư mục local).
- Windows chạy local: Spark KHÔNG ghi được file nếu thiếu `winutils.exe` (java.lang.RuntimeException ... HADOOP_HOME unset),
  nên ghi bằng pandas + pyarrow. Chỉ dùng cho dữ liệu thử/phát triển (toàn bộ DataFrame được kéo về driver);
  bản đầy đủ 11 triệu dòng nên chạy trong cụm Docker.
- Cột Vector (counts, features) luôn lưu dạng mảng số (array<double>) để pandas/sklearn/Elasticsearch đọc được;
  `arrays_to_vectors` đổi lại thành Vector khi cần cho Spark MLlib.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from pyspark.ml.functions import array_to_vector, vector_to_array
from pyspark.ml.linalg import VectorUDT
from pyspark.sql import DataFrame, SparkSession

_REMOTE = ("hdfs://", "s3://", "s3a://", "gs://", "abfs://")


def is_remote(path: str) -> bool:
    return path.startswith(_REMOTE)


def _needs_pandas_writer(path: str) -> bool:
    return os.name == "nt" and not is_remote(path)


def vectors_to_arrays(df: DataFrame) -> DataFrame:
    for f in df.schema.fields:
        if isinstance(f.dataType, VectorUDT):
            df = df.withColumn(f.name, vector_to_array(f.name))
    return df


def arrays_to_vectors(df: DataFrame, *cols: str) -> DataFrame:
    for c in cols:
        df = df.withColumn(c, array_to_vector(c))
    return df


def _write_parts_with_pyarrow(df: DataFrame, out: Path) -> None:
    """Mỗi partition tự ghi một file parquet bằng pyarrow ngay trong tiến trình worker (không kéo về driver).

    Dùng mapInArrow: schema Arrow lấy từ Spark nên mọi batch cùng kiểu, timestamp đã là micro-giây (Spark đọc lại được).
    """
    import uuid

    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyspark.sql.types import LongType, StructField, StructType

    target = str(out)

    def write_partition(batches):
        writer, rows = None, 0
        for batch in batches:
            if writer is None:
                writer = pq.ParquetWriter(os.path.join(target, f"part-{uuid.uuid4().hex}.parquet"), batch.schema)
            writer.write_batch(batch)
            rows += batch.num_rows
        if writer is not None:
            writer.close()
        yield pa.RecordBatch.from_pydict({"rows": [rows]}, schema=pa.schema([("rows", pa.int64())]))

    df.mapInArrow(write_partition, StructType([StructField("rows", LongType())])).collect()


def save_parquet(df: DataFrame, path: str) -> None:
    """Ghi DataFrame ra `path` (thư mục parquet). Ghi đè nếu đã có."""
    df = vectors_to_arrays(df)
    if _needs_pandas_writer(path):
        out = Path(path)
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        _write_parts_with_pyarrow(df, out)
    else:
        df.write.mode("overwrite").parquet(path)


def load_parquet(spark: SparkSession, path: str) -> DataFrame:
    if _needs_pandas_writer(path) and Path(path).is_dir():
        # Windows không có thư viện native của Hadoop: Spark không liệt kê được THƯ MỤC, nhưng đọc được từng FILE
        files = sorted(str(p) for p in Path(path).glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"Không có file .parquet nào trong {path}")
        return spark.read.parquet(*files)
    return spark.read.parquet(path)


def save_json(spark: SparkSession, obj: Any, path: str) -> None:
    """Ghi một đối tượng JSON nhỏ (metrics, meta đặc trưng, model). Đường dẫn remote ghi qua Spark."""
    text = json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default)
    if is_remote(path):
        spark.createDataFrame([(text,)], ["value"]).coalesce(1).write.mode("overwrite").text(path)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")


def load_json(spark: SparkSession, path: str) -> Any:
    if is_remote(path):
        return json.loads("\n".join(r["value"] for r in spark.read.text(path).collect()))
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_default(o: Any) -> Any:
    try:  # numpy / Decimal / datetime
        import numpy as np

        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)
