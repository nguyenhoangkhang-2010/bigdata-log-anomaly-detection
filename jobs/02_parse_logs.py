"""Job 02 - parse log thô -> parquet có cấu trúc (ts, level, component, template, event_id, block_id)."""
from logad.config import hdfs_uri, load_config
from logad.parsing import parse_dataframe
from logad.spark_utils import get_spark


def main() -> None:
    cfg = load_config()
    spark = get_spark(cfg, "02-parse")
    raw = spark.read.text(hdfs_uri(cfg, "raw_path"))
    limit = cfg["dataset"].get("sample_lines")
    if limit:
        raw = raw.limit(limit)

    parsed = parse_dataframe(raw, cfg["parsing"]["line_regex"])
    parsed.write.mode("overwrite").parquet(hdfs_uri(cfg, "parsed_path"))

    print(f"[02] dòng đã parse: {parsed.count():,} | số event_id khác nhau: "
          f"{parsed.select('event_id').distinct().count()}")
    spark.stop()


if __name__ == "__main__":
    main()
