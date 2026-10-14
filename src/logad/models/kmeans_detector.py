"""Mô hình chính: KMeans (Spark MLlib), điểm bất thường = khoảng cách tới tâm cụm gần nhất.

Ý tưởng: phần lớn block bình thường tạo vài cụm lớn, chặt; block bất thường nằm xa mọi tâm cụm
hoặc rơi vào cụm rất nhỏ. Ngưỡng = percentile (cfg models.kmeans.threshold_percentile).
"""
from __future__ import annotations


def select_k(features_df, k_candidates: list[int], seed: int):
    """TODO: chạy KMeans với từng k, tính silhouette (ClusteringEvaluator) / elbow (WSSSE), trả về k tốt nhất."""
    raise NotImplementedError


def fit_and_score(features_df, k: int, seed: int, threshold_percentile: float):
    """TODO:
      1. KMeans(k, seed).fit(features_df)
      2. transform -> cluster; khoảng cách Euclid tới centroid của cụm đó = anomaly_score
      3. ngưỡng = approxQuantile('anomaly_score', [p/100]) ; is_anomaly = score > ngưỡng
      4. lưu model vào models/kmeans (PipelineModel.save)
    """
    raise NotImplementedError
