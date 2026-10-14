"""Baseline thống kê: phát hiện đột biến số lỗi theo cửa sổ thời gian bằng z-score.

Dùng cho cảnh báo "thời điểm bất thường" trên dashboard (khác với bất thường cấp block).
"""
from __future__ import annotations


def detect_error_spikes(window_stats_df, threshold: float = 3.0):
    """TODO: với mỗi component tính mean/std số ERROR+WARN theo cửa sổ; z = (x-mean)/std;
    cảnh báo khi z > threshold. Có thể thay bằng rolling mean/std (Window.rowsBetween)."""
    raise NotImplementedError
