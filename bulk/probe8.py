#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查证最后一个残留候选：603920 世运电路 年报2022。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from bulk_cninfo import load_universe, query_retry, pick_report_target  # noqa: E402
from reports import REPORT_TYPES  # noqa: E402

u = load_universe(r"C:\Users\iq112\Documents\cninfo")
idx = {x["code"]: x for x in u}

for code, rt_key, yr in [("603920", "annual", 2022), ("603920", "annual", 2023),
                         ("603920", "annual", 2024), ("603920", "annual", 2025)]:
    s = idx[code]
    rt = REPORT_TYPES[rt_key]
    lo, hi = rt["date_range"](yr)
    print("=" * 74)
    print(f"{code} {s['name']} {rt_key}{yr}  窗口 {lo}~{hi}")
    a = query_retry(s["stock_param"], s["column"], lo, hi, category=rt["category"], timeout=40)
    print(f"  [category 查询] {len(a)} 条")
    for x in a[:8]:
        print(f"     {x['date']} {x['title'][:64]}")
    t = pick_report_target(a, rt_key, yr)
    if t is None:
        b = query_retry(s["stock_param"], s["column"], lo, hi, category="",
                        searchkey=rt["search_key"], timeout=40)
        print(f"  [兜底 searchkey] {len(b)} 条")
        for x in b[:8]:
            print(f"     {x['date']} {x['title'][:64]}")
        seen = {x["adjunct_url"] for x in a}
        t = pick_report_target(list(a) + [x for x in b if x["adjunct_url"] not in seen], rt_key, yr)
    print(f"  → 正本: {t['title'] if t else '!! 未命中'}")
