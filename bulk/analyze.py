#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计样本下载结果并外推全市场规模。"""
import collections
import json
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else r"D:\cninfo"
universe_raw = json.load(open(os.path.join(root, "_state", "universe.json"), encoding="utf-8"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bulk_cninfo import _dedup_legacy  # noqa: E402

kept, dropped = _dedup_legacy(universe_raw)
N = len(kept)
print(f"股票池：原始 {len(universe_raw)} 只，去北交所旧码重复 {len(dropped)} 只 → 有效 {N} 只")

recs = [json.loads(l) for l in open(os.path.join(root, "_state", "done.jsonl"), encoding="utf-8") if l.strip()]
codes = {r["code"] for r in recs}
print(f"样本：{len(codes)} 只股票，{len(recs)} 个任务\n")

agg = collections.defaultdict(lambda: {"n": 0, "ok": 0, "empty": 0, "fail": 0, "bytes": 0})
for r in recs:
    k = (r["kind"], r["year"] or "-")
    a = agg[k]
    a["n"] += 1
    a[r["status"]] = a.get(r["status"], 0) + 1
    a["bytes"] += r.get("size", 0) or 0

hdr = f"{'类型':<12}{'财报年':<8}{'任务':<7}{'成功':<7}{'空':<7}{'失败':<7}{'命中率':<9}{'平均MB':<9}{'小计GB'}"
print(hdr)
print("-" * len(hdr))
tot_files = tot_bytes = 0
for k in sorted(agg, key=lambda x: (x[0], str(x[1]))):
    a = agg[k]
    hr = a["ok"] / a["n"] * 100 if a["n"] else 0
    avg = a["bytes"] / a["ok"] / 1e6 if a["ok"] else 0
    print(f"{k[0]:<12}{str(k[1]):<8}{a['n']:<7}{a['ok']:<7}{a['empty']:<7}"
          f"{a.get('fail', 0):<7}{hr:<9.1f}{avg:<9.2f}{a['bytes'] / 1e9:.2f}")
    tot_files += a["ok"]
    tot_bytes += a["bytes"]

print(f"\n样本合计：{tot_files} 个文件，{tot_bytes / 1e9:.2f} GB，平均 {tot_bytes / tot_files / 1e6:.2f} MB")

# 按类型汇总命中率，外推到全市场
by_kind = collections.defaultdict(lambda: {"n": 0, "ok": 0})
for k, a in agg.items():
    by_kind[k[0]]["n"] += a["n"]
    by_kind[k[0]]["ok"] += a["ok"]

per_stock = sum(a["ok"] for a in agg.values()) / len(codes)
per_stock_bytes = tot_bytes / len(codes)
print(f"\n每只股票平均：{per_stock:.1f} 个文件，{per_stock_bytes / 1e6:.1f} MB")

task_total = sum(a["n"] for a in agg.values()) / len(codes) * N
print(f"\n全市场预估：任务 {int(task_total):,} 个 → 文件 ≈ {int(per_stock * N):,} 个，"
      f"体积 ≈ {per_stock_bytes * N / 1e9:.0f} GB")
