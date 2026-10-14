"""Tải LogHub HDFS_v1 từ Zenodo vào data/raw/ (~ 150MB nén, ~1.5GB sau giải nén).

Chạy:  python scripts/download_loghub.py            # bản đầy đủ HDFS_v1
       python scripts/download_loghub.py --sample   # chỉ HDFS_2k (2000 dòng) để thử parser

Kiểm tra lại URL/bản ghi tại https://github.com/logpai/loghub (mục HDFS) trước khi chạy.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import requests

# TODO: xác nhận lại link Zenodo mới nhất trong README của loghub
FULL_URL = "https://zenodo.org/records/8196385/files/HDFS_v1.zip?download=1"
SAMPLE_URL = "https://raw.githubusercontent.com/logpai/loghub/master/HDFS/HDFS_2k.log"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    print(f"đã tải {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    if args.sample:
        download(SAMPLE_URL, RAW_DIR / "HDFS_2k.log")
        return 0

    zpath = RAW_DIR / "HDFS_v1.zip"
    download(FULL_URL, zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(RAW_DIR / "HDFS_v1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
