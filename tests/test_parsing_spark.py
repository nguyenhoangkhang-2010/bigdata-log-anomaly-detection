"""Phiên bản Spark của bộ parse phải cho CÙNG template / event_id với phiên bản Python."""
import hashlib
from pathlib import Path

import pytest

from logad.parsing import parse_dataframe, parse_line, to_template

LINES = [
    "081109 203615 148 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block blk_38865049064139660 terminating",
    "081109 203807 222 INFO dfs.FSNamesystem: BLOCK* ask 10.250.19.102:50010 to delete blk_-1608999687919862906 blk_5121344529360475641",
    "081109 205035 28 INFO dfs.FSNamesystem: BLOCK* NameSystem.allocateBlock: /user/root/rand/_temporary/_task_200811092030_0001_m_000590_0/part-00590. blk_-1727475099218615100",
    "081110 103201 19 INFO dfs.FSDataset: Deleting block blk_8483848473254499625 file /mnt/hadoop/dfs/data/current/subdir51/blk_8483848473254499625",
    "081111 071654 18 WARN dfs.DataNode$DataXceiver: 10.251.30.85:50010:Got exception while serving blk_-2918118818249673980 to /10.251.90.64:",
    "dòng rác không đúng định dạng",
]


def test_spark_matches_python_on_handwritten_lines(spark):
    df = spark.createDataFrame([(x,) for x in LINES], ["value"])
    rows = parse_dataframe(df).collect()
    expected_lines = [x for x in LINES if parse_line(x)]
    # dòng rác bị loại; dòng có 2 block thành 2 hàng
    assert len({r["content"] for r in rows}) == len(expected_lines)
    for r in rows:
        tpl = to_template(r["content"])
        assert r["template"] == tpl
        assert r["event_id"] == hashlib.md5(tpl.encode()).hexdigest()[:8]
    assert sorted(r["block_id"] for r in rows if "to delete" in r["content"]) == [
        "blk_-1608999687919862906", "blk_5121344529360475641",
    ]


SAMPLE = Path(__file__).resolve().parents[1] / "data" / "raw" / "HDFS_2k.log"


@pytest.mark.skipif(not SAMPLE.exists(), reason="chưa tải data/raw/HDFS_2k.log")
def test_spark_matches_python_on_real_sample(spark):
    raw = spark.read.text(str(SAMPLE))
    got = {(r["content"], r["template"]) for r in parse_dataframe(raw).select("content", "template").collect()}
    want = {(p["content"], to_template(p["content"])) for p in map(parse_line, SAMPLE.read_text(encoding="utf-8").splitlines())}
    assert got == want
