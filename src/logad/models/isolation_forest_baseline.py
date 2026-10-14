"""Baseline: Isolation Forest (scikit-learn). Spark MLlib không có sẵn Isolation Forest nên
đọc đặc trưng cấp block (~575k dòng, vừa RAM) sang pandas để huấn luyện.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def build_matrix(pdf: pd.DataFrame) -> np.ndarray:
    """log1p(số lần mỗi event) + số dòng + số event khác nhau + số WARN/ERROR + thời lượng."""
    counts = np.log1p(np.vstack(pdf["counts"].to_numpy()).astype(float))
    extra = np.column_stack([
        pdf["n_lines"], pdf["n_events"], pdf["n_warn"] + pdf["n_error"], pdf["duration_s"].fillna(0),
    ]).astype(float)
    return np.hstack([counts, extra])


def fit_and_score(
    pdf: pd.DataFrame, n_estimators: int, contamination: float, seed: int,
) -> tuple[pd.DataFrame, dict]:
    """pdf: block_id, counts (mảng), n_lines, n_events, n_warn, n_error, duration_s (kết quả của features.py, đã chuyển sang pandas).

    anomaly_score = -score_samples (càng cao càng bất thường); ngưỡng = phân vị (1 - contamination) của điểm.
    Trả về (DataFrame[block_id, anomaly_score, is_anomaly], info).
    """
    x = build_matrix(pdf)
    model = IsolationForest(n_estimators=n_estimators, contamination=contamination, random_state=seed, n_jobs=-1).fit(x)
    score = -model.score_samples(x)
    threshold = float(np.quantile(score, 1.0 - contamination))
    out = pd.DataFrame({
        "block_id": pdf["block_id"].to_numpy(),
        "anomaly_score": score,
        "is_anomaly": (score > threshold).astype(int),
    })
    return out, {
        "n_estimators": int(n_estimators), "contamination": float(contamination), "seed": int(seed),
        "threshold": threshold, "n_features": int(x.shape[1]),
    }
