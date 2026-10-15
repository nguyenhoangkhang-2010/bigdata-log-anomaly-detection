from logad.parsing import extract_block_ids, parse_line, to_template

SAMPLE = "081109 203615 148 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block blk_38865049064139660 terminating"
DELETE = (
    "081109 203807 222 INFO dfs.FSNamesystem: BLOCK* ask 10.250.19.102:50010 to delete "
    "blk_-1608999687919862906 blk_5121344529360475641"
)
ALLOC = (
    "081109 205035 28 INFO dfs.FSNamesystem: BLOCK* NameSystem.allocateBlock: "
    "/user/root/rand/_temporary/_task_200811092030_0001_m_000590_0/part-00590. blk_-1727475099218615100"
)
DELETING = (
    "081110 103201 19 INFO dfs.FSDataset: Deleting block blk_8483848473254499625 "
    "file /mnt/hadoop/dfs/data/current/subdir51/blk_8483848473254499625"
)


def content(line: str) -> str:
    return parse_line(line)["content"]


def test_parse_line_fields():
    r = parse_line(SAMPLE)
    assert r["level"] == "INFO"
    assert r["component"] == "dfs.DataNode$PacketResponder"
    assert r["pid"] == 148
    assert r["content"].startswith("PacketResponder 1")


def test_parse_line_invalid_returns_none():
    assert parse_line("không phải log hdfs") is None


def test_template_masks_variable_parts():
    assert to_template(content(SAMPLE)) == "PacketResponder <NUM> for block <BLK> terminating"


def test_template_masks_ip_before_numbers():
    assert to_template("Received block blk_1 of size 67108864 from /10.251.42.84") == "Received block <BLK> of size <NUM> from <IP>"


def test_template_collapses_block_lists():
    # lệnh xóa liệt kê nhiều block phải cùng một template, bất kể có bao nhiêu block
    one = to_template(content(DELETE).replace(" blk_5121344529360475641", ""))
    many = to_template(content(DELETE))
    assert one == many == "BLOCK* ask <IP> to delete <BLK>"


def test_template_masks_file_paths():
    assert to_template(content(ALLOC)) == "BLOCK* NameSystem.allocateBlock: <PATH> <BLK>"


def test_template_ignores_subdir_number():
    # trước đây mỗi subdirN sinh ra một template riêng (khoảng 60 biến thể)
    a = to_template(content(DELETING))
    b = to_template(content(DELETING).replace("subdir51", "subdir7"))
    assert a == b == "Deleting block <BLK> file <PATH>"


def test_multiple_blocks_in_one_line():
    assert extract_block_ids(content(DELETE)) == ["blk_-1608999687919862906", "blk_5121344529360475641"]
