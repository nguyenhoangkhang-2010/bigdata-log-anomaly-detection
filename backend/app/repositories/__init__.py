from __future__ import annotations

from ..config import Settings
from .base import Repository


def build_repository(settings: Settings) -> Repository:
    if settings.data_source == "demo":
        from .demo import DemoRepository

        return DemoRepository(seed=settings.demo_seed, n_blocks=settings.demo_blocks)
    if settings.data_source == "elasticsearch":
        from .elastic import ElasticsearchRepository

        return ElasticsearchRepository(settings.elasticsearch_url)
    raise ValueError(f"LOGAD_DATA_SOURCE không hợp lệ: {settings.data_source!r} (demo | elasticsearch)")
