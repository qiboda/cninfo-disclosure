#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 manifest.csv 的 filepath 列：老根目录 → 新根目录。

背景：数据集整体搬家（C:\\Users\\iq112\\Documents\\cninfo → E:\\cninfo）之后，
manifest.csv 里 101,802 行的 filepath 仍指向旧路径，导致「文件是否存在」类校验
全部误判为缺失。

用法：
  python repair_manifest_paths.py <root> <旧根> <新根> [--dry-run]
"""
import csv
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else r"E:\cninfo"
old = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\iq112\Documents\cninfo"
new = sys.argv[3] if len(sys.argv) > 3 else root
dry = "--dry-run" in sys.argv

path = os.path.join(root, "manifest.csv")
tmp = path + ".tmp"

rows = 0
changed = 0
missing = 0
with open(path, encoding="utf-8-sig", newline="") as f, \
        open(tmp, "w", encoding="utf-8-sig", newline="") as out:
    rd = csv.DictReader(f)
    fields = rd.fieldnames
    wr = csv.DictWriter(out, fieldnames=fields)
    wr.writeheader()
    for r in rd:
        rows += 1
        fp = r.get("filepath") or ""
        if fp.startswith(old):
            fp2 = new + fp[len(old):]
            r["filepath"] = fp2
            changed += 1
        else:
            fp2 = fp
        if fp2 and not os.path.exists(fp2):
            missing += 1
        wr.writerow(r)

print(f"行数 {rows}，改写 {changed}，改写后路径仍不存在 {missing}")
if dry:
    os.remove(tmp)
    print("--dry-run：未落盘")
else:
    os.replace(tmp, path)
    print(f"已写回 {path}")
