#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 3：盘点现状 —— 既有清单里招股书/三季报的最新披露日期，以及根目录已有结构。"""
import csv
import os
from collections import Counter

ROOT = r"C:\Users\iq112\Documents\cninfo"
OUT = open(r"C:\Users\iq112\codes\cninfo-disclosure\bulk\probe_new.out.txt",
           "w", encoding="utf-8")


def p(*a):
    print(*a, file=OUT)


p("## 根目录条目")
for name in sorted(os.listdir(ROOT)):
    full = os.path.join(ROOT, name)
    p(f"  {'DIR ' if os.path.isdir(full) else 'FILE'} {name}")

p("\n## manifest.csv")
mf = os.path.join(ROOT, "manifest.csv")
p(f"exists={os.path.exists(mf)}")
rows = []
with open(mf, encoding="utf-8-sig", newline="") as fh:
    rd = csv.DictReader(fh)
    p("columns:", rd.fieldnames)
    for r in rd:
        rows.append(r)
p(f"rows={len(rows)}")
p("kind counts:", dict(Counter(r.get("kind", "?") for r in rows)))

pros = [r for r in rows if r.get("kind") == "prospectus"]
p(f"prospectus rows={len(pros)}")
if pros:
    ds = sorted(r.get("date", "") for r in pros)
    p("prospectus date min/max:", ds[0], "/", ds[-1])
    p("last 12 by date:")
    for r in sorted(pros, key=lambda x: x.get("date", ""))[-12:]:
        p("   ", r.get("date"), r.get("code"), r.get("name"), "|", r.get("title", "")[:60])

q3 = [r for r in rows if r.get("kind") == "q3"]
p(f"\nq3 rows={len(q3)} by year:", dict(Counter(r.get("year", "?") for r in q3)))
p("2026 q3 rows:", [r.get("title") for r in q3 if r.get("year") == "2026"])

p("\n## 磁盘实际文件数")
for sub in ("reports/2026/q3", "reports/2025/q3", "prospectus"):
    d = os.path.join(ROOT, *sub.split("/"))
    n = len(os.listdir(d)) if os.path.isdir(d) else -1
    p(f"  {sub}: {n}")

OUT.close()
print("done")
