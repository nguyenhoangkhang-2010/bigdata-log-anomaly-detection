"""Job 06 - nạp kết quả pipeline vào Elasticsearch (nơi lưu trữ mà API/dashboard truy vấn).

Đọc thư mục serving do job 07 xuất (block + điểm 3 mô hình, thống kê lỗi theo thời gian, đột biến, dòng log, mẫu sự kiện,
chỉ số mô hình) rồi bulk vào các index `<prefix>-*`. Cần Elasticsearch đang chạy: `docker compose --profile search up -d`.
Đặt ES_HOST nếu không dùng địa chỉ trong cấu hình.
"""
import os
from pathlib import Path

from _common import run_standalone

from logad.config import resolve_paths
from logad.es_load import load_serving, index_name


def run(spark, cfg) -> dict:
    paths = resolve_paths(cfg)
    es = cfg["elasticsearch"]
    host = os.environ.get("ES_HOST", es["host"])
    serving_dir = Path(paths.serving)
    if not (serving_dir / "meta.json").exists():
        raise FileNotFoundError(f"Chưa có {serving_dir}: chạy job 07 (python scripts/run_local_pipeline.py --only 07) trước.")

    out = load_serving(serving_dir, host, es["index_prefix"])
    print(f"[06] Elasticsearch {host} (index {index_name(es['index_prefix'], '*')})")
    for kind, r in out.items():
        print(f"     {kind:<12} {r['indexed']:>9,} tài liệu · {r['errors']} lỗi")
    return out


if __name__ == "__main__":
    run_standalone("06-index", run)
