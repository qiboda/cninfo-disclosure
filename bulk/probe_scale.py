#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 4：量化两种口径的规模差 —— (a) 三季报口径 (b) 2026Q3 期间披露口径。"""
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")
from cninfo_client import CNINFO_QUERY_URL, QUERY_HEADERS  # noqa: E402

OUT = open(r"C:\Users\iq112\codes\cninfo-disclosure\bulk\probe_scale.out.txt",
           "w", encoding="utf-8")


def page(category, searchkey, se_date, page_num, page_size=30):
    data = urllib.parse.urlencode({
        "pageNum": str(page_num), "pageSize": str(page_size), "column": "szse",
        "tabName": "fulltext", "plate": "", "stock": "", "searchkey": searchkey,
        "secid": "", "category": category, "trade": "", "seach": "",
        "seDate": se_date, "isFuzzy": "true", "sortName": "", "sortOrder": "",
    }).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data, headers=QUERY_HEADERS,
                                 method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def count(label, category, searchkey, se_date, max_pages=120):
    seen = []
    p = 0
    for p in range(1, max_pages + 1):
        r = page(category, searchkey, se_date, p)
        anns = r.get("announcements") or []
        if not anns:
            break
        for a in anns:
            ts = a.get("announcementTime", 0)
            d = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"
            seen.append((d, a.get("stockCode", ""), a.get("announcementTitle", "")))
        if not r.get("hasMore"):
            break
    more = " (CAPPED, 还有更多)" if p >= max_pages else ""
    uniq = len(set(x[1] for x in seen))
    print(f"\n=== {label}\n     cat={category!r} key={searchkey!r} seDate={se_date}", file=OUT)
    print(f"     announcements={len(seen)} 涉及股票数={uniq} pages={p}{more}", file=OUT)
    print(f"     by date: {dict(sorted(Counter(x[0] for x in seen).items()))}", file=OUT)
    OUT.flush()


if __name__ == "__main__":
    count("口径a 三季报 2026 全年", "category_sjdbg_szsh", "", "2026-09-01~2026-12-31")
    count("口径b 2026Q3期间 半年报(7-9月)", "", "半年度报告", "2026-07-01~2026-10-09")
    count("口径b 2026Q3期间 招股说明书(7-9月)", "", "招股说明书", "2026-07-01~2026-10-09")
    count("参考 三季报 2025 全季", "category_sjdbg_szsh", "", "2025-10-01~2025-10-31")
    OUT.close()
    print("done")
