#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_q3verify3.py — 第三轮：确认数据源「新鲜度」

前面两轮已用三种互不相同的检索路径（category 倒序 / 全文检索标题 / searchkey=季度报告）
得到同一结论：2026 三季报目前只有 1 份。但还有一种可能没排除 —— **数据源本身是旧的**
（比如接口缓存、或我查的镜像不是活的）。

判别：不加任何过滤条件查最新公告（接口在 searchkey 与 category 都为空时退化为
「最新 30 条」），看最新一条是什么日期。
  · 若最新是 2026-10-10 前后 → 数据源是活的、就是「现在」，结论成立。
  · 若最新远早于今天   → 我查的东西是陈的，结论要推翻。

顺带探一下「预约披露时间表」接口（若可用，能直接告诉用户哪天会放量）。
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

from cninfo_client import (  # noqa: E402
    CNINFO_QUERY_URL,
    DEFAULT_TIMEOUT,
    QUERY_HEADERS,
)

OUT = os.path.join(_HERE, "probe_q3verify3.out.txt")
buf = []


def say(s=""):
    print(s)
    buf.append(s)


def post(**over):
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


def d(ts):
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M") if ts else "?"


say("=" * 78)
say("### L. 全市场最新 30 条公告（无任何过滤）—— 数据源新鲜度")
j = post()
anns = j.get("announcements") or []
say(f"    hasMore={j.get('hasMore')}  返回 {len(anns)} 条")
newest = None
for a in anns:
    ts = a.get("announcementTime") or 0
    line = (f"      {d(ts)}  {a.get('secCode')} {a.get('secName')} | "
            f"{(a.get('announcementTitle') or '')[:70]}")
    say(line)
    if newest is None:
        newest = ts
say()
say(f"    → 最新一条时间戳: {d(newest)}")

say()
say("=" * 78)
say("### M. 2026-10-10 单日全市场公告量（翻页直到 hasMore=False，含所有类型）")
total = 0
for pn in range(1, 201):
    j = post(pageNum=pn, seDate="2026-10-10~2026-10-10")
    a = j.get("announcements") or []
    if not a:
        break
    total += len(a)
    if not j.get("hasMore"):
        break
say(f"    2026-10-10 全市场公告 {total} 条（翻到第 {pn} 页停止）")

say()
say("### M2. 2026-10-09 单日全市场公告量")
total9 = 0
for pn in range(1, 201):
    j = post(pageNum=pn, seDate="2026-10-09~2026-10-09")
    a = j.get("announcements") or []
    if not a:
        break
    total9 += len(a)
    if not j.get("hasMore"):
        break
say(f"    2026-10-09 全市场公告 {total9} 条")

say()
say("=" * 78)
say("### N. 2025-10-31 对照：单日全市场公告量（去年三季报高峰日）")
tot25 = 0
for pn in range(1, 301):
    j = post(pageNum=pn, seDate="2025-10-31~2025-10-31")
    a = j.get("announcements") or []
    if not a:
        break
    tot25 += len(a)
    if not j.get("hasMore"):
        break
say(f"    2025-10-31 全市场公告 {tot25} 条（翻到第 {pn} 页停止）")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(buf) + "\n")
print(f"\n→ {OUT}")
