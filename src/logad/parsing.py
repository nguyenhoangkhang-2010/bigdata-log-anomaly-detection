"""Parse dòng log HDFS và rút template (event) bằng cách mask các phần biến thiên.

Dòng mẫu:
    081109 203615 148 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block blk_38865049064139660 terminating
-> date=081109 time=203615 pid=148 level=INFO component=dfs.DataNode$PacketResponder
   content="PacketResponder 1 for block blk_... terminating"
   template="PacketResponder <NUM> for block <BLK> terminating"

Có 2 phiên bản: thuần Python (dễ unit test) và Spark DataFrame (chạy phân tán).
"""
from __future__ import annotations

import re

LINE_RE = re.compile(r"^(\d{6})\s+(\d{6})\s+(\d+)\s+(INFO|WARN|ERROR|FATAL|DEBUG)\s+([\w.$]+):\s*(.*)$")
BLOCK_RE = re.compile(r"blk_-?\d+")
IP_RE = re.compile(r"/?\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?")
NUM_RE = re.compile(r"\b\d+\b")


def parse_line(line: str) -> dict | None:
    """Trả về dict các trường, hoặc None nếu dòng không khớp định dạng."""
    m = LINE_RE.match(line.strip())
    if not m:
        return None
    date, time, pid, level, component, content = m.groups()
    return {
        "date": date,
        "time": time,
        "pid": int(pid),
        "level": level,
        "component": component,
        "content": content,
    }


def extract_block_ids(content: str) -> list[str]:
    """Một dòng có thể chứa nhiều block (vd. lệnh delete nhiều block)."""
    return BLOCK_RE.findall(content)


def to_template(content: str) -> str:
    """Mask block id, IP, số -> template. Thứ tự quan trọng: block -> IP -> số."""
    t = BLOCK_RE.sub("<BLK>", content)
    t = IP_RE.sub("<IP>", t)
    t = NUM_RE.sub("<NUM>", t)
    return t


# ---------------------------------------------------------------------------
# Phiên bản Spark (chưa chạy thử trên cụm - hoàn thiện ở Tuần 6-7)
# ---------------------------------------------------------------------------
def parse_dataframe(raw_df, line_regex: str):
    """raw_df: DataFrame 1 cột `value` (spark.read.text). Trả về DataFrame đã parse.

    Cột kết quả: ts (timestamp), pid, level, component, content, template, event_id, block_id.
    Mỗi block trong 1 dòng được explode thành 1 hàng riêng.
    """
    from pyspark.sql import functions as F

    p = raw_df.select(
        F.regexp_extract("value", line_regex, 1).alias("date"),
        F.regexp_extract("value", line_regex, 2).alias("time"),
        F.regexp_extract("value", line_regex, 3).cast("int").alias("pid"),
        F.regexp_extract("value", line_regex, 4).alias("level"),
        F.regexp_extract("value", line_regex, 5).alias("component"),
        F.regexp_extract("value", line_regex, 6).alias("content"),
    ).where(F.col("level") != "")

    p = p.withColumn("ts", F.to_timestamp(F.concat_ws(" ", "date", "time"), "yyMMdd HHmmss"))
    p = p.withColumn(
        "template",
        F.regexp_replace(
            F.regexp_replace(
                F.regexp_replace("content", r"blk_-?\d+", "<BLK>"),
                r"/?\d{1,3}(\.\d{1,3}){3}(:\d+)?",
                "<IP>",
            ),
            r"\b\d+\b",
            "<NUM>",
        ),
    )
    p = p.withColumn("event_id", F.substring(F.md5("template"), 1, 8))
    p = p.withColumn("block_id", F.explode_outer(F.expr(r"regexp_extract_all(content, 'blk_-?\\d+', 0)")))
    return p.drop("date", "time")
