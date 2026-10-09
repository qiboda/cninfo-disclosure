#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按年统计 `category_yjygjxz_szsh`（业绩预告及修正，含业绩快报）的规模。

只读第一页的 totalAnnouncement，不翻页 —— 用来在跑历史回填前估算工作量。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from fetch_by_date import _post, YJYG_CATEGORY  # noqa: E402

YEARS = (2022, 2023, 2024, 2025, 2026)
TOTAL = 0
print("category_yjygjxz_szsh 年度规模（业绩预告 + 业绩快报）")
for y in YEARS:
    end = "2026-10-11" if y == 2026 else f"{y}-12-31"
    r = _post({
        "pageNum": "1", "pageSize": "30", "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": "", "searchkey": "", "secid": "",
        "category": YJYG_CATEGORY, "trade": "", "seach": "",
        "seDate": f"{y}-01-01~{end}", "isFuzzy": "true",
        "sortName": "", "sortOrder": "",
    }, 30)
    n = r.get("totalAnnouncement") or 0
    TOTAL += n
    print(f"  {y}-01-01 ~ {end} : {n:>6} 条")
print(f"\n合计 {TOTAL} 条，约 {TOTAL / 30:.0f} 页（每页 30）；"
      f"按平均 200 KB/份估算约 {TOTAL * 200 / 1024 / 1024:.2f} GB")
