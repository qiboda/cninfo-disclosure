#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试：招股说明书检索为何 0 命中。"""
import sys
import json
import urllib.parse
import urllib.request

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\bulk")
sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")

from bulk_cninfo import load_universe, query_retry, PROSPECTUS_FROM, PROSPECTUS_TO
from prospectus import filter_prospectus
from cninfo_client import QUERY_HEADERS, CNINFO_QUERY_URL

u = load_universe(r"D:\cninfo")
idx = {s["code"]: s for s in u}

print("=" * 78)
print("[1] 全市场：2023 年披露的招股说明书（不带 stock 参数，看文档是否真实存在）")


def raw(**kw):
    payload = {
        "pageNum": "1", "pageSize": "50", "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": "", "searchkey": "", "secid": "", "category": "",
        "trade": "", "seach": "", "seDate": "", "isFuzzy": "true",
        "sortName": "", "sortOrder": "",
    }
    payload.update({k: str(v) for k, v in kw.items()})
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data, headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


for col in ["szse", "sse", "bj"]:
    res = raw(column=col, searchkey="招股说明书", seDate="2023-01-01~2023-12-31", pageSize=50)
    anns = res.get("announcements") or []
    print(f"  column={col}: total={res.get('totalAnnouncement')} 返回={len(anns)}")
    for a in anns[:4]:
        print(f"     - {a.get('announcementTitle')} | secCode={a.get('secCode')} secName={a.get('secName')}")

print("\n" + "=" * 78)
print("[2] 逐只测试已知/疑似近期 IPO 公司的招股书检索")
tests = ["001336", "301509", "001308", "301026", "688578", "688312", "301192", "920000", "600519", "000601"]
for code in tests:
    st = idx.get(code)
    if not st:
        print(f"  {code}: 不在池中")
        continue
    try:
        anns = query_retry(st["stock_param"], st["column"], PROSPECTUS_FROM, PROSPECTUS_TO,
                           category="", timeout=40)
    except Exception as e:
        print(f"  {code} {st['name']}: 查询异常 {e}")
        continue
    zs = [a for a in anns if "招股说明书" in a["title"]]
    print(f"  {code} {st['name']} col={st['column']}: 窗口内公告 {len(anns)} 条，含'招股说明书' {len(zs)} 条")
    for a in zs[:3]:
        print(f"     - [{a['date']}] {a['title']}")
    print(f"     filter_prospectus → {bool(filter_prospectus(anns)) if anns else False}")

print("\n" + "=" * 78)
print("[3] 对同一只股票：searchkey 有/无 对照（001336）")
st = idx.get("001336")
if st:
    for sk in ["", "招股说明书", "001336 招股说明书"]:
        res = raw(column=st["column"], stock=st["stock_param"], searchkey=sk,
                  seDate=f"{PROSPECTUS_FROM}~{PROSPECTUS_TO}", pageSize=100)
        anns = res.get("announcements") or []
        zs = [a for a in anns if "招股说明书" in a.get("announcementTitle", "")]
        print(f"  searchkey={sk!r}: total={res.get('totalAnnouncement')} 返回={len(anns)} "
              f"含招股说明书={len(zs)}")
        for a in zs[:3]:
            print(f"     - {a.get('announcementTitle')}")

print("\n" + "=" * 78)
print("[4] 招股书是否不带 category 就能被 stock 参数命中：查 2022-2026 全时段")
for code in ["001336", "301509", "001308"]:
    st = idx.get(code)
    if not st:
        continue
    res = raw(column=st["column"], stock=st["stock_param"], searchkey="",
              seDate="2021-01-01~2026-12-31", pageSize=100)
    anns = res.get("announcements") or []
    print(f"  {code} {st['name']}: total={res.get('totalAnnouncement')} 返回={len(anns)}")
    for a in anns[:5]:
        print(f"     - [{a.get('announcementTime')}] {a.get('announcementTitle')}")
