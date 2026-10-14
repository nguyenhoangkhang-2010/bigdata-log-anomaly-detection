"""Ghi kết quả vào Elasticsearch để Kibana vẽ dashboard.

Cách 1 (khuyến nghị): connector es-hadoop khi spark-submit
    --packages org.elasticsearch:elasticsearch-spark-30_2.12:8.15.3
    df.write.format("org.elasticsearch.spark.sql").option("es.nodes", "elasticsearch")...
Cách 2 (dự phòng): gom về driver rồi dùng elasticsearch.helpers.bulk (cho bảng nhỏ như anomalies, error-stats).
"""
from __future__ import annotations


def write_df(df, index: str, es_host: str, mode: str = "append") -> None:
    """TODO: viết bằng Cách 1; tạo index template (xem dashboard/kibana/index_templates) trước khi ghi."""
    raise NotImplementedError
