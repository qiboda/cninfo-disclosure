#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 2：找出巨潮 API 正确的日期/分页参数，并验证按 stock 精确检索。"""
import json
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
QH = {
    "User-Agent": UA,
    "Referer": "http://www.cninfo.com.cn/new/disclosure/stock",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"


def q(**kw):
    payload = {
        "pageNum": "1", "pageSize": "30", "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": "", "searchkey": "", "secid": "", "category": "",
        "trade": "", "seach": "", "startDate": "", "endDate": "",
        "isFuzzy": "true", "sortName": "", "sortOrder": "",
    }
    payload.update({k: str(v) for k, v in kw.items()})
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=data, headers=QH, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def titles(res, n=6):
    return [(a.get("announcementTitle"), a.get("adjunctUrl")) for a in (res.get("announcements") or [])[:n]]


print("[A] seDate 参数（cninfo 新版真实参数名）")
res = q(column="sse", stock="600519,gssh0600519", category="category_ndbg_szsh",
        seDate="2023-01-01~2023-06-30")
print(f"  total={res.get('totalAnnouncement')}")
for t in titles(res):
    print("   -", t)

print("\n[B] 对照：seDate 无效/空 时")
res = q(column="sse", stock="600519,gssh0600519", category="category_ndbg_szsh")
print(f"  total={res.get('totalAnnouncement')}")
for t in titles(res, 3):
    print("   -", t)

print("\n[C] seDate + 全部页 (pageSize=100, 翻页)")
allrows = []
for p in range(1, 4):
    res = q(column="sse", stock="600519,gssh0600519", category="category_ndbg_szsh",
            seDate="2018-01-01~2030-12-31", pageSize=100, pageNum=p)
    rows = res.get("announcements") or []
    print(f"  page{p}: total={res.get('totalAnnouncement')} got={len(rows)} hasMore={res.get('hasMore')}")
    allrows.extend(rows)
    if not res.get("hasMore"):
        break
print(f"  合计={len(allrows)}")
for a in allrows:
    print("   -", a.get("announcementTitle"), "|", a.get("announcementTime"))

print("\n[D] 按股票代码 searchkey 是否可靠（对比 stock 参数）")
for code in ["000001", "600519", "300750", "920000"]:
    col = "sse" if code[0] == "6" else ("bj" if code[0] in "489" else "szse")
    res = q(column=col, searchkey=f"{code} 年度报告", category="category_ndbg_szsh",
            seDate="2023-01-01~2023-06-30", pageSize=5)
    print(f"  {code} col={col}: total={res.get('totalAnnouncement')} "
          f"first={[a.get('announcementTitle') for a in (res.get('announcements') or [])[:2]]}")

print("\n[E] seDate 对按代码 searchkey 是否生效")
res = q(column="sse", searchkey="600519 年度报告", category="category_ndbg_szsh",
        seDate="2023-01-01~2023-06-30", pageSize=10)
print(f"  total={res.get('totalAnnouncement')}")
for t in titles(res, 5):
    print("   -", t)

print("\n[F] 不带 category、完整 seDate 的招股书检索（stock 精确）")
res = q(column="sse", stock="603195,gssh0603195", searchkey="招股说明书",
        seDate="1990-01-01~2099-12-31", pageSize=50)
print(f"  total={res.get('totalAnnouncement')}")
for t in titles(res, 5):
    print("   -", t)

print("\n[G] 美股/其他 column 探测：column=bj 是否被接受")
res = q(column="bj", stock="920000,gfbj0832000", category="category_ndbg_szsh",
        seDate="2024-01-01~2026-12-31", pageSize=20)
print(f"  total={res.get('totalAnnouncement')}")
for t in titles(res, 4):
    print("   -", t)
