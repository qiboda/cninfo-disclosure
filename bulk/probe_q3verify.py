#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_q3verify.py — 核查「2026 三季报是否真的只有 1 份」

怀疑点：我此前用 seDate=2026-09-01~2026-12-31 + category=category_sjdbg_szsh
只查到 1 条。可能的原因：
  (a) 2026 三季报季真的没开始；
  (b) seDate 对 category 查询不生效 / 语义不是「披露日期」；
  (c) category_sjdbg_szsh 在 2026 已经改了名，查不到东西。

判别办法：**不加任何日期条件**，直接看该 category 按时间倒序返回的「最新 N 条」
是什么。若最新的是 2026 年三季报且成批出现，则说明是 (b)/(c) 而非 (a)。
"""

import json
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402

from cninfo_client import (  # noqa: E402
    CNINFO_PDF_BASE,
    CNINFO_QUERY_URL,
    DEFAULT_TIMEOUT,
    QUERY_HEADERS,
)

OUT = os.path.join(_HERE, "probe_q3verify.out.txt")
buf = []


def say(s=""):
    print(s)
    buf.append(s)


def raw(**over):
    p = {
        "pageNum": "1", "pageSize": "30", "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": "", "searchkey": "", "secid": "", "category": "",
        "trade": "", "seach": "", "seDate": "", "isFuzzy": "true",
        "sortName": "", "sortOrder": "",
    }
    p.update({k: str(v) for k, v in over.items()})
    data = urllib.parse.urlencode(p).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data,
                                 headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def show(label, **over):
    say("=" * 78)
    say(f"### {label}")
    say(f"    参数: {over}")
    try:
        j = raw(**over)
    except Exception as e:  # noqa: BLE001
        say(f"    !! 请求失败 {type(e).__name__}: {e}")
        return
    anns = j.get("announcements") or []
    say(f"    total={j.get('total')}  hasMore={j.get('hasMore')}  "
        f"返回条数={len(anns)}")
    days = Counter()
    for a in anns:
        ts = a.get("announcementTime") or 0
        from datetime import datetime
        d = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"
        days[d] += 1
    say(f"    日期分布: {dict(sorted(days.items(), reverse=True))}")
    for a in anns[:12]:
        ts = a.get("announcementTime") or 0
        from datetime import datetime
        d = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"
        say(f"      {d}  {a.get('secCode')} {a.get('secName')} | "
            f"{(a.get('announcementTitle') or '')[:60]}")


say(f"查询端点: {CNINFO_QUERY_URL}")
say()

# 1) 无日期条件 —— 看该 category 最新返回什么
show("A. category_sjdbg_szsh，无 seDate（最新 N 条）",
     category="category_sjdbg_szsh")
show("B. category_sjdbg_szsh，无 seDate，显式按时间倒序",
     category="category_sjdbg_szsh", sortName="announcementTime", sortOrder="desc")
show("C. 无 category，searchkey=第三季度报告，无 seDate",
     searchkey="第三季度报告")
show("D. category_sjdbg_szsh，seDate=2026-01-01~2026-12-31",
     category="category_sjdbg_szsh", seDate="2026-01-01~2026-12-31")
show("E. category_sjdbg_szsh，seDate=2026-10-01~2026-10-31",
     category="category_sjdbg_szsh", seDate="2026-10-01~2026-10-31")
show("F. searchkey=第三季度报告，seDate=2026-10-01~2026-10-31",
     searchkey="第三季度报告", seDate="2026-10-01~2026-10-31")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(buf) + "\n")
print(f"\n→ {OUT}")
