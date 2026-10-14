"""Trích đặc trưng từ log đã parse.

Hai tầng đặc trưng:
1. Theo phiên (session) = block_id  -> đầu vào cho mô hình phát hiện bất thường.
2. Theo cửa sổ thời gian            -> thống kê lỗi cho dashboard + phát hiện đột biến (z-score).
"""
from __future__ import annotations


def build_event_count_matrix(parsed_df, top_events: int | None = None):
    """Mỗi block -> vector đếm số lần xuất hiện từng event_id (bag-of-events).

    TODO (Tuần 6-7):
      - groupBy(block_id).pivot(event_id).count()  hoặc CountVectorizer trên mảng event_id
      - thêm: tổng số dòng, số event khác nhau, số WARN/ERROR, khoảng thời gian (max(ts)-min(ts))
      - chuẩn hóa theo cfg['features']['normalize'] (none | l2 | tfidf)
      - trả về DataFrame (block_id, features: Vector, ...scalar features)
    """
    raise NotImplementedError


def build_window_error_stats(parsed_df, window_seconds: int = 60):
    """Số dòng / WARN / ERROR theo cửa sổ thời gian và component.

    TODO: groupBy(window(ts, f'{window_seconds} seconds'), component, level).count()
    Kết quả ghi vào index Elasticsearch `logad-error-stats` để vẽ dashboard.
    """
    raise NotImplementedError
