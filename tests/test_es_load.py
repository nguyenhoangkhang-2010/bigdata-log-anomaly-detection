"""Nạp thư mục serving vào Elasticsearch GIẢ (không cần Elasticsearch): kiểm tra tài liệu sinh ra đúng dạng."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend" / "tests")]

from app.demo_data import DemoDataset  # noqa: E402
from serving_fixture import build_serving_dir  # noqa: E402

from logad import es_load  # noqa: E402


class FakeIndices:
    def __init__(self):
        self.created, self.existing = [], set()

    def exists(self, index):
        return index in self.existing

    def delete(self, index):
        self.existing.discard(index)

    def create(self, index, mappings, settings):
        self.created.append((index, settings))
        self.existing.add(index)

    def refresh(self, index):
        pass


class FakeES:
    def __init__(self):
        self.indices = FakeIndices()


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    import elasticsearch.helpers as helpers

    d = DemoDataset(seed=7, n_blocks=300)
    serving = build_serving_dir(tmp_path_factory.mktemp("serving"), d)
    docs: dict[str, list] = {}

    def fake_bulk(es, actions, chunk_size, raise_on_error, stats_only):
        acts = list(actions)
        docs.setdefault(acts[0]["_index"], []).extend(acts)
        return len(acts), []

    real = helpers.bulk
    helpers.bulk = fake_bulk
    try:
        es = FakeES()
        res = es_load.load_serving(serving, "http://unused", "t", client=es)
    finally:
        helpers.bulk = real
    return d, res, docs, es


def test_every_index_is_filled(loaded):
    d, res, docs, es = loaded
    assert res["anomalies"]["indexed"] == len(d.block_ids) and res["meta"]["indexed"] == 1
    assert {i for i, _ in es.indices.created} == {f"t-{k}" for k in es_load.KINDS}
    assert all(r["errors"] == 0 for r in res.values())


def test_anomaly_documents_carry_scores_flags_counts_and_label(loaded):
    d, _, docs, _ = loaded
    first = docs["t-anomalies"][0]
    doc = first["_source"]
    assert first["_id"] == doc["block_id"] == d.block_ids[0]
    assert {"kmeans_score", "kmeans_flag", "iforest_flag", "zscore_flag", "top_events", "counts", "label", "flagged_by"} <= set(doc)
    assert doc["first_ts"].endswith("Z") and doc["counts"] and all(v > 0 for v in doc["counts"].values())
    assert doc["kmeans_score"] == round(doc["kmeans_score"], 4)
    flagged = {a["_id"] for a in docs["t-anomalies"] if a["_source"]["kmeans_flag"]}
    assert len(flagged) == int(d.flags["kmeans"].sum())


def test_time_fields_are_iso_and_no_epoch_left(loaded):
    _, _, docs, _ = loaded
    for index in ("t-error-stats", "t-spikes", "t-logs"):
        src = docs[index][0]["_source"]
        assert "ts_epoch" not in src and src["ts"].endswith("Z")


def test_meta_document_has_vocab_and_normal_mean(loaded):
    _, _, docs, _ = loaded
    meta = docs["t-meta"][0]
    assert meta["_id"] == "meta"
    m = meta["_source"]
    assert len(m["normal_mean"]) == len(m["vocab"]) and all(x >= 0 for x in m["normal_mean"])
    assert m["evaluation"]["models"]["kmeans"]["f1"] > 0
