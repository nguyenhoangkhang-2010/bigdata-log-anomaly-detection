from logad.parsing import extract_block_ids, parse_line, to_template

SAMPLE = "081109 203615 148 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block blk_38865049064139660 terminating"
DELETE = (
    "081109 203807 222 INFO dfs.FSNamesystem: BLOCK* ask 10.250.19.102:50010 to delete "
    "blk_-1608999687919862906 blk_5121344529360475641"
)


def test_parse_line_fields():
    r = parse_line(SAMPLE)
    assert r["level"] == "INFO"
    assert r["component"] == "dfs.DataNode$PacketResponder"
    assert r["pid"] == 148
    assert r["content"].startswith("PacketResponder 1")


def test_parse_line_invalid_returns_none():
    assert parse_line("không phải log hdfs") is None


def test_template_masks_variable_parts():
    t = to_template(parse_line(SAMPLE)["content"])
    assert t == "PacketResponder <NUM> for block <BLK> terminating"


def test_template_masks_ip_before_numbers():
    t = to_template(parse_line(DELETE)["content"])
    assert t == "BLOCK* ask <IP> to delete <BLK> <BLK>"


def test_multiple_blocks_in_one_line():
    assert extract_block_ids(parse_line(DELETE)["content"]) == [
        "blk_-1608999687919862906",
        "blk_5121344529360475641",
    ]
