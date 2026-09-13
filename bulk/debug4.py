#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试：分页行为 + 招股书正确检索姿势 + 全市场招股书枚举。"""
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\bulk")
sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")

from bulk_cninfo import load_universe  # noqa: E402
from cninfo_client import CNINFO_QUERY_URL, QUERY_HEADERS  # noqa: E402
from prospectus import filter_prospectus  # noqa: E402

u = load_universe(r"D:\cninfo")
idx = {s["code"]: s for s in u}


def raw(**kw):
    payload = {
        "pageNum": "1", "pageSize": "30", "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": "", "searchkey": "", "secid": "", "category": "",
        "trade": "", "seach": "", "seDate": "", "isFuzzy": "true",
        "sortName": "", "sortOrder": "",
    }
    payload.update({k: str(v) for k, v in kw.items()})
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data, headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


print("=" * 78)
print("[1] 分页行为：pageSize 上限 & pageNum 是否生效（用「全市场年报 2025」）")
for ps in [30, 50, 100]:
    r = raw(column="szse", category="category_ndbg_szsh", seDate="2025-01-01~2025-06-30", pageSize=ps)
    print(f"  pageSize={ps}: total={r.get('totalAnnouncement')} 返回={len(r.get('announcements') or [])} "
          f"hasMore={r.get('hasMore')}")

for p in [1, 2, 3]:
    r = raw(column="szse", category="category_ndbg_szsh", seDate="2025-01-01~2025-06-30",
            pageSize=30, pageNum=p)
    anns = r.get("announcements") or []
    print(f"  pageNum={p}: 返回={len(anns)} hasMore={r.get('hasMore')} first={anns[0].get('announcementTitle')[:30] if anns else None}")

print("\n" + "=" * 78)
print("[2] 招股书正确姿势：stock 参数 + searchkey='招股说明书'（近期 IPO 公司）")
tests = ["688717", "301566", "301578", "001336", "301509", "001308", "301026",
         "688578", "688312", "301192", "920000", "600519"]
hit = 0
for code in tests:
    st = idx.get(code)
    if not st:
        print(f"  {code}: 不在池中")
        continue
    r = raw(column=st["column"], stock=st["stock_param"], searchkey="招股说明书",
            seDate="2022-01-01~2099-12-31", pageSize=30)
    anns = r.get("announcements") or []
    parsed = [{"title": a["announcementTitle"], "date": "", "pdf_url": a["adjunctUrl"],
               "adjunct_url": a["adjunctUrl"]} for a in anns]
    cand = [a for a in parsed if "招股说明书" in a["title"]]
    tgt = filter_prospectus(cand) if cand else None
    if tgt:
        hit += 1
    print(f"  {code} {st['name']:<8} total={r.get('totalAnnouncement')} 返回={len(anns)} "
          f"命中正本={bool(tgt)} {('| ' + tgt['title'][:34]) if tgt else ''}")
print(f"  → 命中 {hit}/{len(tests)}")

print("\n" + "=" * 78)
print("[3] 全市场招股书枚举：searchkey + seDate 2022-01-01~now，统计总量并翻页")
total_all = 0
for col in ["szse", "sse", "bj"]:
    r = raw(column=col, searchkey="招股说明书", seDate="2022-01-01~2026-09-13", pageSize=30)
    print(f"  column={col}: total={r.get('totalAnnouncement')} 返回={len(r.get('announcements') or [])} "
          f"hasMore={r.get('hasMore')}")
    total_all += r.get("totalAnnouncement") or 0
print(f"  三列合计 total（含重复，各列似返回同一全集）≈ {total_all}")
