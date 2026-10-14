"""Đọc configs/pipeline.yaml và quy đổi đường dẫn theo chế độ lưu trữ (hdfs | local)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path(os.environ.get("LOGAD_CONFIG", "configs/pipeline.yaml"))
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.is_absolute() and not p.exists():
        # chạy trong container: /opt/project/configs/pipeline.yaml
        alt = Path("/opt/project") / p
        if alt.exists():
            p = alt
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def hdfs_uri(cfg: dict[str, Any], key: str) -> str:
    """Ghép namenode + đường dẫn, ví dụ hdfs://namenode:9000/logad/parsed."""
    return cfg["hdfs"]["namenode"].rstrip("/") + cfg["hdfs"][key]


@dataclass(frozen=True)
class Paths:
    """Mọi đường dẫn vào/ra của pipeline, đã quy đổi theo chế độ lưu trữ."""

    is_local: bool
    raw: str
    labels: str | None
    parsed: str
    features: str
    window_stats: str
    results_root: str
    models_dir: str
    metrics: str

    def results(self, model: str) -> str:
        return f"{self.results_root}/{model}"


def _first_existing(*candidates: str | None) -> str | None:
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def resolve_paths(cfg: dict[str, Any]) -> Paths:
    """Chế độ `hdfs` (mặc định, chạy trong cụm Docker) hoặc `local` (đọc/ghi thư mục data/, không cần HDFS).

    Ghi đè bằng biến môi trường: LOGAD_STORAGE=local, LOGAD_RAW=<file log>, LOGAD_LABELS=<anomaly_label.csv>,
    LOGAD_LOCAL_ROOT=<thư mục kết quả>.
    """
    mode = os.environ.get("LOGAD_STORAGE", cfg.get("storage", {}).get("mode", "hdfs")).lower()

    if mode == "hdfs":
        return Paths(
            is_local=False,
            raw=hdfs_uri(cfg, "raw_path"),
            labels=hdfs_uri(cfg, "labels_path"),
            parsed=hdfs_uri(cfg, "parsed_path"),
            features=hdfs_uri(cfg, "features_path"),
            window_stats=hdfs_uri(cfg, "window_stats_path"),
            results_root=hdfs_uri(cfg, "results_path"),
            models_dir=str(Path(cfg.get("storage", {}).get("models_dir", "models"))),
            metrics=hdfs_uri(cfg, "results_path") + "/metrics.json",
        )

    root = Path(os.environ.get("LOGAD_LOCAL_ROOT") or cfg.get("storage", {}).get("local_root", "data/interim/logad"))
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    ds = cfg["dataset"]

    def abs_(p: str | None) -> str | None:
        if not p:
            return None
        pp = Path(p)
        return str(pp if pp.is_absolute() else PROJECT_ROOT / pp)

    raw = _first_existing(
        os.environ.get("LOGAD_RAW"), abs_(ds.get("local_raw")), abs_(ds.get("local_raw_fallback")),
    )
    if raw is None:
        raise FileNotFoundError(
            "Không tìm thấy file log thô. Tải dữ liệu bằng `python scripts/download_loghub.py [--sample]` "
            "hoặc đặt LOGAD_RAW=<đường dẫn HDFS.log>."
        )
    labels = _first_existing(os.environ.get("LOGAD_LABELS"), abs_(ds.get("local_labels")))
    return Paths(
        is_local=True,
        raw=raw,
        labels=labels,
        parsed=str(root / "parsed"),
        features=str(root / "features"),
        window_stats=str(root / "window_stats"),
        results_root=str(root / "results"),
        models_dir=str(root / "models"),
        metrics=str(root / "results" / "metrics.json"),
    )
