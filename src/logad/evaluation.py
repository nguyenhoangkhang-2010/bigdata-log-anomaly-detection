"""Đánh giá bộ phát hiện bất thường với nhãn LogHub (Normal/Anomaly theo block)."""
from __future__ import annotations


def evaluate(pred_df, labels_df, positive: str = "Anomaly") -> dict[str, float]:
    """TODO: join theo block_id; tính Precision, Recall, F1, PR-AUC (dữ liệu mất cân bằng ~3% anomaly),
    kèm ma trận nhầm lẫn TP/FP/FN/TN. Trả về dict để ghi docs/results.

    Lưu ý: nhãn CHỈ dùng để đánh giá, không dùng khi huấn luyện (unsupervised).
    """
    raise NotImplementedError
