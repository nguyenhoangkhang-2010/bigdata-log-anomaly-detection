"""Job 02 - parse log thô -> parquet có cấu trúc (ts, level, component, template, event_id, block_id)."""
from _common import run_standalone

from logad.config import resolve_paths
from logad.parsing import parse_dataframe
from logad.storage import save_parquet


def run(spark, cfg) -> dict:
    paths = resolve_paths(cfg)
    raw = spark.read.text(paths.raw)
    limit = cfg["dataset"].get("sample_lines")
    if limit:
        raw = raw.limit(int(limit))
    n_raw = raw.count()

    parsed = parse_dataframe(raw, cfg["parsing"]["line_regex"]).cache()
    n_rows = parsed.count()
    n_events = parsed.select("event_id").distinct().count()
    n_blocks = parsed.where("block_id is not null").select("block_id").distinct().count()
    save_parquet(parsed, paths.parsed)

    print(f"[02] {n_raw:,} dòng thô -> {n_rows:,} hàng đã parse (mỗi block trong 1 dòng thành 1 hàng)")
    print(f"     {n_events} template (event) khác nhau · {n_blocks:,} block -> {paths.parsed}")
    return {"raw_lines": n_raw, "rows": n_rows, "events": n_events, "blocks": n_blocks}


if __name__ == "__main__":
    run_standalone("02-parse", run)
