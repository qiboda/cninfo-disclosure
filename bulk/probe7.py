#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 q1/q3 标题模式修复。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from bulk_cninfo import load_universe, query_retry, pick_report_target  # noqa: E402
from reports import REPORT_TYPES  # noqa: E402

u = load_universe(r"C:\Users\iq112\Documents\cninfo")
idx = {x["code"]: x for x in u}

cases = [("603012", "q1", 2022), ("603816", "q1", 2022), ("300750", "q1", 2023),
         ("600519", "q1", 2023), ("000001", "q3", 2023), ("002284", "q3", 2023),
         ("000601", "q3", 2023), ("600519", "q3", 2022), ("000001", "semi", 2023)]

for code, rt_key, yr in cases:
    s = idx[code]
    rt = REPORT_TYPES[rt_key]
    lo, hi = rt["date_range"](yr)
    a = query_retry(s["stock_param"], s["column"], lo, hi, category=rt["category"], timeout=40)
    t = pick_report_target(a, rt_key, yr)
    src = "主查询"
    if t is None:
        b = query_retry(s["stock_param"], s["column"], lo, hi, category="",
                        searchkey=rt["search_key"], timeout=40)
        seen = {x["adjunct_url"] for x in a}
        t = pick_report_target(list(a) + [x for x in b if x["adjunct_url"] not in seen], rt_key, yr)
        src = "兜底"
    title = t["title"] if t else "!! 仍未命中"
    print(f"{code} {s['name']:<10} {rt_key} {yr} [{src}] -> {title}")
