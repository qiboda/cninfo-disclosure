#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 category_yjygjxz_szsh（业绩预告）是否真过滤、以及覆盖度。

对照：
  A) category=category_yjygjxz_szsh, searchkey=""   —— 网页「业绩预告」筛选
  B) category="", searchkey="业绩" + YJYG_TITLE_RE  —— 现在脚本走的宽词+正则
  C) category="", searchkey="业绩快报"              —— 业绩快报是否有 category 归属
问题：
  1) A 是不是真的过滤（不返回全市场噪声）？
  2) A ⊇ B 吗（category 会不会漏掉 regex 能抓到的）？
  3) 业绩快报在不在 A 里？
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))
from cninfo_client import CNINFO_QUERY_URL, QUERY_HEADERS  # noqa: E402

YJYG_TITLE_RE = re.compile(r"业绩\s*(预告|预增|预盈|预减|预亏|预平)")
YJKB_TITLE_RE = re.compile(r"业绩\s*快报")


def fetch(category, searchkey, se_date, max_pages=200):
    out, page = [], 1
    total = None
    capped = False
    while page <= max_pages:
        params = {
            "pageNum": str(page), "pageSize": "30", "column": "szse",
            "tabName": "fulltext", "plate": "", "stock": "", "searchkey": searchkey,
            "secid": "", "category": category, "trade": "", "seach": "",
            "seDate": se_date, "isFuzzy": "true", "sortName": "", "sortOrder": "",
        }
        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(CNINFO_QUERY_URL, data=data,
                                     headers=QUERY_HEADERS, method="POST")
        with urllib.request.urlopen(req, timeout=25) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        if total is None:
            total = r.get("totalAnnouncement") or r.get("totalRecordNum") or 0
        anns = r.get("announcements") or []
        if not anns:
            break
        for a in anns:
            out.append({
                "id": a.get("announcementId"),
                "title": (a.get("announcementTitle") or "").strip(),
                "code": (a.get("secCode") or "").strip(),
                "name": (a.get("secName") or "").strip(),
            })
        if not r.get("hasMore"):
            break
        page += 1
    else:
        capped = True
    return total, out, capped


def report(label, se_date):
    print(f"\n{'=' * 78}\n### {label}   seDate={se_date}\n{'=' * 78}")

    ta, a, cap_a = fetch("category_yjygjxz_szsh", "", se_date)
    print(f"A) category_yjygjxz_szsh        totalAnnouncement={ta:<6} 取回={len(a):<5} capped={cap_a}")

    tb, b, cap_b = fetch("", "业绩", se_date)
    b_hit = [x for x in b if YJYG_TITLE_RE.search(x["title"])]
    b_kb = [x for x in b if YJKB_TITLE_RE.search(x["title"])]
    print(f"B) searchkey=业绩                totalAnnouncement={tb:<6} 取回={len(b):<5} capped={cap_b}")
    print(f"   └ regex 业绩预告族命中={len(b_hit)}   业绩快报命中={len(b_kb)}")

    ids_a = {x["id"] for x in a}
    ids_b = {x["id"] for x in b_hit}
    print(f"\n   A∩B = {len(ids_a & ids_b)}    B∖A（category 漏掉的）= {len(ids_b - ids_a)}"
          f"    A∖B（category 多给的）= {len(ids_a - ids_b)}")

    extra = [x for x in b_hit if x["id"] not in ids_a]
    if extra:
        print("\n   --- category 漏掉、但 regex 命中的（前 20）---")
        for x in extra[:20]:
            print(f"     {x['code']} {x['name']} | {x['title'][:64]}")

    only_a = [x for x in a if x["id"] not in ids_b]
    if only_a:
        print(f"\n   --- category 有、regex 未命中的（前 25 / 共 {len(only_a)}）---")
        for x in only_a[:25]:
            print(f"     {x['code']} {x['name']} | {x['title'][:64]}")

    if a:
        print("\n   --- A 的前 8 条样本 ---")
        for x in a[:8]:
            print(f"     {x['code']} {x['name']} | {x['title'][:64]}")

    tc, c, _ = fetch("", "业绩快报", se_date)
    c_ids = {x["id"] for x in c}
    print(f"\nC) searchkey=业绩快报             totalAnnouncement={tc:<6} 取回={len(c)}")
    print(f"   其中也在 A(category 业绩预告) 里的 = {len(c_ids & ids_a)}")
    for x in c[:6]:
        print(f"     {x['code']} {x['name']} | {x['title'][:64]}")

    return ids_a, ids_b


if __name__ == "__main__":
    report("2025 年 10 月（去年三季报预告季，作完整季对照）", "2025-10-01~2025-10-31")
    report("2026-10-01 ~ 2026-10-11（本赛季至今）", "2026-10-01~2026-10-11")
