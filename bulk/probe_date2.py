#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 2：验证「全市场 + category」是否生效（用 2025 年三季报窗口做对照）。"""
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")
from cninfo_client import CNINFO_QUERY_URL, QUERY_HEADERS  # noqa: E402

OUT = open(r"C:\Users\iq112\codes\cninfo-disclosure\bulk\probe_date2.out.txt",
           "w", encoding="utf-8")


def page(category, searchkey, se_date, page_num, column="szse", page_size=30,
         plate="", trade=""):
    data = urllib.parse.urlencode({
        "pageNum": str(page_num), "pageSize": str(page_size), "column": column,
        "tabName": "fulltext", "plate": plate, "stock": "", "searchkey": searchkey,
        "secid": "", "category": category, "trade": trade, "seach": "",
        "seDate": se_date, "isFuzzy": "true", "sortName": "", "sortOrder": "",
    }).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data, headers=QUERY_HEADERS,
                                 method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def scan(label, category, searchkey, se_date, max_pages=80, **kw):
    seen = []
    p = 0
    for p in range(1, max_pages + 1):
        r = page(category, searchkey, se_date, p, **kw)
        anns = r.get("announcements") or []
        if not anns:
            break
        for a in anns:
            ts = a.get("announcementTime", 0)
            d = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"
            seen.append((d, a.get("stockCode", ""), a.get("secName", ""),
                         a.get("announcementTitle", ""), a.get("adjunctUrl", "")))
        if not r.get("hasMore"):
            break
    print(f"\n=== {label} | cat={category} key={searchkey} seDate={se_date} kw={kw}",
          file=OUT)
    print(f"total={len(seen)} pages={p} hasMore_last={r.get('hasMore')}", file=OUT)
    print("by date:", dict(sorted(Counter(x[0] for x in seen).items())), file=OUT)
    for row in seen[:6]:
        print("   ", row[0], row[1], row[2], "|", row[3][:70], file=OUT)
    OUT.flush()
    return seen


if __name__ == "__main__":
    W25 = "2025-10-01~2025-10-31"
    scan("A 三季报 category", "category_sjdbg_szsh", "", W25)
    scan("B 三季报 searchkey 三季度", "", "三季度", W25)
    scan("C 三季报 searchkey 第三季度报告", "", "第三季度报告", W25)
    scan("D 三季报 category + searchkey", "category_sjdbg_szsh", "三季度", W25)
    scan("E 2026 三季报 category 全年", "category_sjdbg_szsh", "", "2026-09-01~2026-12-31")
    OUT.close()
    print("done")
