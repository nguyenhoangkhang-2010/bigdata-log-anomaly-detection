"""Đọc configs/pipeline.yaml."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path(os.environ.get("LOGAD_CONFIG", "configs/pipeline.yaml"))


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
