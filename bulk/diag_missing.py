#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：某类型/年份未命中的公司，到底是没有该报告，还是被筛选规则漏掉。"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from bulk_cninfo import load_universe, query_retry  # noqa: E402
from reports import REPORT_TYPES, filter_report  # noqa: E402

root = r"C:\Users\iq112\Documents\cninfo"
rtype = sys.argv[1] if len(sys.argv) > 1 else "annual"
year = int(sys.argv[2]) if len(sys.argv) > 2 else 2025

universe = load_universe(root)
idx = {s["code"]: s for s in universe}

latest = {}
with open(os.path.join(root, "_state", "done.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            r = json.loads(line)
            latest[r["key"]] = r

have, missing = set(), []
for s in universe:
    rec = latest.get(f"{s['code']}|{rtype}|{year}")
    if rec and rec["status"] == "ok":
        have.add(s["code"])
    else:
        missing.append(s)

print(f"== {rtype} {year}：命中 {len(have)} / {len(universe)}，未命中 {len(missing)} ==")
print("\n未命中公司的状态分布：")
print(collections.Counter(
    latest.get(f"{s['code']}|{rtype}|{year}", {}).get("status", "<无记录>") for s in missing))

print("\n按板块分布（未命中）：")


def board(c):
    if c.startswith(("688", "689")):
        return "科创板"
    if c.startswith(("300", "301", "302")):
        return "创业板"
    if c.startswith("6"):
        return "沪主板"
    if c.startswith(("000", "001", "002", "003")):
        return "深主板"
    return "北交所"


print("  未命中:", collections.Counter(board(s["code"]) for s in missing))
print("  全市场:", collections.Counter(board(s["code"]) for s in universe))

random.seed(int(os.environ.get("SEED", "3")))
sample = random.sample(missing, 10)
print(f"\n抽取 {len(sample)} 家未命中公司，直接查原始公告：")
for s in sample:
    rt = REPORT_TYPES[rtype]
    start, end = rt["date_range"](year)
    try:
        anns = query_retry(s["stock_param"], s["column"], start, end,
                           category=rt["category"], timeout=40)
    except Exception as e:  # noqa: BLE001
        print(f"  {s['code']} {s['name']}: 查询异常 {e}")
        continue
    yr = [a for a in anns if str(year) in a["title"]]
    tgt = filter_report(yr, rtype) if yr else None
    print(f"  {s['code']} {s['name']:<8} [{board(s['code'])}] 原始 {len(anns)} 条 / 含{year} {len(yr)} 条 "
          f"/ 正本 {bool(tgt)}")
    for a in anns[:4]:
        print(f"       - [{a['date']}] {a['title'][:52]}")
