import numpy as np

from logad import serving

VOCAB = ["e_recv", "e_term", "e_err"]


def test_top_events_name_what_deviates_from_normal_blocks():
    counts = np.array([[3, 3, 0], [3, 3, 0], [3, 3, 0], [3, 0, 4]], dtype=np.float32)
    normal = np.array([True, True, True, False])
    tops = serving.top_deviating_events(counts, np.ones(3), normal, VOCAB, top=2)
    assert tops[0] == [] and tops[1] == []  # block bình thường: không lệch gì
    assert set(tops[3]) == {"e_term", "e_err"} and tops[3][0] == "e_err"  # lệch nhiều nhất đứng đầu


def test_top_events_weights_by_idf():
    counts = np.array([[1, 1, 0], [3, 2, 0]], dtype=np.float32)
    tops = serving.top_deviating_events(counts, np.array([1.0, 10.0, 1.0]), np.array([True, False]), VOCAB, top=1)
    assert tops[1] == ["e_term"]  # lệch nhỏ hơn nhưng event hiếm (idf cao) nên được ưu tiên


def test_event_stats_lift_is_ratio_to_baseline():
    counts = np.array([[1, 1, 0], [1, 1, 0], [1, 0, 3], [1, 0, 3]], dtype=np.float32)
    flagged = np.array([False, False, True, True])
    rows = {r["event_id"]: r for r in serving.event_stats(counts, flagged, VOCAB)}
    assert rows["e_err"]["anomaly_ratio"] == 1.0 and rows["e_err"]["block_count"] == 2
    assert rows["e_recv"]["anomaly_ratio"] == 0.5
    base = 8 / 12  # 8 lần xuất hiện nằm trong block gắn cờ (2 + 6) / tổng 12 (4 + 2 + 6)
    assert rows["e_err"]["lift"] == round(1.0 / base, 2)
    assert rows["e_err"]["lift"] > rows["e_recv"]["lift"]


def test_event_stats_without_flagged_blocks_does_not_divide_by_zero():
    rows = serving.event_stats(np.ones((3, 3), dtype=np.float32), np.zeros(3, dtype=bool), VOCAB)
    assert all(r["lift"] == 0.0 and r["anomaly_ratio"] == 0.0 for r in rows)
