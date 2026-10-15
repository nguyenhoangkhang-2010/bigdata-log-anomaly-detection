"""Phần dùng chung của các repository đọc KẾT QUẢ THẬT (files, elasticsearch): cách dựng meta, lý do bất thường, cảnh báo,
đánh giá mô hình từ `meta` do job 07 xuất. Hai repository chỉ khác nhau ở chỗ lấy dữ liệu ra (tệp hay truy vấn)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np

from ..schemas import (
    Alert, Confusion, Meta, MetaDataset, MetaRun, ModelEval, ModelName, Reason, TimeRange,
)

PRIMARY: ModelName = "kmeans"
MODEL_ORDER: tuple[ModelName, ...] = ("kmeans", "iforest", "zscore")
BUCKET_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
LEVELS = ("INFO", "WARN", "ERROR", "FATAL")
MODEL_INFO = {
    "kmeans": ("KMeans (Spark MLlib)", "distributed"),
    "iforest": ("Isolation Forest (scikit-learn)", "single-node"),
    "zscore": ("Z-score số lỗi", "statistical"),
}
MIN_DEVIATION = 0.5
MAX_SPIKE_ALERTS = 300  # chỉ giữ các đột biến mạnh nhất làm cảnh báo, tránh hàng nghìn cảnh báo
MAX_BLOCK_ALERTS = 12


def dt(epoch: float) -> datetime:
    return datetime.fromtimestamp(float(epoch), tz=UTC)


def aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def vi(x: float, d: int = 2) -> str:
    """Số thập phân theo kiểu Việt (dấu phẩy) cho các câu mô tả cảnh báo, khớp cách giao diện hiển thị."""
    return f"{x:.{d}f}".replace(".", ",")


def level_of(v: str) -> str:
    return v if v in LEVELS else "INFO"


def build_meta(m: dict[str, Any], data_source: str) -> Meta:
    ds, tot, tr = m["dataset"], m["totals"], m["time_range"]
    sample, raw = ds.get("sample_lines"), ds["raw"]
    name = "Nhật ký HDFS (mô phỏng)" if ds["is_synthetic"] else (
        "LogHub HDFS (mẫu 2.000 dòng)" if "2k" in raw else "LogHub HDFS_v1"
    )
    desc = f"{tot['lines']:,} dòng · {tot['blocks']:,} block · tệp {raw}"
    if sample:
        desc += f" · CHỈ {int(sample):,} dòng đầu (chạy thử)"
    if ds["is_synthetic"]:
        desc += " · dữ liệu mô phỏng, không dùng số liệu cho báo cáo"
    return Meta(
        dataset=MetaDataset(name=name, description=desc),
        data_source=data_source, is_synthetic=bool(ds["is_synthetic"]),  # type: ignore[arg-type]
        time_range=TimeRange(start=dt(tr["start_epoch"]), end=dt(tr["end_epoch"])),
        models=list(MODEL_ORDER), primary_model=PRIMARY,
        pipeline_run=MetaRun(id=m["run_id"], finished_at=dt(m["finished_at_epoch"])),
        version=m["version"],
    )


def threshold_of(m: dict[str, Any], model: str) -> float:
    return float(m["training"][model]["threshold"])


def _params(m: dict[str, Any], model: str) -> dict:
    p, t = m["params"], m["training"]
    if model == "kmeans":
        return {"k": t["kmeans"]["k"], "threshold_percentile": p["kmeans"]["threshold_percentile"], "seed": p["kmeans"]["seed"]}
    if model == "iforest":
        return {k: p["isolation_forest"][k] for k in ("n_estimators", "contamination", "seed")}
    return {"threshold": p["zscore"]["threshold"]}


def build_model_evals(m: dict[str, Any]) -> list[ModelEval]:
    ev = m.get("evaluation")
    if not ev:
        return []
    out = []
    for name in MODEL_ORDER:
        r = ev["models"].get(name)
        if not r:
            continue
        label, kind = MODEL_INFO[name]
        out.append(ModelEval(
            name=name, label=label, kind=kind, precision=r["precision"], recall=r["recall"], f1=r["f1"],
            pr_auc=r["pr_auc"], threshold=round(threshold_of(m, name), 4),
            confusion=Confusion(tp=r["tp"], fp=r["fp"], fn=r["fn"], tn=r["tn"]),
            train_seconds=float(m["training"][name].get("train_seconds", 0.0)),
            params={**_params(m, name), "evaluated_on": ev.get("split", "all")},
        ))
    return out


def build_reasons(
    counts: np.ndarray, normal_mean: np.ndarray, idf: np.ndarray, vocab: list[str], template: dict[str, str], top: int = 5,
) -> list[Reason]:
    """Các event lệch nhiều nhất (độ lệch tuyệt đối × idf) của một block so với block bình thường."""
    dev = counts - normal_mean
    reasons = []
    for j in np.argsort(-(np.abs(dev) * idf))[:top]:
        if abs(dev[j]) < MIN_DEVIATION:
            break
        obs, exp = int(counts[j]), float(normal_mean[j])
        if obs == 0:
            note = f"Không xuất hiện, block bình thường có ~{exp:.1f} lần (thiếu bước)"
        elif exp < 0.05:
            note = "Hiếm gặp ở block bình thường"
        elif dev[j] > 0:
            note = f"Nhiều hơn bình thường (~{exp:.1f} lần)"
        else:
            note = f"Ít hơn bình thường (~{exp:.1f} lần)"
        eid = vocab[j]
        reasons.append(Reason(event_id=eid, template=template.get(eid, ""), observed=obs, expected=round(exp, 2), note=note))
    return reasons


def spike_alert(component: str, ts_epoch: float, n: float, mean: float, z: float, window_seconds: int) -> Alert:
    return Alert(
        id=f"spike-{component}-{int(ts_epoch)}", kind="error_spike", severity="critical" if z >= 8 else "warning",
        ts=dt(ts_epoch), title=f"Đột biến lỗi ở {component}",
        detail=f"{int(n)} dòng WARN/ERROR trong {window_seconds} giây (trung bình {vi(mean)}, z = {vi(z, 1)})",
        component=component, score=round(z, 2),
    )


def block_alert(block_id: str, score: float, threshold: float, first_epoch: float, n_lines: int, n_error: int) -> Alert:
    return Alert(
        id=f"block-{block_id}", kind="anomalous_block", severity="critical" if score >= 1.6 * threshold else "warning",
        ts=dt(first_epoch), title=f"Block bất thường {block_id}",
        detail=f"Điểm {vi(score)} (ngưỡng {vi(threshold)}) · {n_lines} dòng · {n_error} lỗi",
        block_id=block_id, score=round(score, 3),
    )
