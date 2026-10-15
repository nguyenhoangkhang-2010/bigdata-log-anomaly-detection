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


# ───────────── xuất CSV ─────────────
def _csv_rows(text: str) -> list[list[str]]:
    import csv
    import io

    return list(csv.reader(io.StringIO(text)))


def test_export_is_csv_attachment_with_header(client):
    r = client.get("/api/v1/anomalies/export", params={"limit": 5})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="anomalies-kmeans.csv"' in r.headers["content-disposition"]
    rows = _csv_rows(r.text)
    assert rows[0][:3] == ["block_id", "model", "anomaly_score"] and len(rows) == 6  # tiêu đề + 5 dòng


def test_export_not_shadowed_by_block_route(client):
    # "export" không được bị hiểu là block_id (sẽ ra 404 nếu route động đứng trước)
    assert client.get("/api/v1/anomalies/export").status_code == 200


def test_export_matches_list_order_and_filters(client):
    lst = client.get("/api/v1/anomalies", params={"model": "iforest", "page_size": 10, "sort": "time_asc"}).json()["items"]
    rows = _csv_rows(client.get("/api/v1/anomalies/export", params={"model": "iforest", "limit": 10, "sort": "time_asc"}).text)[1:]
    assert [x[0] for x in rows] == [i["block_id"] for i in lst]
    assert all(x[1] == "iforest" and x[4] == "" for x in rows)  # iforest không có cụm


def test_export_rejects_bad_limit_and_empty_result_still_has_header(client):
    assert client.get("/api/v1/anomalies/export", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/anomalies/export", params={"limit": 10001}).status_code == 422
    r = client.get("/api/v1/anomalies/export", params={"q": "khong-co-block-nao-nhu-vay"})
    assert len(_csv_rows(r.text)) == 1


# ───────────── nhánh còn lại của API ─────────────
def test_anomalies_min_score_and_sort_orders(client):
    top = client.get("/api/v1/anomalies", params={"page_size": 1}).json()["items"][0]["anomaly_score"]
    hi = client.get("/api/v1/anomalies", params={"min_score": top, "only_flagged": False}).json()
    assert hi["total"] >= 1 and all(i["anomaly_score"] >= top for i in hi["items"])
    asc = client.get("/api/v1/anomalies", params={"sort": "time_asc", "page_size": 30}).json()["items"]
    assert [i["first_ts"] for i in asc] == sorted(i["first_ts"] for i in asc)
    big = client.get("/api/v1/anomalies", params={"sort": "lines_desc", "page_size": 30}).json()["items"]
    assert [i["line_count"] for i in big] == sorted((i["line_count"] for i in big), reverse=True)


def test_anomalies_page_beyond_last_is_empty_but_keeps_total(client):
    first = client.get("/api/v1/anomalies", params={"page_size": 10}).json()
    far = client.get("/api/v1/anomalies", params={"page_size": 10, "page": 9999}).json()
    assert far["items"] == [] and far["total"] == first["total"] and far["page"] == 9999


def test_logs_time_range_and_text_filter(client):
    pts = client.get("/api/v1/logs", params={"page_size": 200}).json()["items"]
    ts = sorted(p["ts"] for p in pts)
    lo, hi = ts[len(ts) // 3], ts[2 * len(ts) // 3]
    r = client.get("/api/v1/logs", params={"start": lo, "end": hi, "page_size": 200}).json()
    assert r["total"] > 0 and all(lo <= i["ts"] <= hi for i in r["items"])
    up = client.get("/api/v1/logs", params={"q": "RECEIVING BLOCK"}).json()
    assert up["total"] > 0 and all("receiving block" in i["content"].lower() for i in up["items"])


def test_logs_component_filter_and_page_size_limit(client):
    comp = client.get("/api/v1/overview/components").json()[0]["component"]
    r = client.get("/api/v1/logs", params={"component": comp, "page_size": 20}).json()
    assert r["total"] > 0 and all(i["component"] == comp for i in r["items"])
    assert client.get("/api/v1/logs", params={"page_size": 201}).status_code == 422


def test_components_sorted_by_errors_and_limited(client):
    rows = client.get("/api/v1/overview/components", params={"limit": 3}).json()
    assert len(rows) == 3
    keys = [(r["error"] + r["fatal"], r["warn"]) for r in rows]
    assert keys == sorted(keys, reverse=True)


def test_timeline_default_bucket_is_one_hour(client):
    d = client.get("/api/v1/overview/timeline").json()
    assert d["bucket"] == "1h" and len(d["points"]) <= 30
    t = [p["ts"] for p in d["points"]]
    assert t == sorted(t)


def test_events_count_sort(client):
    ev = client.get("/api/v1/events", params={"sort": "count_desc"}).json()
    assert [e["count"] for e in ev] == sorted((e["count"] for e in ev), reverse=True)


def test_score_distribution_for_every_model_and_bad_model(client):
    for m in ("kmeans", "iforest", "zscore"):
        d = client.get(f"/api/v1/models/{m}/score-distribution").json()
        assert d["model"] == m and len(d["bins"]) == 40
        assert all(b["upper"] > b["lower"] for b in d["bins"])
    assert client.get("/api/v1/models/gpt/score-distribution").status_code == 422


def test_unknown_route_is_problem_404(client):
    r = client.get("/api/v1/khong-co")
    assert r.status_code == 404 and r.json()["status"] == 404


def test_cors_allows_dev_origin_only(client):
    ok = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers
