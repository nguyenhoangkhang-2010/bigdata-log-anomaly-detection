"""Tải LogHub HDFS_v1 từ Zenodo vào data/raw/ (178 MB nén, ~1,6 GB sau giải nén).

Chạy:  python scripts/download_loghub.py            # bản đầy đủ HDFS_v1
       python scripts/download_loghub.py --sample   # chỉ HDFS_2k (2000 dòng) để thử parser

Kết quả (bản đầy đủ):
    data/raw/HDFS.log
    data/raw/preprocessed/anomaly_label.csv      (đúng đường dẫn mà configs/pipeline.yaml đang trỏ tới)
An toàn khi chạy lại: ghi ra file .part rồi mới đổi tên; đứt kết nối thì tự tiếp tục từ chỗ dở (Range).
"""
from __future__ import annotations

import argparse
import sys
import time
import zipfile
from pathlib import Path

import requests

FULL_URL = "https://zenodo.org/records/8196385/files/HDFS_v1.zip?download=1"  # đã kiểm tra: 186.645.559 byte
SAMPLE_URL = "https://raw.githubusercontent.com/logpai/loghub/master/HDFS/HDFS_2k.log"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def download(url: str, dest: Path, retries: int = 40) -> None:
    """Tải có thể tiếp tục: nếu đứt kết nối thì thử lại và xin phần còn thiếu bằng header Range."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    # BẮT BUỘC "identity": GitHub trả file nén gzip nên Content-Length là cỡ file NÉN, còn requests lại ghi
    # file đã GIẢI NÉN -> hai số lệch nhau, script tưởng "tải thiếu" rồi xin Range và bị HTTP 416.
    plain = {"Accept-Encoding": "identity"}
    total = int(requests.head(url, allow_redirects=True, headers=plain, timeout=30).headers.get("content-length", 0))
    for attempt in range(1, retries + 1):
        have = part.stat().st_size if part.exists() else 0
        if total and have > total:  # file dở hỏng (to hơn cả file gốc) -> bỏ, tải lại từ đầu
            part.unlink()
            have = 0
        if total and have == total:
            break
        try:
            headers = {**plain, **({"Range": f"bytes={have}-"} if have else {})}
            with requests.get(url, stream=True, headers=headers, timeout=(15, 60)) as r:
                r.raise_for_status()
                if have and r.status_code != 206:  # server không hỗ trợ tiếp tục -> tải lại từ đầu
                    have = 0
                with open(part, "ab" if have else "wb") as f:
                    done, last = have, -1
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        pct = int(done * 100 / total) if total else 0
                        if pct != last and pct % 5 == 0:
                            print(f"  {dest.name}: {pct:3d}%  ({done / 1e6:.0f}/{total / 1e6:.0f} MB)", flush=True)
                            last = pct
        except requests.RequestException as e:
            have = part.stat().st_size if part.exists() else 0
            status = getattr(e.response, "status_code", None)
            why = f"HTTP {status}" if status else type(e).__name__
            print(f"  ! lỗi ở {have / 1e6:.1f} MB ({why}); thử lại {attempt}/{retries} ...", flush=True)
            time.sleep(3)
    size = part.stat().st_size if part.exists() else 0
    if total and size != total:
        raise RuntimeError(f"Tải thiếu: {size} / {total} byte. Chạy lại script để tiếp tục.")
    part.replace(dest)
    print(f"đã tải {dest} ({dest.stat().st_size / 1e6:.1f} MB)")


def valid_zip(p: Path) -> bool:
    try:
        with zipfile.ZipFile(p) as z:
            return z.testzip() is None
    except (zipfile.BadZipFile, OSError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()

    if args.sample:
        sample = RAW_DIR / "HDFS_2k.log"
        if sample.exists() and sample.stat().st_size > 0:
            print(f"đã có {sample} ({sample.stat().st_size / 1e3:.0f} KB), bỏ qua")
        else:
            download(SAMPLE_URL, sample)
        return 0

    zpath = RAW_DIR / "HDFS_v1.zip"
    out = RAW_DIR  # zip chứa HDFS.log và preprocessed/ ở cấp cao nhất nên giải nén thẳng vào data/raw
    if zpath.exists() and not valid_zip(zpath):
        print(f"{zpath.name} hỏng/rỗng ({zpath.stat().st_size} byte) -> tải lại")
        zpath.unlink()
    if not zpath.exists():
        download(FULL_URL, zpath)
    else:
        print(f"đã có {zpath.name} hợp lệ, bỏ qua bước tải")

    print(f"giải nén vào {out} ...", flush=True)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(out)
    for rel in ("HDFS.log", "preprocessed/anomaly_label.csv"):
        p = out / rel
        print(f"  {'OK ' if p.exists() else 'THIẾU'} {p.relative_to(RAW_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
