"""Baseline: Isolation Forest (scikit-learn). Spark MLlib không có sẵn Isolation Forest nên
đọc đặc trưng cấp block (~575k dòng, vừa RAM) sang pandas để huấn luyện.
"""
from __future__ import annotations


def fit_and_score(features_pdf, n_estimators: int, contamination: float, seed: int):
    """TODO: IsolationForest(...).fit(X); anomaly_score = -score_samples(X); is_anomaly = predict == -1.

    features_pdf: pandas DataFrame (block_id + các cột đặc trưng dạng số / vector đã tách cột).
    """
    raise NotImplementedError
