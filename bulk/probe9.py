#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全市场检索 世运电路2022年年度报告 正本是否存在于巨潮。"""
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")
from cninfo_client import CNINFO_QUERY_URL, QUERY_HEADERS  # noqa: E402


def raw(**kw):
    payload = {
        "pageNum": "1", "pageSize": "30", "column": "sse", "tabName": "fulltext",
        "plate": "", "stock": "", "searchkey": "", "secid": "", "category": "",
        "trade": "", "seach": "", "seDate": "", "isFuzzy": "true",
        "sortName": "", "sortOrder": "",
    }
    payload.update({k: str(v) for k, v in kw.items()})
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data, headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


for sk in ["世运电路2022年年度报告", "世运电路 年度报告", "世运电路"]:
    res = raw(column="sse", searchkey=sk, seDate="2023-01-01~2023-12-31", pageSize=30)
    anns = res.get("announcements") or []
    print(f"searchkey={sk!r}: total={res.get('totalAnnouncement')} 返回={len(anns)}")
    for a in anns[:10]:
        print(f"   - {a.get('announcementTitle')} | {a.get('adjunctUrl')}")
    print()
