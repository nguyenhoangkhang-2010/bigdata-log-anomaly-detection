"""Sinh dữ liệu MÔ PHỎNG đúng định dạng LogHub HDFS_v1 (HDFS.log + anomaly_label.csv) để chạy thử pipeline có nhãn
khi chưa có bộ dữ liệu thật. Dùng lại bộ sinh của backend (backend/app/demo_data.py).

Chỉ để kiểm tra code chạy đúng từ đầu đến cuối. KHÔNG dùng chỉ số tính trên dữ liệu này cho báo cáo.

    python scripts/make_synthetic_hdfs.py [--blocks 4000] [--seed 7] [--out data/interim/synthetic]
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.demo_data import DemoDataset  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "data" / "interim" / "synthetic"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    d = DemoDataset(seed=args.seed, n_blocks=args.blocks)
    rnd = random.Random(args.seed)

    with open(out / "HDFS.log", "w", encoding="utf-8", newline="\n") as f:
        for ln in d.lines:
            f.write(f"{ln.ts:%y%m%d} {ln.ts:%H%M%S} {rnd.randint(10, 20000)} {ln.level} {ln.component}: {ln.content}\n")

    with open(out / "anomaly_label.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["BlockId", "Label"])
        for blk, bad in zip(d.block_ids, d.y, strict=True):
            w.writerow([blk, "Anomaly" if bad else "Normal"])

    print(f"đã ghi {len(d.lines):,} dòng log, {len(d.block_ids):,} block ({int(d.y.sum())} bất thường) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
