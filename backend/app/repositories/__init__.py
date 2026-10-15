from __future__ import annotations

import logging
from pathlib import Path

from ..config import Settings
from .base import Repository

log = logging.getLogger("logad.repository")


def _try_elasticsearch(settings: Settings) -> Repository | None:
    """Có Elasticsearch đang chạy và đã nạp dữ liệu thì dùng; ngược lại trả về None (không báo lỗi để còn thử nguồn khác)."""
    try:
        from .elastic import ElasticsearchRepository

        return ElasticsearchRepository(settings.elasticsearch_url, settings.es_index_prefix)
    except Exception as e:  # noqa: BLE001 - mọi lỗi kết nối/thiếu dữ liệu đều có nghĩa là "chưa dùng được"
        log.info("Chưa dùng được Elasticsearch (%s: %s)", type(e).__name__, str(e)[:120])
        return None


def build_repository(settings: Settings) -> Repository:
    source = settings.data_source
    if source == "auto":  # ưu tiên: Elasticsearch có dữ liệu thật > tệp kết quả pipeline > dữ liệu mô phỏng
        repo = _try_elasticsearch(settings)
        if repo is not None:
            return repo
        source = "files" if (Path(settings.serving_dir) / "meta.json").exists() else "demo"
    if source == "demo":
        from .demo import DemoRepository

        return DemoRepository(seed=settings.demo_seed, n_blocks=settings.demo_blocks)
    if source == "files":
        from .files import FilesRepository

        return FilesRepository(settings.serving_dir)
    if source == "elasticsearch":
        from .elastic import ElasticsearchRepository

        return ElasticsearchRepository(settings.elasticsearch_url, settings.es_index_prefix)
    raise ValueError(f"LOGAD_DATA_SOURCE không hợp lệ: {settings.data_source!r} (auto | demo | files | elasticsearch)")
