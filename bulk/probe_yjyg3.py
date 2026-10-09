#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_yjyg3.py — 用真实标题反推「业绩预告」的识别规则与赛季节奏。

已知：
  · category_yjyg_szsh / yjkb_szsh 等一律被静默忽略（无效代码）；
  · searchkey 路径有效，且 `searchkey=业绩` 在 2026-10 窗口的 85 条 =
    前一轮 10 个候选词（业绩预告/预增/预减/预亏/预盈/快报/修正/前三季度业绩/
    第三季度业绩）的完全并集 —— 说明「业绩」是覆盖词。
  · 响应里有 totalAnnouncement / totalRecordNum 可直接拿到**精确条数**，
    不必翻页。（之前读 total 字段得到 None 是读错了 key。）
本脚本据此：dump 真实标题 → 设计正则 → 量化赛季节奏。
"""

import json
import os
import re
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

OUT = os.path.join(_HERE, "probe_yjyg3.out.txt")
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
    req = urllib.request.Request(CNINFO_QUERY_URL,
                                 data=urllib.parse.urlencode(p).encode("utf-8"),
                                 headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_all(day, key="业绩", max_pages=60):
    out, seen = [], set()
    for pn in range(1, max_pages + 1):
        j = post(pageNum=pn, searchkey=key, seDate=f"{day}~{day}")
        aa = j.get("announcements") or []
        if not aa:
            break
        for a in aa:
            i = a.get("announcementId") or a.get("adjunctUrl")
            if i not in seen:
                seen.add(i)
                out.append(a)
        if not j.get("hasMore"):
            break
    return out


def count(day, key="业绩"):
    j = post(searchkey=key, seDate=f"{day}~{day}")
    return j.get("totalAnnouncement") or j.get("totalRecordNum") or 0


say("=" * 78)
say("### 1. 2026-10 窗口内 searchkey=业绩 的**全部标题**（用于设计正则）")
all26 = []
for day_n in range(1, 11):
    day = f"2026-10-{day_n:02d}"
    anns = fetch_all(day)
    all26.extend(anns)
say(f"    合计 {len(all26)} 条")
say()
for a in sorted(all26, key=lambda x: (x.get("announcementTime") or 0), reverse=True):
    d = datetime.fromtimestamp((a.get("announcementTime") or 0) / 1000).strftime("%m-%d")
    say(f"      {d}  {a.get('secCode')} {a.get('secName')} | {a.get('announcementTitle')}")

say()
say("=" * 78)
say("### 2. 候选正则对上面的标题分类")
PAT = re.compile(
    r"(业绩(预告|预增|预盈|预减|预亏|预平|快报|预告修正)|"
    r"(\d{4}\s*年\s*)?(前三季度|第三季度|三季度|1\s*[-~－]\s*9\s*月)"
    r"[^\n]{0,12}业绩(预告|预增|预盈|预减|预亏|快报))"
)
EXC = ["说明会", "业绩说明", "承诺", "完成情况", "问询", "监管", "督导",
       "核查意见", "法律意见", "董事会关于", "独立董事", "摘要"]
hit, miss = [], []
for a in all26:
    t = a.get("announcementTitle") or ""
    if PAT.search(t) and not any(e in t for e in EXC):
        hit.append(t)
    else:
        miss.append(t)
say(f"    正则命中 {len(hit)} 条 / 未命中 {len(miss)} 条")
say()
say("    ── 命中（这些才是业绩预告/快报正本）──")
for t in sorted(hit):
    say(f"      ✔ {t}")
say()
say("    ── 未命中（排除项，确认没有误杀）──")
for t in sorted(miss):
    say(f"      ✘ {t}")

say()
say("=" * 78)
say("### 3. 赛季节奏：searchkey=业绩 的每日条数（totalAnnouncement 精确计数）")
say("    2025 年（去年 Q3 预告季）:")
d25 = "2025-10-01"
series25 = []
for i in range(36):
    from datetime import date, timedelta
    day = (date(2025, 10, 1) + timedelta(days=i)).isoformat()
    if day > "2025-11-05":
        break
    c = count(day)
    if c:
        series25.append((day, c))
say("      " + "  ".join(f"{d[5:]}:{c}" for d, c in series25))
say()
say("    2026 年（今年 Q3 预告季）:")
series26 = []
for i in range(11):
    from datetime import date, timedelta
    day = (date(2026, 10, 1) + timedelta(days=i)).isoformat()
    c = count(day)
    if c:
        series26.append((day, c))
say("      " + "  ".join(f"{d[5:]}:{c}" for d, c in series26))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(buf) + "\n")
print(f"\n→ {OUT}")
