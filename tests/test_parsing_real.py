"""Kiểm tra bộ che template trên DỮ LIỆU THẬT (bản mẫu LogHub) và đối chiếu với 29 template chuẩn của LogHub.

Tự bỏ qua nếu chưa có dữ liệu:
  - data/raw/HDFS_2k.log                     <- python scripts/download_loghub.py --sample
  - data/interim/HDFS.log_templates.csv      <- có trong HDFS_v1.zip (preprocessed/HDFS.log_templates.csv)
"""
import csv
import re
from pathlib import Path

import pytest

from logad.parsing import parse_line, to_template

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "raw" / "HDFS_2k.log"
REFERENCE = ROOT / "data" / "interim" / "HDFS.log_templates.csv"

pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="chưa tải data/raw/HDFS_2k.log")


@pytest.fixture(scope="module")
def parsed():
    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    return lines, [parse_line(x) for x in lines]


def test_every_line_parses(parsed):
    lines, rows = parsed
    assert len(lines) == 2000
    assert all(rows)


def test_template_count_is_close_to_reference(parsed):
    # trước khi che đường dẫn/subdir/danh sách block: 192 template. LogHub gốc có 29 cho toàn bộ HDFS_v1.
    _, rows = parsed
    templates = {to_template(r["content"]) for r in rows}
    assert len(templates) <= 29, sorted(templates)


def _reference_regexes():
    with REFERENCE.open(encoding="utf-8") as f:
        out = {}
        for row in csv.DictReader(f):
            parts = [re.escape(p.strip()) for p in row["EventTemplate"].split("[*]")]
            out[row["EventId"]] = re.compile(".*".join(parts), re.DOTALL)
        return out


@pytest.mark.skipif(not REFERENCE.exists(), reason="chưa có data/interim/HDFS.log_templates.csv")
def test_templates_do_not_merge_different_reference_events(parsed):
    # mỗi template của ta chỉ được rơi vào TỐI ĐA 1 sự kiện chuẩn: nếu 2 sự kiện chuẩn khác nhau bị gộp
    # thành một template thì ta mất thông tin phân biệt
    _, rows = parsed
    ref = _reference_regexes()
    seen: dict[str, set[str]] = {}
    for r in rows:
        tpl = to_template(r["content"])
        seen.setdefault(tpl, set()).update(eid for eid, rx in ref.items() if rx.search(r["content"]))
    merged = {t: ids for t, ids in seen.items() if len(ids) > 1}
    assert not merged, merged
