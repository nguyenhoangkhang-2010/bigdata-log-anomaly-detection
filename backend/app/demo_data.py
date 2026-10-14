"""Bộ dữ liệu MÔ PHỎNG theo hình dạng log HDFS_v1 - chỉ để phát triển giao diện/API khi pipeline Spark
chưa chạy. Không phải kết quả thật; API báo `is_synthetic = true` để giao diện hiển thị rõ điều này.

Điểm số được tính thật bằng numpy (KMeans, Isolation Forest, z-score) trên dữ liệu mô phỏng,
và chỉ số Precision/Recall/F1/PR-AUC được tính từ nhãn mô phỏng - không gán cứng.
"""
from __future__ import annotations

import hashlib
import math
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from .schemas import LogLine

START = datetime(2008, 11, 9, 20, 0, 0, tzinfo=timezone.utc)
SPAN_SECONDS = 24 * 3600
# hai cửa sổ sự cố (giây kể từ START): xác suất bất thường tăng mạnh
INCIDENTS = [(6 * 3600, 6 * 3600 + 40 * 60), (17 * 3600, 17 * 3600 + 25 * 60)]

BLOCK_RE = re.compile(r"blk_-?\d+")
IP_RE = re.compile(r"/?\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?")
NUM_RE = re.compile(r"\b\d+\b")


def to_template(content: str) -> str:
    """Giống src/logad/parsing.to_template - giữ đồng bộ để event_id khớp pipeline thật."""
    return NUM_RE.sub("<NUM>", IP_RE.sub("<IP>", BLOCK_RE.sub("<BLK>", content)))


def event_id_of(template: str) -> str:
    return hashlib.md5(template.encode()).hexdigest()[:8]


def _ip(r: random.Random) -> str:
    return f"/10.250.{r.randint(5, 19)}.{r.randint(10, 250)}:50010"


# key -> (level, component, render(blk, rng) -> content)
CATALOG: dict[str, tuple[str, str, callable]] = {
    "alloc": ("INFO", "dfs.FSNamesystem",
              lambda b, r: f"BLOCK* NameSystem.allocateBlock: /user/root/sortrand/part-{r.randint(0, 99999):05d}. {b}"),
    "recv": ("INFO", "dfs.DataNode$DataXceiver",
             lambda b, r: f"Receiving block {b} src: {_ip(r)} dest: {_ip(r)}"),
    "resp_term": ("INFO", "dfs.DataNode$PacketResponder",
                  lambda b, r: f"PacketResponder {r.randint(0, 2)} for block {b} terminating"),
    "received": ("INFO", "dfs.DataNode$PacketResponder",
                 lambda b, r: f"Received block {b} of size 67108864 from {_ip(r)}"),
    "added": ("INFO", "dfs.FSNamesystem",
              lambda b, r: f"BLOCK* NameSystem.addStoredBlock: blockMap updated: {_ip(r)} is added to {b} size 67108864"),
    "verify": ("INFO", "dfs.DataBlockScanner", lambda b, r: f"Verification succeeded for {b}"),
    "ask_del": ("INFO", "dfs.FSNamesystem", lambda b, r: f"BLOCK* ask {_ip(r)} to delete {b}"),
    "deleting": ("INFO", "dfs.FSDataset",
                 lambda b, r: f"Deleting block {b} file /mnt/hadoop/dfs/data/current/subdir/{b}"),
    # ---- sự kiện lỗi ----
    "exc_write": ("ERROR", "dfs.DataNode$DataXceiver",
                  lambda b, r: f"writeBlock {b} received exception java.io.IOException: Could not read from stream"),
    "exc_recv": ("ERROR", "dfs.DataNode$DataXceiver",
                 lambda b, r: f"Exception in receiveBlock for block {b} java.io.IOException: Connection reset by peer"),
    "resp_int": ("WARN", "dfs.DataNode$PacketResponder",
                 lambda b, r: f"PacketResponder {r.randint(0, 2)} for block {b} Interrupted."),
    "not_belong": ("WARN", "dfs.FSNamesystem",
                   lambda b, r: f"BLOCK* NameSystem.addStoredBlock: addStoredBlock request received for {b} on {_ip(r)} size 67108864 But it does not belong to any file."),
    "redundant": ("WARN", "dfs.FSNamesystem",
                  lambda b, r: f"BLOCK* NameSystem.addStoredBlock: Redundant addStoredBlock request received for {b} on {_ip(r)} size 67108864"),
    "del_err": ("ERROR", "dfs.FSDataset",
                lambda b, r: f"Unexpected error trying to delete block {b}. BlockInfo not found in volumeMap."),
    "serve_exc": ("ERROR", "dfs.DataNode$DataXceiver",
                  lambda b, r: f"{_ip(r)[1:]}:Got exception while serving {b} to {_ip(r)}:"),
    "oom": ("FATAL", "dfs.DataNode",
            lambda b, r: f"Exception in thread DataXceiver for block {b}: java.lang.OutOfMemoryError: unable to create new native thread"),
}


@dataclass
class RawLine:
    ts: datetime
    key: str
    block: str
    content: str


def _normal_lines(r: random.Random, blk: str, t0: float, with_delete: bool = True) -> list[tuple[float, str]]:
    rep = 3 if r.random() < 0.9 else 2
    out: list[tuple[float, str]] = [(t0, "alloc")]
    for _ in range(rep):
        out.append((t0 + r.uniform(0.1, 1.5), "recv"))
    for _ in range(rep):
        out.append((t0 + r.uniform(2, 4), "resp_term"))
        out.append((t0 + r.uniform(2, 4), "received"))
        out.append((t0 + r.uniform(2, 5), "added"))
    if r.random() < 0.5:
        out.append((t0 + r.uniform(60, 1500), "verify"))
    if with_delete and r.random() < 0.85:
        td = t0 + r.uniform(180, 2400)
        for _ in range(rep):
            out.append((td + r.uniform(0, 3), "ask_del"))
            out.append((td + r.uniform(1, 8), "deleting"))
    return out


def _anomalous_lines(r: random.Random, blk: str, t0: float) -> list[tuple[float, str]]:
    roll = r.random()
    if roll < 0.12:  # "ẩn mình": gần như bình thường, chỉ thiếu bước xóa + 1 cảnh báo nhẹ -> khó phát hiện
        base = _normal_lines(r, blk, t0, with_delete=False)
        base.append((t0 + r.uniform(5, 30), "resp_int"))
        return base
    roll = r.random()
    out: list[tuple[float, str]] = [(t0, "alloc")]
    for _ in range(3):
        out.append((t0 + r.uniform(0.1, 1.5), "recv"))
    if roll < 0.35:  # lỗi ghi block
        for _ in range(r.randint(1, 2)):
            out.append((t0 + r.uniform(2, 6), "exc_write"))
            out.append((t0 + r.uniform(2, 6), "resp_int"))
        out.append((t0 + r.uniform(3, 7), "exc_recv"))
        out.append((t0 + r.uniform(3, 7), "received"))
        out.append((t0 + r.uniform(4, 8), "added"))
        if r.random() < 0.06:
            out.append((t0 + r.uniform(5, 9), "oom"))
    elif roll < 0.60:  # block mồ côi / yêu cầu thừa
        for _ in range(3):
            out += [(t0 + r.uniform(2, 4), "resp_term"), (t0 + r.uniform(2, 4), "received"), (t0 + r.uniform(2, 5), "added")]
        for _ in range(r.randint(2, 4)):
            out.append((t0 + r.uniform(30, 600), "not_belong"))
        for _ in range(r.randint(1, 2)):
            out.append((t0 + r.uniform(30, 600), "redundant"))
    elif roll < 0.85:  # lỗi khi xóa
        for _ in range(3):
            out += [(t0 + r.uniform(2, 4), "resp_term"), (t0 + r.uniform(2, 4), "received"), (t0 + r.uniform(2, 5), "added")]
        td = t0 + r.uniform(180, 2400)
        for _ in range(3):
            out.append((td + r.uniform(0, 3), "ask_del"))
        for _ in range(r.randint(2, 3)):
            out.append((td + r.uniform(1, 8), "del_err"))
    else:  # lỗi phục vụ đọc
        for _ in range(r.randint(2, 3)):
            out.append((t0 + r.uniform(20, 900), "serve_exc"))
        for _ in range(2):
            out += [(t0 + r.uniform(2, 4), "received"), (t0 + r.uniform(2, 5), "added")]
    return out


def _sample_start(r: random.Random) -> float:
    while True:
        t = r.uniform(0, SPAN_SECONDS - 3000)
        # lưu lượng ngày/đêm nhẹ nhàng
        if r.random() < 0.65 + 0.35 * math.sin(math.pi * t / SPAN_SECONDS):
            return t


def _in_incident(t: float) -> bool:
    return any(a <= t <= b for a, b in INCIDENTS)


# --------------------------------------------------------------------------------------
# mô hình (numpy thuần)
# --------------------------------------------------------------------------------------
def _kmeans(X: np.ndarray, k: int, rng: np.random.Generator, iters: int = 30) -> tuple[np.ndarray, np.ndarray]:
    n = X.shape[0]
    centers = [X[rng.integers(n)]]
    for _ in range(1, k):  # khởi tạo kmeans++
        d2 = np.min(((X[:, None, :] - np.array(centers)[None]) ** 2).sum(-1), axis=1)
        centers.append(X[rng.choice(n, p=d2 / d2.sum())])
    C = np.array(centers)
    for _ in range(iters):
        d = ((X[:, None, :] - C[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            if (lab == j).any():
                C[j] = X[lab == j].mean(0)
    d = np.sqrt(((X[:, None, :] - C[None]) ** 2).sum(-1))
    return d.min(1), d.argmin(1)


def _c_factor(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=float)
    out = np.zeros_like(m)
    big = m > 1
    out[big] = 2 * (np.log(m[big] - 1) + 0.5772156649) - 2 * (m[big] - 1) / m[big]
    return out


def _iforest(X: np.ndarray, rng: np.random.Generator, n_trees: int = 100, psi: int = 256) -> np.ndarray:
    n = X.shape[0]
    psi = min(psi, n)
    max_depth = int(math.ceil(math.log2(psi)))
    depth_acc = np.zeros(n)
    rows = np.arange(n)
    for _ in range(n_trees):
        feats: list[int] = []
        thr: list[float] = []
        left: list[int] = []
        right: list[int] = []
        size: list[int] = []

        def build(sample: np.ndarray, depth: int) -> int:
            node = len(feats)
            feats.append(-1); thr.append(0.0); left.append(0); right.append(0); size.append(len(sample))
            if depth >= max_depth or len(sample) <= 1:
                return node
            sub = X[sample]
            lo, hi = sub.min(0), sub.max(0)
            cand = np.flatnonzero(hi > lo)
            if cand.size == 0:
                return node
            f = int(rng.choice(cand))
            t = float(rng.uniform(lo[f], hi[f]))
            m = sub[:, f] < t
            feats[node], thr[node] = f, t
            left[node] = build(sample[m], depth + 1)
            right[node] = build(sample[~m], depth + 1)
            return node

        build(rng.choice(n, psi, replace=False), 0)
        fa, ta, la, ra, sa = map(np.array, (feats, thr, left, right, size))
        node = np.zeros(n, dtype=int)
        d = np.zeros(n)
        for _ in range(max_depth + 1):
            f = fa[node]
            internal = f >= 0
            if not internal.any():
                break
            go_left = X[rows, np.where(internal, f, 0)] < ta[node]
            node = np.where(internal, np.where(go_left, la[node], ra[node]), node)
            d += internal
        depth_acc += d + _c_factor(sa[node])
    return 2 ** (-(depth_acc / n_trees) / _c_factor(np.array([psi]))[0])


def _average_precision(score: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(-score, kind="stable")
    ys = y[order]
    tp = np.cumsum(ys)
    prec = tp / np.arange(1, len(ys) + 1)
    return float((prec * ys).sum() / max(ys.sum(), 1))


def _prf(pred: np.ndarray, y: np.ndarray) -> tuple[float, float, float, dict[str, int]]:
    tp = int((pred & y).sum()); fp = int((pred & ~y).sum())
    fn = int((~pred & y).sum()); tn = int((~pred & ~y).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
    return p, rc, f1, {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


# --------------------------------------------------------------------------------------
class DemoDataset:
    """Toàn bộ dữ liệu mô phỏng nằm trong bộ nhớ."""

    def __init__(self, seed: int = 7, n_blocks: int = 4000) -> None:
        r = random.Random(seed)
        nrng = np.random.default_rng(seed)

        # ---- 1. sinh dòng log ----
        raw: list[RawLine] = []
        self.block_ids: list[str] = []
        labels: list[bool] = []
        for _ in range(n_blocks):
            blk = f"blk_{'-' if r.random() < 0.5 else ''}{r.randint(10**17, 9 * 10**18)}"
            t0 = _sample_start(r)
            p_anom = 0.22 if _in_incident(t0) else 0.018
            is_anom = r.random() < p_anom
            seq = _anomalous_lines(r, blk, t0) if is_anom else _normal_lines(r, blk, t0)
            if not is_anom and r.random() < 0.015:  # nhiễu: block bình thường có 1 cảnh báo thoáng qua
                seq.append((t0 + r.uniform(3, 20), "resp_int"))
            self.block_ids.append(blk)
            labels.append(is_anom)
            for t, key in seq:
                ts = START + timedelta(seconds=int(t))
                raw.append(RawLine(ts, key, blk, CATALOG[key][2](blk, r)))
        raw.sort(key=lambda x: x.ts)

        self.events: dict[str, tuple[str, str, str]] = {}  # event_id -> (template, level, component)
        self.lines: list[LogLine] = []
        for x in raw:
            level, comp, _ = CATALOG[x.key]
            tpl = to_template(x.content)
            eid = event_id_of(tpl)
            self.events.setdefault(eid, (tpl, level, comp))
            self.lines.append(LogLine.model_construct(
                ts=x.ts, level=level, component=comp, block_id=x.block, content=x.content, template=tpl, event_id=eid))

        n = len(self.block_ids)
        self.index = {b: i for i, b in enumerate(self.block_ids)}
        self.block_lines: list[list[int]] = [[] for _ in range(n)]
        for li, ln in enumerate(self.lines):
            self.block_lines[self.index[ln.block_id]].append(li)

        # ---- 2. đặc trưng cấp block ----
        self.event_ids = sorted(self.events)
        col = {e: j for j, e in enumerate(self.event_ids)}
        counts = np.zeros((n, len(self.event_ids)))
        warn = np.zeros(n, dtype=int)
        err = np.zeros(n, dtype=int)
        for i, idxs in enumerate(self.block_lines):
            for li in idxs:
                ln = self.lines[li]
                counts[i, col[ln.event_id]] += 1
                if ln.level == "WARN":
                    warn[i] += 1
                elif ln.level in ("ERROR", "FATAL"):
                    err[i] += 1
        self.counts, self.warn_count, self.error_count = counts, warn, err
        self.line_count = counts.sum(1).astype(int)
        self.first_ts = [self.lines[ix[0]].ts for ix in self.block_lines]
        self.last_ts = [self.lines[ix[-1]].ts for ix in self.block_lines]
        self.y = np.array(labels, dtype=bool)

        df = (counts > 0).sum(0)
        self.idf = np.log(n / (1 + df)) + 1
        tfidf = np.log1p(counts) * self.idf
        norm = np.linalg.norm(tfidf, axis=1, keepdims=True)
        tfidf = tfidf / np.where(norm == 0, 1, norm)

        # ---- 3. mô hình ----
        self.scores: dict[str, np.ndarray] = {}
        self.thr: dict[str, float] = {}
        self.eval_rows: list[dict] = []
        self.clusters = np.zeros(n, dtype=int)

        t = time.perf_counter()
        k = 6
        s, self.clusters = _kmeans(tfidf, k, nrng)
        self._register("kmeans", "KMeans · Spark MLlib", "distributed", s, float(np.percentile(s, 97)),
                       time.perf_counter() - t, {"k": k, "seed": seed, "chuẩn hóa": "TF-IDF + L2", "ngưỡng": "percentile 97"})

        t = time.perf_counter()
        feats = np.column_stack([np.log1p(counts), self.line_count, (counts > 0).sum(1), warn + err])
        s = _iforest(feats, nrng)
        self._register("iforest", "Isolation Forest · scikit-learn", "single-node", s, float(np.percentile(s, 96)),
                       time.perf_counter() - t, {"n_estimators": 100, "max_samples": 256, "ngưỡng": "percentile 96"})

        t = time.perf_counter()
        x = (warn + err).astype(float)
        z = np.maximum((x - x.mean()) / (x.std() or 1.0), 0)
        self._register("zscore", "Z-score số lỗi", "statistical", z, 3.0, time.perf_counter() - t,
                       {"đặc trưng": "WARN + ERROR theo block", "ngưỡng": "z > 3"})

        self.flags = {m: self.scores[m] > self.thr[m] for m in self.scores}
        self.finished_at = START + timedelta(seconds=SPAN_SECONDS + 3600)
        self.start = self.lines[0].ts
        self.end = self.lines[-1].ts

    def _register(self, name: str, label: str, kind: str, score: np.ndarray, thr: float, secs: float, params: dict) -> None:
        self.scores[name], self.thr[name] = score, thr
        pred = score > thr
        p, rc, f1, cm = _prf(pred, self.y)
        self.eval_rows.append({
            "name": name, "label": label, "kind": kind, "precision": p, "recall": rc, "f1": f1,
            "pr_auc": _average_precision(score, self.y), "threshold": thr, "confusion": cm,
            "train_seconds": round(secs, 3), "params": params,
        })
