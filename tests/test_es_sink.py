"""Kiểm thử es_sink bằng Elasticsearch GIẢ (không cần chạy Elasticsearch)."""
import pytest

from logad import es_sink


class FakeIndices:
    def __init__(self):
        self.calls, self.existing = [], set()

    def exists(self, index):
        return index in self.existing

    def delete(self, index):
        self.calls.append(("delete", index))
        self.existing.discard(index)

    def create(self, index, mappings, settings):
        self.calls.append(("create", index, mappings, settings))
        self.existing.add(index)

    def refresh(self, index):
        self.calls.append(("refresh", index))


class FakeES:
    def __init__(self):
        self.indices = FakeIndices()


@pytest.fixture
def captured(monkeypatch):
    got = {}

    def fake_bulk(es, actions, chunk_size, raise_on_error, stats_only):
        got["actions"] = list(actions)
        got["chunk_size"] = chunk_size
        return len(got["actions"]), []

    monkeypatch.setattr("elasticsearch.helpers.bulk", fake_bulk)
    return got


def test_write_df_creates_index_with_mapping_and_sends_docs(spark, captured):
    from pyspark.sql import functions as F

    df = spark.createDataFrame([("b1", 1.5, 3), ("b2", float("nan"), 0)], "block_id string, kmeans_score double, n_error int")
    df = df.withColumn("first_ts", F.to_timestamp(F.lit("081109 203615"), "yyMMdd HHmmss"))
    es = FakeES()
    res = es_sink.write_df(df, "logad-anomalies", "http://unused", "anomalies", id_col="block_id", client=es)

    assert res == {"indexed": 2, "errors": 0}
    kinds = [c[0] for c in es.indices.calls]
    assert kinds == ["create", "refresh"]
    create = es.indices.calls[0]
    assert create[2] == es_sink.MAPPINGS["anomalies"] and create[3]["number_of_replicas"] == 0

    docs = {a["_id"]: a for a in captured["actions"]}
    assert set(docs) == {"b1", "b2"} and docs["b1"]["_index"] == "logad-anomalies"
    assert docs["b1"]["_source"]["first_ts"] == "2008-11-09T20:36:15Z"  # ISO UTC, không bị lệch múi giờ máy
    assert docs["b2"]["_source"]["kmeans_score"] is None  # NaN không hợp lệ trong JSON


def test_recreate_deletes_existing_index_first(spark, captured):
    es = FakeES()
    es.indices.existing.add("logad-spikes")
    df = spark.createDataFrame([(1,)], "n int")
    es_sink.write_df(df, "logad-spikes", "http://unused", "spikes", client=es)
    assert [c[0] for c in es.indices.calls][:2] == ["delete", "create"]


def test_no_id_col_lets_elasticsearch_generate_ids(spark, captured):
    df = spark.createDataFrame([("INFO", 3)], "level string, n int")
    es_sink.write_df(df, "logad-error-stats", "http://unused", "error_stats", client=FakeES())
    assert "_id" not in captured["actions"][0]


def test_unknown_kind_is_rejected(spark):
    with pytest.raises(ValueError):
        es_sink.write_df(spark.createDataFrame([(1,)], "n int"), "x", "http://unused", "nope", client=FakeES())


def test_every_job06_field_is_mapped():
    # các trường mà job 06 ghi phải có trong ánh xạ, nếu không Elasticsearch sẽ tự đoán kiểu
    assert {"block_id", "kmeans_score", "kmeans_flag", "iforest_flag", "zscore_flag", "cluster", "label", "flagged_by"} <= set(
        es_sink.MAPPINGS["anomalies"]["properties"]
    )
    assert {"ts", "level", "component", "block_id", "content"} <= set(es_sink.MAPPINGS["logs"]["properties"])
