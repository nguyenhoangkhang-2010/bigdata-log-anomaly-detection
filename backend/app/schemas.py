"""Pydantic models - phải khớp api/openapi.yaml (test_contract.py kiểm tra tự động)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

Level = Literal["INFO", "WARN", "ERROR", "FATAL"]
Severity = Literal["critical", "warning", "info"]
ModelName = Literal["kmeans", "iforest", "zscore"]
Bucket = Literal["1m", "5m", "15m", "1h"]
DataSource = Literal["demo", "elasticsearch"]


class Problem(BaseModel):
    status: int
    title: str
    detail: str | None = None


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    data_source: DataSource


class TimeRange(BaseModel):
    start: datetime
    end: datetime


class MetaDataset(BaseModel):
    name: str
    description: str


class MetaRun(BaseModel):
    id: str
    finished_at: datetime


class Meta(BaseModel):
    dataset: MetaDataset
    data_source: DataSource
    is_synthetic: bool = False
    time_range: TimeRange
    models: list[ModelName]
    primary_model: ModelName
    pipeline_run: MetaRun
    version: str


class Summary(BaseModel):
    total_lines: int
    total_blocks: int
    anomalous_blocks: int
    anomaly_rate: float
    warn_lines: int
    error_lines: int
    error_rate: float
    active_alerts: int


class TimelinePoint(BaseModel):
    ts: datetime
    info: int
    warn: int
    error: int
    fatal: int
    anomalies: int


class Timeline(BaseModel):
    bucket: Bucket
    points: list[TimelinePoint]


class ComponentStat(BaseModel):
    component: str
    total: int
    warn: int
    error: int
    fatal: int


class Alert(BaseModel):
    id: str
    kind: Literal["error_spike", "anomalous_block"]
    severity: Severity
    ts: datetime
    title: str
    detail: str
    component: str | None = None
    block_id: str | None = None
    score: float | None = None


class AnomalyItem(BaseModel):
    block_id: str
    model: ModelName
    anomaly_score: float
    is_anomaly: bool
    cluster: int | None = None
    first_ts: datetime
    last_ts: datetime
    line_count: int
    warn_count: int
    error_count: int
    top_events: list[str]


class AnomalyPage(BaseModel):
    items: list[AnomalyItem]
    total: int
    page: int
    page_size: int


class LogLine(BaseModel):
    ts: datetime
    level: Level
    component: str
    block_id: str | None = None
    content: str
    template: str
    event_id: str


class LogPage(BaseModel):
    items: list[LogLine]
    total: int
    page: int
    page_size: int


class ModelScore(BaseModel):
    model: ModelName
    score: float
    is_anomaly: bool


class Reason(BaseModel):
    event_id: str
    template: str
    observed: int
    expected: float
    note: str


class AnomalyDetail(BaseModel):
    item: AnomalyItem
    threshold: float
    label: Literal["Normal", "Anomaly"] | None = None
    scores: list[ModelScore]
    reasons: list[Reason]
    timeline: list[LogLine]


class EventTemplate(BaseModel):
    event_id: str
    template: str
    level: Level
    count: int
    block_count: int
    anomaly_ratio: float
    lift: float


class Confusion(BaseModel):
    tp: int
    fp: int
    fn: int
    tn: int


class ModelEval(BaseModel):
    name: ModelName
    label: str
    kind: Literal["distributed", "single-node", "statistical"]
    precision: float
    recall: float
    f1: float
    pr_auc: float
    threshold: float
    confusion: Confusion
    train_seconds: float
    params: dict[str, Any]


class ScoreBin(BaseModel):
    lower: float
    upper: float
    normal: int
    anomaly: int


class ScoreDistribution(BaseModel):
    model: ModelName
    threshold: float
    bins: list[ScoreBin]
