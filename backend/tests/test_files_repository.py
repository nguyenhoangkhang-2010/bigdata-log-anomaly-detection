"""FilesRepository (kết quả pipeline đã xuất) phải trả đúng hợp đồng API và số liệu nhất quán."""
import pytest
from fastapi.testclient import TestClient
from serving_fixture import build_serving_dir
from test_contract import _validate, _validate_list

from app.config import Settings
from app.demo_data import DemoDataset
from app.main import create_app
from app.repositories import build_repository
from app.repositories.files import FilesRepository


@pytest.fixture(scope="module")
def dataset():
    return DemoDataset(seed=7, n_blocks=800)


@pytest.fixture(scope="module")
def serving_dir(tmp_path_factory, dataset):
    return build_serving_dir(tmp_path_factory.mktemp("serving"), dataset)


@pytest.fixture(scope="module")
def fclient(serving_dir):
    app = create_app(Settings(data_source="files", serving_dir=str(serving_dir)))
    with TestClient(app) as c:
        yield c


def test_factory_builds_files_repository(serving_dir):
    repo = build_repository(Settings(data_source="files", serving_dir=str(serving_dir)))
    assert isinstance(repo, FilesRepository) and repo.name == "files"


def test_missing_directory_gives_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="run_local_pipeline"):
        FilesRepository(tmp_path)


def test_responses_match_contract(fclient):
    _validate(fclient, "/api/v1/health", "Health")
    _validate(fclient, "/api/v1/meta", "Meta")
    _validate(fclient, "/api/v1/overview/summary", "Summary")
    _validate(fclient, "/api/v1/overview/timeline", "Timeline", bucket="15m")
    _validate_list(fclient, "/api/v1/overview/components", "ComponentStat")
    _validate_list(fclient, "/api/v1/alerts", "Alert")
    page = _validate(fclient, "/api/v1/anomalies", "AnomalyPage")
    _validate(fclient, f"/api/v1/anomalies/{page['items'][0]['block_id']}", "AnomalyDetail")
    _validate_list(fclient, "/api/v1/events", "EventTemplate")
    _validate_list(fclient, "/api/v1/models", "ModelEval")
    _validate(fclient, "/api/v1/models/kmeans/score-distribution", "ScoreDistribution")
    _validate(fclient, "/api/v1/logs", "LogPage", level="ERROR")


def test_meta_reports_files_source(fclient):
    m = fclient.get("/api/v1/meta").json()
    assert m["data_source"] == "files" and m["pipeline_run"]["id"] == "run-test"
    assert m["time_range"]["start"] < m["time_range"]["end"]


def test_timeline_sums_to_total_lines_and_counts_anomalies(fclient, dataset):
    s = fclient.get("/api/v1/overview/summary").json()
    assert s["total_lines"] == len(dataset.lines)
    for bucket in ("1m", "15m", "1h"):
        pts = fclient.get("/api/v1/overview/timeline", params={"bucket": bucket}).json()["points"]
        assert sum(p["info"] + p["warn"] + p["error"] + p["fatal"] for p in pts) == s["total_lines"]
        assert sum(p["anomalies"] for p in pts) == s["anomalous_blocks"]


def test_anomalies_sorted_filtered_and_paginated(fclient):
    p = fclient.get("/api/v1/anomalies", params={"page_size": 5}).json()
    scores = [i["anomaly_score"] for i in p["items"]]
    assert len(p["items"]) == 5 and scores == sorted(scores, reverse=True) and all(i["is_anomaly"] for i in p["items"])
    one = p["items"][0]["block_id"]
    q = fclient.get("/api/v1/anomalies", params={"q": one[-6:], "only_flagged": False}).json()
    assert q["total"] >= 1 and any(i["block_id"] == one for i in q["items"])
    assert fclient.get("/api/v1/anomalies", params={"model": "iforest"}).json()["items"][0]["cluster"] is None


def test_detail_has_reasons_scores_label_and_block_timeline(fclient):
    bid = fclient.get("/api/v1/anomalies").json()["items"][0]["block_id"]
    d = fclient.get(f"/api/v1/anomalies/{bid}").json()
    assert d["label"] in ("Normal", "Anomaly") and {s["model"] for s in d["scores"]} == {"kmeans", "iforest", "zscore"}
    assert d["reasons"] and all(r["template"] for r in d["reasons"])
    assert d["timeline"] and all(ln["block_id"] == bid for ln in d["timeline"])
    assert fclient.get("/api/v1/anomalies/blk_nope").status_code == 404


def test_models_carry_evaluation_split_and_confusion_adds_up(fclient):
    ms = fclient.get("/api/v1/models").json()
    assert [m["name"] for m in ms] == ["kmeans", "iforest", "zscore"]
    for m in ms:
        c = m["confusion"]
        assert m["params"]["evaluated_on"] == "test" and c["tp"] + c["fp"] + c["fn"] + c["tn"] > 0


def test_score_distribution_covers_all_blocks(fclient):
    n = fclient.get("/api/v1/overview/summary").json()["total_blocks"]
    bins = fclient.get("/api/v1/models/kmeans/score-distribution", params={"bins": 20}).json()["bins"]
    assert len(bins) == 20 and sum(b["normal"] + b["anomaly"] for b in bins) == n


def test_logs_filter_by_level_block_and_text(fclient):
    errs = fclient.get("/api/v1/logs", params={"level": "ERROR", "page_size": 200}).json()
    assert errs["total"] > 0 and all(i["level"] == "ERROR" for i in errs["items"])
    ts = [i["ts"] for i in errs["items"]]
    assert ts == sorted(ts, reverse=True)
    bid = fclient.get("/api/v1/anomalies").json()["items"][0]["block_id"]
    blk = fclient.get("/api/v1/logs", params={"block_id": bid, "page_size": 200}).json()
    assert blk["total"] > 0 and all(i["block_id"] == bid for i in blk["items"])
    word = errs["items"][0]["content"].split()[0]
    assert fclient.get("/api/v1/logs", params={"q": word.upper()}).json()["total"] > 0


def test_alerts_have_both_kinds_and_events_sorting(fclient):
    kinds = {a["kind"] for a in fclient.get("/api/v1/alerts", params={"limit": 200}).json()}
    assert kinds == {"error_spike", "anomalous_block"}
    lifts = [e["lift"] for e in fclient.get("/api/v1/events").json()]
    assert lifts == sorted(lifts, reverse=True)
    counts = [e["count"] for e in fclient.get("/api/v1/events", params={"sort": "count_desc"}).json()]
    assert counts == sorted(counts, reverse=True)


def test_export_csv_works_on_files_source(fclient):
    r = fclient.get("/api/v1/anomalies/export", params={"limit": 10})
    assert r.status_code == 200 and r.text.splitlines()[0].startswith("block_id,model")


def test_auto_uses_files_when_results_exist_else_demo(serving_dir, tmp_path):
    from app.repositories.demo import DemoRepository

    no_es = "http://127.0.0.1:1"  # không có Elasticsearch ở đây, để kiểm tra riêng nhánh tệp/demo của chế độ auto
    files = build_repository(Settings(data_source="auto", elasticsearch_url=no_es, serving_dir=str(serving_dir)))
    demo = build_repository(
        Settings(data_source="auto", elasticsearch_url=no_es, serving_dir=str(tmp_path / "none"), demo_blocks=300),
    )
    assert isinstance(files, FilesRepository) and isinstance(demo, DemoRepository)
