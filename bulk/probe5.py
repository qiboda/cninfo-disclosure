#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：为什么中国石油这类老牌公司在 年报2025 上未命中？"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from bulk_cninfo import load_universe, query_retry  # noqa: E402
from reports import REPORT_TYPES, filter_report  # noqa: E402
from cninfo_client import query_announcements, QUERY_HEADERS, CNINFO_QUERY_URL  # noqa: E402

root = r"C:\Users\iq112\Documents\cninfo"
universe = load_universe(root)
idx = {s["code"]: s for s in universe}

codes = ["601857", "600050", "600958", "600754", "601107", "600616"]
for code in codes:
    s = idx.get(code)
    if not s:
        print(f"{code}: 不在池中")
        continue
    rt = REPORT_TYPES["annual"]
    start, end = rt["date_range"](2025)
    print("=" * 78)
    print(f"{code} {s['name']}  col={s['column']}  stock_param={s['stock_param']}")
    print(f"  窗口 {start}~{end}  category={rt['category']}")

    anns = query_retry(s["stock_param"], s["column"], start, end,
                       category=rt["category"], timeout=40)
    print(f"  [A] stock参数 + category → {len(anns)} 条")
    for a in anns[:6]:
        print(f"       - [{a['date']}] {a['title'][:60]}")

    yr = [a for a in anns if "2025" in a["title"]]
    print(f"      含'2025' {len(yr)} 条 → 正本 {bool(filter_report(yr, 'annual')) if yr else None}")

    # 对照：不带 category，看窗口内全部公告类别
    allanns = query_retry(s["stock_param"], s["column"], start, end, category="",
                          searchkey="年度报告", timeout=40)
    print(f"  [B] stock参数 + searchkey='年度报告'（无category）→ {len(allanns)} 条")
    for a in allanns[:8]:
        print(f"       - [{a['date']}] {a['title'][:60]}")

    # 对照：原工具的 searchkey 用法
    try:
        raw = query_announcements(f"{s['name']} 年度报告", s["column"], start, end,
                                  category=rt["category"], timeout=40)
        print(f"  [C] searchkey='{s['name']} 年度报告' + category → {len(raw)} 条")
        for a in raw[:5]:
            print(f"       - [{a['date']}] {a['title'][:60]}")
    except Exception as e:  # noqa: BLE001
        print(f"  [C] 异常 {e}")
