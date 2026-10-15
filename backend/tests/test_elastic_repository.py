"""ElasticsearchRepository: cùng bộ kiểm tra với FilesRepository, chạy trên Elasticsearch THẬT.

Tự bỏ qua nếu không có Elasticsearch (đặt LOGAD_TEST_ES=http://host:9200 để đổi địa chỉ mặc định http://localhost:9200).
Dữ liệu thử nằm ở các index có prefix `logadtest` và được xóa sau khi chạy.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from serving_fixture import build_serving_dir
from test_contract import _validate, _validate_list

from app.config import Settings
from app.demo_data import DemoDataset
from app.main import create_app

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from logad.es_load import KINDS, index_name, load_serving  # noqa: E402

ES = os.environ.get("LOGAD_TEST_ES", "http://localhost:9200")
PREFIX = "logadtest"


def _es_up() -> bool:
    try:
        from elasticsearch import Elasticsearch

        return bool(Elasticsearch(ES, request_timeout=3).ping())
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _es_up(), reason=f"không có Elasticsearch ở {ES}")


@pytest.fixture(scope="module")
def dataset():
    return DemoDataset(seed=7, n_blocks=800)


@pytest.fixture(scope="module")
def eclient(tmp_path_factory, dataset):
    from elasticsearch import Elasticsearch

    d = build_serving_dir(tmp_path_factory.mktemp("serving_es"), dataset)
    res = load_serving(d, ES, PREFIX)
    assert all(r["errors"] == 0 for r in res.values()), res
    app = create_app(Settings(data_source="elasticsearch", elasticsearch_url=ES, es_index_prefix=PREFIX))
    with TestClient(app) as c:
        yield c
    es = Elasticsearch(ES)
    for k in KINDS:
        es.indices.delete(index=index_name(PREFIX, k), ignore_unavailable=True)


def test_responses_match_contract(eclient):
    _validate(eclient, "/api/v1/health", "Health")
    _validate(eclient, "/api/v1/meta", "Meta")
    _validate(eclient, "/api/v1/overview/summary", "Summary")
    _validate(eclient, "/api/v1/overview/timeline", "Timeline", bucket="15m")
    _validate_list(eclient, "/api/v1/overview/components", "ComponentStat")
    _validate_list(eclient, "/api/v1/alerts", "Alert")
    page = _validate(eclient, "/api/v1/anomalies", "AnomalyPage")
    _validate(eclient, f"/api/v1/anomalies/{page['items'][0]['block_id']}", "AnomalyDetail")
    _validate_list(eclient, "/api/v1/events", "EventTemplate")
    _validate_list(eclient, "/api/v1/models", "ModelEval")
    _validate(eclient, "/api/v1/models/kmeans/score-distribution", "ScoreDistribution")
    _validate(eclient, "/api/v1/logs", "LogPage", level="ERROR")


def test_meta_and_summary_match_dataset(eclient, dataset):
    assert eclient.get("/api/v1/health").json()["data_source"] == "elasticsearch"
    s = eclient.get("/api/v1/overview/summary").json()
    assert s["total_lines"] == len(dataset.lines) and s["total_blocks"] == len(dataset.block_ids)
    assert s["anomalous_blocks"] == int(dataset.flags["kmeans"].sum())
    assert eclient.get("/api/v1/meta").json()["pipeline_run"]["id"] == "run-test"


def test_timeline_sums_to_total_lines_and_counts_anomalies(eclient):
    s = eclient.get("/api/v1/overview/summary").json()
    for bucket in ("1m", "15m", "1h"):
        pts = eclient.get("/api/v1/overview/timeline", params={"bucket": bucket}).json()["points"]
        assert sum(p["info"] + p["warn"] + p["error"] + p["fatal"] for p in pts) == s["total_lines"]
        assert sum(p["anomalies"] for p in pts) == s["anomalous_blocks"]


def test_anomalies_sorted_filtered_paginated_and_deep_paging(eclient):
    p = eclient.get("/api/v1/anomalies", params={"page_size": 5}).json()
    scores = [i["anomaly_score"] for i in p["items"]]
    assert len(p["items"]) == 5 and scores == sorted(scores, reverse=True) and all(i["is_anomaly"] for i in p["items"])
    one = p["items"][0]["block_id"]
    q = eclient.get("/api/v1/anomalies", params={"q": one[-6:].upper(), "only_flagged": False}).json()
    assert q["total"] >= 1 and any(i["block_id"] == one for i in q["items"])
    assert eclient.get("/api/v1/anomalies", params={"model": "iforest"}).json()["items"][0]["cluster"] is None
    total = eclient.get("/api/v1/anomalies", params={"only_flagged": False}).json()["total"]
    last = eclient.get("/api/v1/anomalies", params={"only_flagged": False, "page": 8, "page_size": 100}).json()
    assert total == 800 and len(last["items"]) == 100
    hi = eclient.get("/api/v1/anomalies", params={"min_score": scores[0]}).json()
    assert hi["total"] >= 1 and all(i["anomaly_score"] >= scores[0] for i in hi["items"])


def test_detail_has_reasons_scores_label_and_block_timeline(eclient):
    bid = eclient.get("/api/v1/anomalies").json()["items"][0]["block_id"]
    d = eclient.get(f"/api/v1/anomalies/{bid}").json()
    assert d["label"] in ("Normal", "Anomaly") and {s["model"] for s in d["scores"]} == {"kmeans", "iforest", "zscore"}
    assert d["reasons"] and all(r["template"] for r in d["reasons"])
    assert d["timeline"] and all(ln["block_id"] == bid for ln in d["timeline"])
    assert eclient.get("/api/v1/anomalies/blk_nope").status_code == 404


def test_models_events_and_alerts(eclient):
    ms = eclient.get("/api/v1/models").json()
    assert [m["name"] for m in ms] == ["kmeans", "iforest", "zscore"] and ms[0]["params"]["evaluated_on"] == "test"
    lifts = [e["lift"] for e in eclient.get("/api/v1/events").json()]
    assert lifts == sorted(lifts, reverse=True) and len(lifts) > 3
    counts = [e["count"] for e in eclient.get("/api/v1/events", params={"sort": "count_desc"}).json()]
    assert counts == sorted(counts, reverse=True)
    kinds = {a["kind"] for a in eclient.get("/api/v1/alerts", params={"limit": 200}).json()}
    assert kinds == {"error_spike", "anomalous_block"}


def test_score_distribution_covers_all_blocks(eclient):
    for model in ("kmeans", "iforest", "zscore"):
        bins = eclient.get(f"/api/v1/models/{model}/score-distribution", params={"bins": 20}).json()["bins"]
        assert len(bins) == 20 and sum(b["normal"] + b["anomaly"] for b in bins) == 800


def test_components_and_logs_filters(eclient):
    comps = eclient.get("/api/v1/overview/components", params={"limit": 5}).json()
    assert 0 < len(comps) <= 5
    errs = eclient.get("/api/v1/logs", params={"level": "ERROR", "page_size": 200}).json()
    assert errs["total"] > 0 and all(i["level"] == "ERROR" for i in errs["items"])
    ts = [i["ts"] for i in errs["items"]]
    assert ts == sorted(ts, reverse=True)
    bid = eclient.get("/api/v1/anomalies").json()["items"][0]["block_id"]
    blk = eclient.get("/api/v1/logs", params={"block_id": bid, "page_size": 200}).json()
    assert blk["total"] > 0 and all(i["block_id"] == bid for i in blk["items"])
    word = errs["items"][0]["content"].split()[0]
    assert eclient.get("/api/v1/logs", params={"q": word.upper()}).json()["total"] > 0
    assert eclient.get("/api/v1/logs", params={"component": comps[0]["component"]}).json()["total"] > 0


def test_export_csv_and_auto_prefers_elasticsearch(eclient):
    r = eclient.get("/api/v1/anomalies/export", params={"limit": 10})
    assert r.status_code == 200 and r.text.splitlines()[0].startswith("block_id,model")
    from app.repositories import build_repository

    repo = build_repository(Settings(data_source="auto", elasticsearch_url=ES, es_index_prefix=PREFIX))
    assert repo.name == "elasticsearch"
