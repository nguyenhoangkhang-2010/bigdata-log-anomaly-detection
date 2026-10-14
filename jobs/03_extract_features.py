"""Job 03 - trích đặc trưng cấp block (vector đếm sự kiện) + thống kê lỗi theo cửa sổ thời gian."""
from _common import run_standalone

from logad.config import resolve_paths
from logad.features import build_event_count_matrix, build_window_error_stats
from logad.storage import load_parquet, save_json, save_parquet


def run(spark, cfg) -> dict:
    paths = resolve_paths(cfg)
    fc = cfg["features"]
    parsed = load_parquet(spark, paths.parsed)

    features, meta = build_event_count_matrix(parsed, normalize=fc["normalize"])
    features = features.cache()
    n = features.count()
    save_parquet(features, paths.features)
    save_json(spark, meta, paths.features + "_meta.json")

    stats = build_window_error_stats(parsed, fc["time_window_seconds"])
    save_parquet(stats, paths.window_stats)

    print(f"[03] {n:,} block x {len(meta['vocab'])} sự kiện, chuẩn hóa = {meta['normalize']} -> {paths.features}")
    print(f"     thống kê lỗi theo cửa sổ {fc['time_window_seconds']}s -> {paths.window_stats}")
    return {"blocks": n, "events": len(meta["vocab"])}


if __name__ == "__main__":
    run_standalone("03-features", run)
