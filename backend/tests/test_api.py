def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok", "data_source": "demo"}


def test_meta_marks_demo_as_synthetic(client):
    m = client.get("/api/v1/meta").json()
    assert m["is_synthetic"] is True and m["data_source"] == "demo"
    assert m["primary_model"] in m["models"]


def test_summary_is_consistent(client):
    s = client.get("/api/v1/overview/summary").json()
    assert 0 < s["anomalous_blocks"] < s["total_blocks"]
    assert abs(s["anomaly_rate"] - s["anomalous_blocks"] / s["total_blocks"]) < 1e-9
    assert s["warn_lines"] + s["error_lines"] < s["total_lines"]


def test_timeline_sums_to_total_lines(client):
    total = client.get("/api/v1/overview/summary").json()["total_lines"]
    for bucket in ("1m", "15m", "1h"):
        pts = client.get("/api/v1/overview/timeline", params={"bucket": bucket}).json()["points"]
        assert sum(p["info"] + p["warn"] + p["error"] + p["fatal"] for p in pts) == total


def test_anomalies_sorted_and_paginated(client):
    p1 = client.get("/api/v1/anomalies", params={"page_size": 5}).json()
    assert len(p1["items"]) == 5 and p1["total"] >= 5
    scores = [i["anomaly_score"] for i in p1["items"]]
    assert scores == sorted(scores, reverse=True)
    assert all(i["is_anomaly"] for i in p1["items"])
    p2 = client.get("/api/v1/anomalies", params={"page_size": 5, "page": 2}).json()
    assert {i["block_id"] for i in p1["items"]}.isdisjoint({i["block_id"] for i in p2["items"]})


def test_anomalies_filter_by_query_and_model(client):
    top = client.get("/api/v1/anomalies", params={"page_size": 1}).json()["items"][0]
    hit = client.get("/api/v1/anomalies", params={"q": top["block_id"][-8:], "only_flagged": False}).json()
    assert any(i["block_id"] == top["block_id"] for i in hit["items"])
    z = client.get("/api/v1/anomalies", params={"model": "zscore"}).json()
    assert all(i["model"] == "zscore" and i["cluster"] is None for i in z["items"])


def test_anomaly_detail_has_timeline_and_reasons(client):
    top = client.get("/api/v1/anomalies", params={"page_size": 1}).json()["items"][0]
    d = client.get(f"/api/v1/anomalies/{top['block_id']}").json()
    assert d["item"]["block_id"] == top["block_id"]
    assert len(d["timeline"]) == top["line_count"]
    assert d["reasons"] and {s["model"] for s in d["scores"]} == {"kmeans", "iforest", "zscore"}
    ts = [ln["ts"] for ln in d["timeline"]]
    assert ts == sorted(ts)


def test_unknown_block_is_problem_404(client):
    r = client.get("/api/v1/anomalies/blk_nope")
    assert r.status_code == 404
    assert set(r.json()) >= {"status", "title"} and r.json()["status"] == 404


def test_validation_error_is_problem_422(client):
    r = client.get("/api/v1/anomalies", params={"page_size": 9999})
    assert r.status_code == 422 and r.json()["status"] == 422
    assert client.get("/api/v1/overview/timeline", params={"bucket": "2h"}).status_code == 422


def test_logs_filters(client):
    r = client.get("/api/v1/logs", params={"level": "ERROR", "page_size": 10}).json()
    assert r["total"] > 0 and all(i["level"] == "ERROR" for i in r["items"])
    ts = [i["ts"] for i in r["items"]]
    assert ts == sorted(ts, reverse=True)
    blk = r["items"][0]["block_id"]
    by_blk = client.get("/api/v1/logs", params={"block_id": blk, "page_size": 200}).json()
    assert by_blk["total"] > 0 and all(i["block_id"] == blk for i in by_blk["items"])


def test_models_metrics_are_consistent(client):
    for m in client.get("/api/v1/models").json():
        c = m["confusion"]
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        assert abs(m["precision"] - (tp / (tp + fp) if tp + fp else 0)) < 1e-9
        assert abs(m["recall"] - (tp / (tp + fn) if tp + fn else 0)) < 1e-9
        assert 0 <= m["pr_auc"] <= 1


def test_score_distribution_covers_all_blocks(client):
    total = client.get("/api/v1/overview/summary").json()["total_blocks"]
    d = client.get("/api/v1/models/iforest/score-distribution", params={"bins": 20}).json()
    assert len(d["bins"]) == 20
    assert sum(b["normal"] + b["anomaly"] for b in d["bins"]) == total


def test_events_lift_orders_anomalous_first(client):
    ev = client.get("/api/v1/events", params={"sort": "lift_desc"}).json()
    assert ev[0]["lift"] >= ev[-1]["lift"]
    assert ev[0]["anomaly_ratio"] > 0


def test_alerts_filter_by_severity(client):
    rows = client.get("/api/v1/alerts", params={"severity": "critical", "limit": 50}).json()
    assert all(a["severity"] == "critical" for a in rows)
