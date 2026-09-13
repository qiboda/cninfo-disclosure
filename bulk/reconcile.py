#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对：状态记录引用的文件体积 vs 磁盘实际枚举体积，找出差异来源。"""
import json
import os
import collections
import sys

root = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\iq112\Documents\cninfo"

latest = {}
with open(os.path.join(root, "_state", "done.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            r = json.loads(line)
            latest[r["key"]] = r

ok = [r for r in latest.values() if r["status"] == "ok"]
paths = [r.get("path", "") for r in ok]
print(f"ok 记录数: {len(ok)}")
print(f"  其中 path 为空: {sum(1 for p in paths if not p)}")
print(f"  唯一 path 数: {len(set(paths))}")

rec_total = 0
rec_missing = 0
for p in paths:
    if p and os.path.exists(p):
        rec_total += os.path.getsize(p)
    else:
        rec_missing += 1
print(f"  记录引用文件合计: {rec_total/1e9:.2f} GB（缺失 {rec_missing} 个）")

# 记录里存的大小 vs 磁盘现况
size_delta = 0
mismatch = 0
for r in ok:
    p = r.get("path", "")
    if p and os.path.exists(p):
        d = os.path.getsize(p) - (r.get("size") or 0)
        if d:
            mismatch += 1
            size_delta += d
print(f"  记录内 size 与磁盘现况不一致的: {mismatch} 个，差值合计 {size_delta/1e9:.2f} GB")

disk_total = 0
disk_n = 0
by_dir = collections.defaultdict(int)
for sub in ("reports", "prospectus"):
    base = os.path.join(root, sub)
    for dirpath, _dirnames, filenames in os.walk(base):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(fp)
            except OSError:
                continue
            disk_total += sz
            disk_n += 1
            by_dir[os.path.relpath(dirpath, root)] += sz
print(f"  磁盘实际枚举: {disk_n} 个文件, {disk_total/1e9:.2f} GB")

print("\n按目录（磁盘实际）：")
for d, b in sorted(by_dir.items(), key=lambda x: -x[1])[:12]:
    print(f"  {d:<28} {b/1e9:7.2f} GB")
