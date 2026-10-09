#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_q3verify2.py — 第二轮核查：用「全文检索」独立复核 2026 三季报的数量。

第一轮（probe_q3verify.py）结论：category 查询按时间倒序，最新是 2026-10-10 沃华医药，
之后直接跳回 2026-08-29，中间没有任何 2026 三季报。

本轮换完全不同的检索路径，避免「同一个错误参数导致的相同错误结论」：
  G/H. 全文检索 `2026年第三季度报告` / `2026年三季度报告`，不加任何日期条件，
       翻完所有页 → 直接数标题里带 2026 三季报字样的公告有多少条。
  I.   完全不加 category/searchkey，只看 seDate=2026-10-05~2026-10-10 这 6 天
       全市场**所有**公告有多少条、里面有几条是季度报告 → 判断「那几天到底有没有
       在披露」。
  J.   seDate=2026-10-01~2026-10-31 + searchkey=季度报告，翻页计数。
  K.   对照 2025 同期：seDate=2025-10-01~2025-10-31 + searchkey=2026年... 不需要，
       改为 seDate=2025-10-01~2025-10-31 + 全文检索 `2025年第三季度报告` 翻页计数，
       验证「全文检索这条路本身是通的」。
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

from cninfo_client import (  # noqa: E402
    CNINFO_QUERY_URL,
    DEFAULT_TIMEOUT,
    QUERY_HEADERS,
)

OUT = os.path.join(_HERE, "probe_q3verify2.out.txt")
buf = []


def say(s=""):
    print(s)
    buf.append(s)


def page(page_num, **over):
    p = {
        "pageNum": str(page_num), "pageSize": "30", "column": "szse",
        "tabName": "fulltext", "plate": "", "stock": "", "searchkey": "",
        "secid": "", "category": "", "trade": "", "seach": "", "seDate": "",
        "isFuzzy": "true", "sortName": "", "sortOrder": "",
    }
    p.update({k: str(v) for k, v in over.items()})
    data = urllib.parse.urlencode(p).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data,
                                 headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def walk(label, max_pages=40, **over):
    """翻完所有页，返回 (条数, hasMore 是否仍为真, 日期分布, 样本标题)"""
    say("=" * 78)
    say(f"### {label}")
    say(f"    参数: {over}")
    total = 0
    has_more = False
    days = Counter()
    samples = []
    for pn in range(1, max_pages + 1):
        try:
            j = page(pn, **over)
        except Exception as e:  # noqa: BLE001
            say(f"    !! 第 {pn} 页失败 {type(e).__name__}: {e}")
            break
        anns = j.get("announcements") or []
        has_more = bool(j.get("hasMore"))
        if not anns:
            break
        for a in anns:
            ts = a.get("announcementTime") or 0
            d = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"
            days[d] += 1
            total += 1
            if len(samples) < 8:
                samples.append(f"{d}  {a.get('secCode')} {a.get('secName')} | "
                               f"{(a.get('announcementTitle') or '')[:64]}")
        if not has_more:
            break
    say(f"    合计 {total} 条   hasMore(末页)={has_more}   翻到第 {pn} 页")
    say(f"    日期分布(近 12 天): "
        f"{dict(sorted(days.items(), reverse=True)[:12])}")
    for s in samples:
        say(f"      {s}")
    return total, has_more, days


# --- G/H：全文检索 2026 三季报标题，不加日期，翻完所有页 ---
walk("G. 全文检索「2026年第三季度报告」，无 category 无 seDate",
     searchkey="2026年第三季度报告")
walk("H. 全文检索「2026年三季度报告」，无 category 无 seDate",
     searchkey="2026年三季度报告")
walk("H2. 全文检索「2026三季报」，无 category 无 seDate",
     searchkey="2026三季报")

# --- K：对照组，验证全文检索这条路本身通不通（2025 季） ---
walk("K. 对照：全文检索「2025年第三季度报告」，无 category 无 seDate",
     searchkey="2025年第三季度报告", max_pages=12)

# --- I：那几天全市场到底在披露什么 ---
walk("I. 无 category 无 searchkey，seDate=2026-10-05~2026-10-10（全市场所有公告）",
     seDate="2026-10-05~2026-10-10", max_pages=12)

# --- J：十月窗口内的所有「季度报告」 ---
walk("J. searchkey=季度报告，seDate=2026-10-01~2026-10-31",
     searchkey="季度报告", seDate="2026-10-01~2026-10-31")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(buf) + "\n")
print(f"\n→ {OUT}")
