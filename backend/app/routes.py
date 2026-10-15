"""Các route - operationId và tham số khớp api/openapi.yaml."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from .repositories.base import Repository
from .schemas import (
    Alert, AnomalyDetail, AnomalyPage, Bucket, ComponentStat, EventTemplate, Health, Level, LogPage, Meta,
    ModelEval, ModelName, ScoreDistribution, Severity, Summary, Timeline,
)

router = APIRouter(prefix="/api/v1")


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


Repo = Annotated[Repository, Depends(get_repo)]
AnomalySort = Literal["score_desc", "score_asc", "time_desc", "time_asc", "lines_desc"]


@router.get("/health", operation_id="getHealth", response_model=Health, tags=["system"])
def get_health(repo: Repo) -> Health:
    return Health(status="ok", data_source=repo.name)


@router.get("/meta", operation_id="getMeta", response_model=Meta, tags=["system"])
def get_meta(repo: Repo) -> Meta:
    return repo.meta()


@router.get("/overview/summary", operation_id="getSummary", response_model=Summary, tags=["overview"])
def get_summary(repo: Repo) -> Summary:
    return repo.summary()


@router.get("/overview/timeline", operation_id="getTimeline", response_model=Timeline, tags=["overview"])
def get_timeline(repo: Repo, bucket: Bucket = "1h") -> Timeline:
    return repo.timeline(bucket)


@router.get("/overview/components", operation_id="getComponents", response_model=list[ComponentStat], tags=["overview"])
def get_components(repo: Repo, limit: Annotated[int, Query(ge=1, le=50)] = 10) -> list[ComponentStat]:
    return repo.components(limit)


@router.get("/alerts", operation_id="listAlerts", response_model=list[Alert], tags=["overview"])
def list_alerts(
    repo: Repo,
    severity: Severity | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[Alert]:
    return repo.alerts(severity, limit)


@router.get("/anomalies", operation_id="listAnomalies", response_model=AnomalyPage, tags=["anomalies"])
def list_anomalies(
    repo: Repo,
    model: ModelName | None = None,
    only_flagged: bool = True,
    min_score: Annotated[float | None, Query(ge=0)] = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
    sort: AnomalySort = "score_desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AnomalyPage:
    return repo.anomalies(model, only_flagged, min_score, q, sort, page, page_size)


CSV_COLUMNS = [
    "block_id", "model", "anomaly_score", "is_anomaly", "cluster", "first_ts", "last_ts",
    "line_count", "warn_count", "error_count", "top_events",
]


# Phải khai báo TRƯỚC /anomalies/{block_id}, nếu không "export" bị hiểu là block_id.
@router.get(
    "/anomalies/export", operation_id="exportAnomalies", tags=["anomalies"], response_class=Response,
    responses={200: {"description": "Tệp CSV (UTF-8)", "content": {"text/csv": {"schema": {"type": "string"}}}}},
)
def export_anomalies(
    repo: Repo,
    model: ModelName | None = None,
    only_flagged: bool = True,
    min_score: Annotated[float | None, Query(ge=0)] = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
    sort: AnomalySort = "score_desc",
    limit: Annotated[int, Query(ge=1, le=10000)] = 1000,
) -> Response:
    page = repo.anomalies(model, only_flagged, min_score, q, sort, 1, limit)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(CSV_COLUMNS)
    for it in page.items:
        w.writerow([
            it.block_id, it.model, it.anomaly_score, int(it.is_anomaly),
            "" if it.cluster is None else it.cluster,
            it.first_ts.isoformat(), it.last_ts.isoformat(),
            it.line_count, it.warn_count, it.error_count, " ".join(it.top_events),
        ])
    name = f"anomalies-{page.items[0].model if page.items else (model or 'kmeans')}.csv"
    return Response(
        buf.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/anomalies/{block_id}", operation_id="getAnomaly", response_model=AnomalyDetail, tags=["anomalies"])
def get_anomaly(repo: Repo, block_id: str, model: ModelName | None = None) -> AnomalyDetail:
    detail = repo.anomaly_detail(block_id, model)
    if detail is None:
        raise HTTPException(404, f"Không tìm thấy block {block_id}")
    return detail


@router.get("/events", operation_id="listEvents", response_model=list[EventTemplate], tags=["events"])
def list_events(
    repo: Repo,
    sort: Literal["count_desc", "lift_desc"] = "lift_desc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[EventTemplate]:
    return repo.events(sort, limit)


@router.get("/models", operation_id="listModels", response_model=list[ModelEval], tags=["models"])
def list_models(repo: Repo) -> list[ModelEval]:
    return repo.models()


@router.get(
    "/models/{model}/score-distribution", operation_id="getScoreDistribution",
    response_model=ScoreDistribution, tags=["models"],
)
def get_score_distribution(
    repo: Repo, model: ModelName, bins: Annotated[int, Query(ge=5, le=100)] = 40,
) -> ScoreDistribution:
    dist = repo.score_distribution(model, bins)
    if dist is None:
        raise HTTPException(404, f"Chưa có điểm số cho mô hình {model}")
    return dist


@router.get("/logs", operation_id="searchLogs", response_model=LogPage, tags=["logs"])
def search_logs(
    repo: Repo,
    q: Annotated[str | None, Query(max_length=200)] = None,
    level: Level | None = None,
    component: str | None = None,
    block_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> LogPage:
    return repo.logs(q, level, component, block_id, start, end, page, page_size)
