"""Các tệp "phục vụ" (serving) mà backend đọc: nhỏ gọn, tính sẵn từ kết quả pipeline.

Thư mục `paths.serving` (mặc định `<results_root>/serving/`) do job 07 ghi:

    meta.json            tóm tắt lần chạy: tổng dòng/block, khoảng thời gian, ngưỡng + chỉ số từng mô hình, từ vựng event + idf
    blocks.parquet       1 dòng / block: thời gian, số dòng/WARN/ERROR, điểm + cờ của 3 mô hình, nhãn thật, top_events, counts
    events.parquet       1 dòng / template: số lần xuất hiện, số block, tỉ lệ nằm trong block bất thường, lift
    window_stats.parquet số dòng theo (cửa sổ 60 giây, component, level)          -> biểu đồ theo thời gian / theo component
    spikes.parquet       đột biến lỗi theo thời gian (z-score)                   -> cảnh báo
    lines/               dòng WARN/ERROR/FATAL + mọi dòng của block bị KMeans/IForest gắn cờ -> tìm kiếm log, dòng thời gian block

Thời gian luôn lưu dạng giây Unix (UTC, cột `*_epoch`) để không bị lệch múi giờ giữa Spark, pandas và trình duyệt.
"""
from __future__ import annotations

import numpy as np

MODELS = ("kmeans", "iforest", "zscore")
PRIMARY = "kmeans"
META_FILE = "meta.json"
BLOCKS_FILE = "blocks.parquet"
EVENTS_FILE = "events.parquet"
WINDOW_FILE = "window_stats.parquet"
SPIKES_FILE = "spikes.parquet"
LINES_DIR = "lines"

MIN_DEVIATION = 0.5  # lệch dưới mức này (so với block bình thường) thì không coi là lý do


def top_deviating_events(
    counts: np.ndarray, idf: np.ndarray, normal_mask: np.ndarray, vocab: list[str], top: int = 3,
) -> list[list[str]]:
    """Với mỗi block: các event lệch nhiều nhất so với block bình thường (độ lệch tuyệt đối × idf), tối đa `top` event."""
    mean = counts[normal_mask].mean(axis=0) if normal_mask.any() else counts.mean(axis=0)
    dev = counts - mean
    order = np.argsort(-(np.abs(dev) * idf), axis=1)[:, :top]
    rows = np.arange(counts.shape[0])[:, None]
    keep = np.abs(dev[rows, order]) >= MIN_DEVIATION
    return [[vocab[j] for j, k in zip(order[i], keep[i]) if k] for i in range(counts.shape[0])]


def event_stats(counts: np.ndarray, flagged: np.ndarray, vocab: list[str]) -> list[dict]:
    """Thống kê từng event: tổng số lần, số block chứa nó, tỉ lệ lần xuất hiện nằm trong block bị gắn cờ và lift so với nền."""
    counts = counts.astype(np.float64)  # float32 làm tỉ lệ/lift lẻ ở chữ số thập phân thứ 8
    total = counts.sum(axis=0)
    in_flagged = counts[flagged].sum(axis=0) if flagged.any() else np.zeros_like(total)
    base = in_flagged.sum() / total.sum() if total.sum() else 0.0
    rows = []
    for j, eid in enumerate(vocab):
        ratio = float(in_flagged[j] / total[j]) if total[j] else 0.0
        rows.append({
            "event_id": eid, "count": int(total[j]), "block_count": int((counts[:, j] > 0).sum()),
            "anomaly_ratio": round(ratio, 4), "lift": round(ratio / base, 2) if base else 0.0,
        })
    return rows
