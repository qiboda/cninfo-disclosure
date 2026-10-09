#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_yjyg.py — 探业绩预告（及业绩快报）在巨潮的检索路径与赛季节奏。

背景：用户要求把「业绩预告」也下载下来。需要先确定：
  1. 业绩预告的 category 代码是什么（候选：category_yjyg_szsh / category_yjkb_szsh）；
  2. 全市场模式下 category 与 searchkey 哪条路更全；
  3. 标题形态有多少种（决定正本识别正则）；
  4. 赛季节奏 —— 2026 三季度预告是否已经放量，2025 同期是什么样。
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

OUT = os.path.join(_HERE, "probe_yjyg.out.txt")
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
    req = urllib.request.Request(CNINFO_QUERY_URL,
                                 data=urllib.parse.urlencode(p).encode("utf-8"),
                                 headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def d(ts):
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"


def walk(label, max_pages=25, show=6, **over):
    say("=" * 78)
    say(f"### {label}")
    say(f"    参数: {over}")
    total, has_more, days, samples = 0, False, Counter(), []
    last = 0
    for pn in range(1, max_pages + 1):
        try:
            j = page(pn, **over)
        except Exception as e:  # noqa: BLE001
            say(f"    !! 第 {pn} 页失败 {type(e).__name__}: {e}")
            break
        anns = j.get("announcements") or []
        has_more = bool(j.get("hasMore"))
        last = pn
        if not anns:
            break
        for a in anns:
            days[d(a.get("announcementTime"))] += 1
            total += 1
            if len(samples) < show:
                samples.append(f"{d(a.get('announcementTime'))}  {a.get('secCode')} "
                               f"{a.get('secName')} | "
                               f"{(a.get('announcementTitle') or '')[:66]}")
        if not has_more:
            break
    say(f"    合计 {total} 条   hasMore={has_more}   翻到第 {last} 页")
    say(f"    日期分布: {dict(sorted(days.items(), reverse=True)[:14])}")
    for s in samples:
        say(f"      {s}")
    return total


say("第一部分：确定 category 代码（候选逐个试，2026-10-01~2026-10-31）")
for cat in ("category_yjyg_szsh", "category_yjkb_szsh", "category_yjdbg_szsh",
            "category_yjyg_szsh_bj", "category_bndbg_szsh"):
    walk(f"category={cat}", category=cat, seDate="2026-10-01~2026-10-31",
         max_pages=6, show=3)

say()
say("第二部分：searchkey 路径（不加 category）")
for kw in ("业绩预告", "业绩预增", "业绩快报", "前三季度业绩预告", "第三季度业绩预告"):
    walk(f"searchkey={kw}", searchkey=kw, seDate="2026-10-01~2026-10-31",
         max_pages=6, show=3)

say()
say("第三部分：赛季节奏对照（不加日期，看最新）")
walk("searchkey=业绩预告，无日期（最新 N 条）", searchkey="业绩预告",
     max_pages=4, show=8)

say()
say("第四部分：2025 同期对照（去年同期预告节奏）")
walk("category=category_yjyg_szsh, 2025-10-01~2025-10-31",
     category="category_yjyg_szsh", seDate="2025-10-01~2025-10-31",
     max_pages=25, show=4)
walk("category=category_yjkb_szsh, 2025-10-01~2025-10-31",
     category="category_yjkb_szsh", seDate="2025-10-01~2025-10-31",
     max_pages=25, show=4)

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(buf) + "\n")
print(f"\n→ {OUT}")
