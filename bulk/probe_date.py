#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：验证「全市场 + 日期区间」检索是否可行（不按股票，只按 category/searchkey + seDate）。

目的：为「按披露日期归档最近公告」的增量抓取找入口。
"""
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")
from cninfo_client import CNINFO_QUERY_URL, QUERY_HEADERS  # noqa: E402


def page(column, category, searchkey, se_date, page_num, page_size=30):
    data = urllib.parse.urlencode({
        "pageNum": str(page_num),
        "pageSize": str(page_size),
        "column": column,
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": searchkey,
        "secid": "",
        "category": category,
        "trade": "",
        "seach": "",
        "seDate": se_date,
        "isFuzzy": "true",
        "sortName": "",
        "sortOrder": "",
    }).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data, headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def scan(label, column, category, searchkey, se_date, max_pages=60):
    seen = []
    for p in range(1, max_pages + 1):
        r = page(column, category, searchkey, se_date, p)
        anns = r.get("announcements") or []
        if not anns:
            break
        for a in anns:
            ts = a.get("announcementTime", 0)
            d = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"
            seen.append((d, a.get("announcementTitle", ""), a.get("adjunctUrl", ""),
                         a.get("secName", ""), a.get("stockCode", "")))
        if not r.get("hasMore"):
            break
    print(f"\n=== {label} | col={column} cat={category} key={searchkey} seDate={se_date}")
    print(f"total={len(seen)}  pages_used={p}")
    print("by date:", dict(sorted(Counter(x[0] for x in seen).items())))
    for row in seen[:5]:
        print("   ", row[0], row[4], row[3], "|", row[1][:60])
    return seen


if __name__ == "__main__":
    WIN = "2026-09-01~2026-10-09"
    for col in ("szse", "sse", "bj"):
        scan("三季报", col, "category_sjdbg_szsh", "", WIN)
    for col in ("szse", "sse", "bj"):
        scan("招股书", col, "", "招股说明书", "2026-08-01~2026-10-09")
