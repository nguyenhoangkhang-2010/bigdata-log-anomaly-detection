"""Chạy pipeline 02 -> 05 trên máy (Spark local, không cần Docker/HDFS), dùng chung một SparkSession.

    python scripts/run_local_pipeline.py                  # dùng dữ liệu trong data/raw (bản đầy đủ, hoặc HDFS_2k nếu chưa có)
    python scripts/run_local_pipeline.py --synthetic      # sinh dữ liệu mô phỏng CÓ NHÃN rồi chạy (để kiểm tra code)
    python scripts/run_local_pipeline.py --raw X --labels Y --only 02,03

Kết quả ghi ở data/interim/logad (hoặc data/interim/synthetic_run khi --synthetic).
Trên Windows, ghi parquet bằng pandas nên chỉ hợp dữ liệu nhỏ; bản đầy đủ 11 triệu dòng hãy chạy trong cụm Docker.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jobs"))

JOBS = {
    "01": "01_ingest_to_hdfs.py",
    "02": "02_parse_logs.py",
    "03": "03_extract_features.py",
    "04": "04_detect_anomalies.py",
    "05": "05_evaluate.py",
    "06": "06_index_elasticsearch.py",
    "07": "07_export_serving.py",
}


def load_job(filename: str):
    spec = importlib.util.spec_from_file_location(f"job_{filename[:2]}", ROOT / "jobs" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true", help="sinh dữ liệu mô phỏng có nhãn rồi chạy")
    ap.add_argument("--raw", help="file log thô (mặc định theo cấu hình)")
    ap.add_argument("--labels", help="anomaly_label.csv")
    ap.add_argument("--only", default="02,03,04,05,07", help="các job cần chạy, vd. 02,03 (06 = Elasticsearch, 07 = tệp cho backend)")
    ap.add_argument("--blocks", type=int, default=4000, help="số block khi --synthetic")
    args = ap.parse_args()

    os.environ["LOGAD_STORAGE"] = "local"
    if args.synthetic:
        syn = ROOT / "data" / "interim" / "synthetic"
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_synthetic_hdfs.py"),
                        "--blocks", str(args.blocks), "--out", str(syn)], check=True)
        os.environ["LOGAD_RAW"] = str(syn / "HDFS.log")
        os.environ["LOGAD_LABELS"] = str(syn / "anomaly_label.csv")
        os.environ.setdefault("LOGAD_LOCAL_ROOT", str(ROOT / "data" / "interim" / "synthetic_run"))
    if args.raw:
        os.environ["LOGAD_RAW"] = args.raw
    if args.labels:
        os.environ["LOGAD_LABELS"] = args.labels

    from logad.config import load_config, resolve_paths
    from logad.spark_utils import get_spark

    cfg = load_config(ROOT / "configs" / "pipeline.yaml")
    paths = resolve_paths(cfg)
    print(f"dữ liệu thô : {paths.raw}\nnhãn        : {paths.labels or '(không có)'}\nkết quả     : {paths.results_root}\n")

    spark = get_spark(cfg, "local-pipeline", local=True)
    spark.sparkContext.setLogLevel("ERROR")
    t0 = time.perf_counter()
    try:
        for key in (s.strip() for s in args.only.split(",")):
            t = time.perf_counter()
            load_job(JOBS[key]).run(spark, cfg)
            print(f"     ({time.perf_counter() - t:.1f}s)\n")
    finally:
        spark.stop()
    print(f"xong trong {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
