from datetime import datetime

import numpy as np
import pytest

from logad.features import build_event_count_matrix, build_vocab, build_window_error_stats


def parsed(spark):
    t = lambda s: datetime(2008, 11, 9, 20, 0, s)  # noqa: E731
    rows = [  # (block_id, event_id, level, component, ts)
        ("b1", "e1", "INFO", "dfs.A", t(0)),
        ("b1", "e1", "INFO", "dfs.A", t(1)),
        ("b1", "e2", "INFO", "dfs.B", t(5)),
        ("b2", "e1", "INFO", "dfs.A", t(2)),
        ("b2", "e3", "WARN", "dfs.A", t(3)),
        ("b2", "e3", "ERROR", "dfs.A", t(9)),
        ("b3", "e2", "FATAL", "dfs.B", t(4)),
        (None, "e9", "INFO", "dfs.A", t(6)),  # dòng không thuộc block nào: phải bị bỏ qua
    ]
    return spark.createDataFrame(rows, "block_id string, event_id string, level string, component string, ts timestamp")


def by_block(df):
    return {r["block_id"]: r for r in df.collect()}


def test_vocab_ignores_lines_without_block(spark):
    assert build_vocab(parsed(spark)) == ["e1", "e2", "e3"]


def test_counts_and_scalar_features(spark):
    df, meta = build_event_count_matrix(parsed(spark), normalize="none")
    rows = by_block(df)
    assert meta["vocab"] == ["e1", "e2", "e3"]
    assert list(rows["b1"]["counts"].toArray()) == [2, 1, 0]
    assert list(rows["b2"]["counts"].toArray()) == [1, 0, 2]
    assert (rows["b1"]["n_lines"], rows["b1"]["n_events"], rows["b1"]["n_warn"], rows["b1"]["n_error"]) == (3, 2, 0, 0)
    assert (rows["b2"]["n_warn"], rows["b2"]["n_error"]) == (1, 1)
    assert rows["b3"]["n_error"] == 1  # FATAL tính vào n_error
    assert rows["b2"]["duration_s"] == 7  # từ giây 2 đến giây 9
    assert set(rows) == {"b1", "b2", "b3"}


@pytest.mark.parametrize("mode", ["l2", "tfidf"])
def test_normalized_features_have_unit_norm(spark, mode):
    df, meta = build_event_count_matrix(parsed(spark), normalize=mode)
    for r in df.collect():
        assert np.linalg.norm(r["features"].toArray()) == pytest.approx(1.0)
    assert len(meta["idf"]) == len(meta["vocab"])


def test_tfidf_gives_rarer_events_more_weight(spark):
    _, meta = build_event_count_matrix(parsed(spark), normalize="tfidf")
    idf = dict(zip(meta["vocab"], meta["idf"], strict=True))
    # e1 có ở 2/3 block, e3 chỉ có ở 1/3 block -> e3 hiếm hơn nên idf lớn hơn
    assert idf["e3"] > idf["e1"]


def test_reusing_vocab_and_idf_keeps_feature_space(spark):
    _, meta = build_event_count_matrix(parsed(spark), normalize="tfidf")
    new = parsed(spark).where("block_id = 'b1'")  # dữ liệu mới chỉ có 1 block, thiếu event e3
    df, meta2 = build_event_count_matrix(new, vocab=meta["vocab"], normalize="tfidf", idf=meta["idf"])
    assert meta2["vocab"] == meta["vocab"] and meta2["idf"] == meta["idf"]
    assert len(df.first()["features"]) == len(meta["vocab"])


def test_invalid_normalize_mode_is_rejected(spark):
    with pytest.raises(ValueError):
        build_event_count_matrix(parsed(spark), normalize="minmax")


def test_window_error_stats(spark):
    stats = build_window_error_stats(parsed(spark), window_seconds=60).collect()
    total = sum(r["n"] for r in stats)
    assert total == 8  # mọi dòng, kể cả dòng không có block
    warn = [r for r in stats if r["level"] == "WARN"]
    assert len(warn) == 1 and warn[0]["n"] == 1 and warn[0]["component"] == "dfs.A"
