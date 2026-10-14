"""Repository đọc từ Elasticsearch - dữ liệu thật do pipeline Spark (jobs/06) ghi vào.

CHƯA CÀI ĐẶT: hoàn thiện sau khi `04_detect_anomalies` và `06_index_elasticsearch` chạy được.
Bản đồ chuyển đổi (index -> endpoint):

    logad-error-stats  -> /overview/timeline, /overview/components, cảnh báo đột biến (/alerts)
    logad-anomalies    -> /anomalies, /anomalies/{block_id}, cảnh báo block, /models/{m}/score-distribution
    logad-logs         -> /logs, timeline trong chi tiết block
    logad-models       -> /models   (job 05 cần ghi thêm index/metrics.json này)

Mỗi phương thức phải trả đúng các schema trong app/schemas.py - test_contract.py và test_api.py
chạy chung bộ kiểm thử cho cả hai repository, nên chỉ cần thay DemoRepository bằng lớp này.
"""
from __future__ import annotations


class ElasticsearchRepository:
    name = "elasticsearch"

    def __init__(self, url: str) -> None:
        raise NotImplementedError(
            "ElasticsearchRepository chưa được cài đặt. Dùng LOGAD_DATA_SOURCE=demo cho tới khi pipeline chạy xong."
        )
