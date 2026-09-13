#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试：q3 筛选失败原因 + 北交所代码重复。"""
import json
import os
import sys
import collections

BULK = r"C:\Users\iq112\codes\cninfo-disclosure\bulk"
sys.path.insert(0, BULK)
sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")

from bulk_cninfo import load_universe, query_retry, PROSPECTUS_FROM, PROSPECTUS_TO
from reports import REPORT_TYPES, filter_report, EXCLUDE_KEYWORDS
from prospectus import filter_prospectus

u = load_universe(r"D:\cninfo")

print("=" * 78)
print("[1] 北交所新旧代码重复检查（按公司简称）")
by_name = collections.defaultdict(list)
for s in u:
    by_name[s["name"]].append(s["code"])
dups = {k: v for k, v in by_name.items() if len(v) > 1}
print(f"  简称重复的公司数: {len(dups)}")
for k, v in list(dups.items())[:15]:
    print(f"   - {k}: {v}")

print("\n" + "=" * 78)
print("[2] q3 筛选失败原因：002284 / 000601")
for code in ["002284", "000601", "600519"]:
    st = next((s for s in u if s["code"] == code), None)
    if not st:
        print(f"  {code} 不在池中")
        continue
    rt = REPORT_TYPES["q3"]
    start, end = rt["date_range"](2023)
    anns = query_retry(st["stock_param"], st["column"], start, end,
                       category=rt["category"], timeout=30)
    print(f"\n  {code} {st['name']} q3 2023: 原始返回 {len(anns)} 条 (窗口 {start}~{end})")
    for a in anns[:12]:
        print(f"    - [{a['date']}] {a['title']}")
    yr = [a for a in anns if "2023" in a["title"]]
    print(f"    含'2023'的: {len(yr)}")
    print(f"    filter_report → {filter_report(yr, 'q3') if yr else None}")
    print(f"    EXCLUDE_KEYWORDS={EXCLUDE_KEYWORDS} include_kw={rt['include_keyword']!r}")

print("\n" + "=" * 78)
print("[3] 三季报是否普遍以'三季度报告'而非'第三季度报告'命名（全市场小抽样）")
import random
random.seed(7)
sample = random.sample(u, 25)
pat = collections.Counter()
for st in sample:
    rt = REPORT_TYPES["q3"]
    start, end = rt["date_range"](2023)
    try:
        anns = query_retry(st["stock_param"], st["column"], start, end,
                           category=rt["category"], timeout=30)
    except Exception:
        pat["<error>"] += 1
        continue
    anns = [a for a in anns if "2023" in a["title"]]
    if not anns:
        pat["<none>"] += 1
        continue
    t = anns[0]["title"]
    if "第三季度" in t:
        pat["第三季度"] += 1
    elif "三季度" in t:
        pat["三季度(无第)"] += 1
        print(f"    !! {st['code']} {st['name']}: {t}")
    else:
        pat["其他"] += 1
        print(f"    ?? {st['code']} {st['name']}: {t}")
print("  分布:", dict(pat))

print("\n" + "=" * 78)
print("[4] 一季报命名抽样（同类风险）")
pat2 = collections.Counter()
for st in sample:
    rt = REPORT_TYPES["q1"]
    start, end = rt["date_range"](2023)
    try:
        anns = query_retry(st["stock_param"], st["column"], start, end,
                           category=rt["category"], timeout=30)
    except Exception:
        pat2["<error>"] += 1
        continue
    anns = [a for a in anns if "2023" in a["title"]]
    if not anns:
        pat2["<none>"] += 1
        continue
    t = anns[0]["title"]
    if "第一季度" in t:
        pat2["第一季度"] += 1
    elif "一季度" in t:
        pat2["一季度(无第)"] += 1
        print(f"    !! {st['code']} {st['name']}: {t}")
    else:
        pat2["其他"] += 1
        print(f"    ?? {st['code']} {st['name']}: {t}")
print("  分布:", dict(pat2))
