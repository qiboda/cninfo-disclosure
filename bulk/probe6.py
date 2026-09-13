#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证修复：此前未命中的老牌公司能否捞到年报正本。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from bulk_cninfo import load_universe, query_retry, pick_report_target, DEFAULT_YEARS  # noqa: E402
from reports import REPORT_TYPES  # noqa: E402

root = r"C:\Users\iq112\Documents\cninfo"
universe = load_universe(root)
idx = {s["code"]: s for s in universe}

cases = [("601857", "annual", 2025), ("600050", "annual", 2025), ("600958", "annual", 2025),
         ("600754", "annual", 2025), ("601107", "annual", 2025), ("600616", "annual", 2025),
         ("600519", "annual", 2025), ("000001", "annual", 2025), ("601398", "annual", 2025)]

for code, rtype, year in cases:
    s = idx.get(code)
    if not s:
        print(f"{code}: 不在池中")
        continue
    rt = REPORT_TYPES[rtype]
    start, end = rt["date_range"](year)
    anns = query_retry(s["stock_param"], s["column"], start, end,
                       category=rt["category"], timeout=40)
    t1 = pick_report_target(anns, rtype, year)
    src = "主查询"
    if t1 is None:
        more = query_retry(s["stock_param"], s["column"], start, end,
                           category="", searchkey=rt["search_key"], timeout=40)
        seen = {a["adjunct_url"] for a in anns}
        merged = list(anns) + [a for a in more if a["adjunct_url"] not in seen]
        t1 = pick_report_target(merged, rtype, year)
        src = f"兜底查询(+{len(more)}条)"
    print(f"{code} {s['name']:<10} [{src}] → {t1['title'] if t1 else '!! 仍未命中'}")
