#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""巨潮 API 行为探针：验证批量下载所需的接口行为。"""
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")

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


def show(label, res, n=3):
    anns = res.get("announcements") or []
    print(f"\n### {label}")
    print(f"  totalAnnouncement={res.get('totalAnnouncement')} returned={len(anns)} "
          f"hasMore={res.get('hasMore')}")
    for a in anns[:n]:
        print(f"   - {a.get('announcementTitle')} | {a.get('adjunctUrl')}")
    return anns


print("=" * 70)
print("[1] 股票清单 szse_stock.json")
req = urllib.request.Request("http://www.cninfo.com.cn/new/data/szse_stock.json",
                             headers={"User-Agent": UA, "Referer": "http://www.cninfo.com.cn/"})
with urllib.request.urlopen(req, timeout=30) as r:
    raw = r.read()
stock_list = json.loads(raw.decode("utf-8"))["stockList"]
print(f"  total={len(stock_list)}")
print(f"  sample={stock_list[:2]}")
codes = [s["code"] for s in stock_list]

import collections
pref = collections.Counter(c[:3] for c in codes)


def bucket(c):
    if c[0] == "6":
        return "SSE(6xx)"
    if c[:3] in ("000", "001", "002", "003"):
        return "SZSE-board(00x)"
    if c[:3] in ("300", "301", "302"):
        return "ChiNext(30x)"
    if c[:3] in ("900", "200", "201"):
        return "B-share"
    return "BSE/other"


b = collections.Counter(bucket(c) for c in codes)
print("  分桶:", dict(b))

print("\n" + "=" * 70)
print("[2] 按 6 位代码 + searchkey 检索（tool 当前用法）")
res = q(column="sse", searchkey="600519 年度报告", category="category_ndbg_szsh",
        startDate="2023-01-01", endDate="2023-06-30")
show("600519 贵州茅台 2022年报 (searchkey=代码)", res)

print("\n" + "=" * 70)
print("[3] 按 6 位代码 + searchkey（公司名）")
res = q(column="sse", searchkey="贵州茅台 年度报告", category="category_ndbg_szsh",
        startDate="2023-01-01", endDate="2023-06-30")
show("600519 贵州茅台 2022年报 (searchkey=名称)", res)

print("\n" + "=" * 70)
print("[4] 精确 stock 参数 (code,orgId)")
org = next((s["orgId"] for s in stock_list if s["code"] == "600519"), None)
print(f"  orgId(600519)={org}")
res = q(column="sse", stock=f"600519,{org}", searchkey="", category="category_ndbg_szsh",
        startDate="2023-01-01", endDate="2023-06-30")
show("精确 stock 参数", res)

print("\n" + "=" * 70)
print("[5] 北交所 column=bj")
bj = next((s for s in stock_list if s["code"].startswith("920")), None)
print(f"  bj sample={bj}")
if bj:
    res = q(column="bj", stock=f"{bj['code']},{bj['orgId']}", searchkey="",
            category="category_ndbg_szsh", startDate="2024-01-01", endDate="2026-12-31")
    show(f"北交所 {bj['code']} 年报 (column=bj)", res)

print("\n" + "=" * 70)
print("[6] 分页上限探测 pageSize=100")
res = q(column="szse", searchkey="", category="category_ndbg_szsh",
        startDate="2025-01-01", endDate="2025-06-30", pageSize=100)
print(f"  totalAnnouncement={res.get('totalAnnouncement')} returned={len(res.get('announcements') or [])}")

print("\n" + "=" * 70)
print("[7] 单只股票代码搜索是否稳健：000001 年报")
res = q(column="szse", searchkey="000001 年度报告", category="category_ndbg_szsh",
        startDate="2024-01-01", endDate="2024-06-30")
show("000001 平安银行 2023年报", res, 5)

print("\n" + "=" * 70)
print("[8] 不带 category、纯 searchkey（招股书用法）")
res = q(column="sse", searchkey="603195 招股说明书", startDate="1990-01-01", endDate="2099-12-31")
show("603195 招股说明书", res, 5)
