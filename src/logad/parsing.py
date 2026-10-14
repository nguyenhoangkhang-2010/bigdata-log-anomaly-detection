"""Parse dòng log HDFS và rút template (event) bằng cách mask các phần biến thiên.

Dòng mẫu:
    081109 203615 148 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block blk_38865049064139660 terminating
-> date=081109 time=203615 pid=148 level=INFO component=dfs.DataNode$PacketResponder
   content="PacketResponder 1 for block blk_... terminating"
   template="PacketResponder <NUM> for block <BLK> terminating"

Có 2 phiên bản: thuần Python (dễ unit test) và Spark DataFrame (chạy phân tán). Cả hai dùng CHUNG danh sách
`MASK_RULES` nên không thể lệch nhau (có test đối chiếu ở tests/test_parsing_spark.py).
"""
from __future__ import annotations

import re
from functools import reduce

LINE_REGEX = r"^(\d{6})\s+(\d{6})\s+(\d+)\s+(INFO|WARN|ERROR|FATAL|DEBUG)\s+([\w.$]+):\s*(.*)$"
LINE_RE = re.compile(LINE_REGEX)
BLOCK_RE = re.compile(r"blk_-?\d+")

# (tên, regex, thay thế). THỨ TỰ QUAN TRỌNG. Giữ regex đơn giản để cú pháp Python và Java (Spark) cho cùng kết quả.
MASK_RULES: list[tuple[str, str, str]] = [
    ("block", r"blk_-?\d+", "<BLK>"),
    # IP (kèm "/" đứng trước và ":port" theo sau nếu có)
    ("ip", r"/?\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?", "<IP>"),
    # đường dẫn file: /user/root/rand/_temporary/_task_2008..._m_000590_0/part-00590. , /mnt/hadoop/dfs/data/current/subdir5/<BLK>
    # (làm SAU khi block/IP đã được che; nếu không, mỗi subdirN và mỗi mã task sẽ sinh ra một template riêng)
    ("path", r"/[\w.\-]+(?:/[\w.\-<>]+)*", "<PATH>"),
    # lệnh xóa/sao chép có thể liệt kê hàng chục block -> gộp thành một <BLK>
    ("block_list", r"<BLK>(?:\s+<BLK>)+", "<BLK>"),
    ("number", r"\b\d+\b", "<NUM>"),
    ("spaces", r"\s{2,}", " "),
]
_COMPILED = [(re.compile(rx), repl) for _, rx, repl in MASK_RULES]


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
    """Che các phần biến thiên (block, IP, đường dẫn, số) -> template."""
    for rx, repl in _COMPILED:
        content = rx.sub(repl, content)
    return content.strip()


# ---------------------------------------------------------------------------
# Phiên bản Spark
# ---------------------------------------------------------------------------
def parse_dataframe(raw_df, line_regex: str = LINE_REGEX):
    """raw_df: DataFrame 1 cột `value` (spark.read.text). Trả về DataFrame đã parse.

    Cột kết quả: ts (timestamp), pid, level, component, content, template, event_id, block_id.
    Mỗi block trong 1 dòng được explode thành 1 hàng riêng (dòng không có block giữ 1 hàng, block_id = null).
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
    masked = reduce(lambda col, rule: F.regexp_replace(col, rule[1], rule[2]), MASK_RULES, F.col("content"))
    p = p.withColumn("template", F.trim(masked))
    p = p.withColumn("event_id", F.substring(F.md5("template"), 1, 8))
    p = p.withColumn("block_id", F.explode_outer(F.expr(r"regexp_extract_all(content, 'blk_-?\\d+', 0)")))
    return p.drop("date", "time")
