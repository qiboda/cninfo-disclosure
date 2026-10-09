#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 `category_yjygjxz_szsh` 的结果里，有多少条**两个正则都没命中**。

category 是权威的（实测噪声≈0），但代码是先用正则分流 yjyg/yjkb 再落盘 ——
如果有标题两个正则都匹配不上，就会被静默丢弃。这里量化这个漏口，
并打印漏掉的标题，以便判断是「该放宽正则」还是「这些本来就该丢」。
"""
import os
import sys
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from fetch_by_date import (YJYG_CATEGORY, YJYG_TITLE_RE, YJKB_TITLE_RE,  # noqa: E402
                           scan_range)

WINDOWS = [
    ("2025-04 一季报预告轮", "2025-04-01", "2025-04-30"),
    ("2026-01 年报预告轮（最大一轮）", "2026-01-01", "2026-01-31"),
    ("2025-10 三季报预告轮", "2025-10-01", "2025-10-31"),
]

for label, a, b in WINDOWS:
    anns, capped = scan_range(YJYG_CATEGORY, "", date.fromisoformat(a),
                              date.fromisoformat(b), timeout=25, max_pages=250)
    yjyg = [x for x in anns if YJYG_TITLE_RE.search(x["title"])]
    yjkb = [x for x in anns if YJKB_TITLE_RE.search(x["title"])]
    miss = [x for x in anns if not YJYG_TITLE_RE.search(x["title"])
            and not YJKB_TITLE_RE.search(x["title"])]
    print(f"\n=== {label}  {a} ~ {b}   capped={capped}")
    print(f"    category 取回 {len(anns)} 条：预告正则 {len(yjyg)} / 快报正则 {len(yjkb)}"
          f" / **两个都没命中 {len(miss)}**")
    for x in miss[:40]:
        print(f"      {x['date']} {x['code']} {x['name']} | {x['title'][:78]}")
    if len(miss) > 40:
        print(f"      ...（还有 {len(miss) - 40} 条）")
