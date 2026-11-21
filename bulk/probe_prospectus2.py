#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 2：抽样估算「1990 起窗口」对缺失股票的实际产出率，并对比 searchkey 变体。

用法：
  python probe_prospectus2.py [root] [sample] [searchkey]
"""
import json
import os
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

from cninfo_client import query_by_stock  # noqa: E402
from prospectus import filter_prospectus  # noqa: E402

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"E:\cninfo"
SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 40
SEARCHKEY = sys.argv[3] if len(sys.argv) > 3 else "招股说明书"
FROM, TO = "1990-01-01", "2099-12-31"

with open(os.path.join(ROOT, "_state", "universe.json"), encoding="utf-8") as f:
    universe = json.load(f)

have = set()
pdir = os.path.join(ROOT, "prospectus")
for fn in os.listdir(pdir):
    if fn[:6].isdigit() and fn[6] == "_":
        have.add(fn[:6])

missing = [s for s in universe if s["code"] not in have]
random.seed(20261121)
random.shuffle(missing)
sample = missing[:SAMPLE]
print(f"searchkey={SEARCHKEY!r}  抽样 {len(sample)} / 缺失 {len(missing)}")

lock = threading.Lock()


def work(s):
    try:
        anns = query_by_stock(s["stock_param"], s["column"], FROM, TO,
                              category="", searchkey=SEARCHKEY,
                              page_size=30, max_pages=10)
    except Exception as e:  # noqa: BLE001
        return {"code": s["code"], "name": s["name"], "err": f"{type(e).__name__}: {e}"}
    tgt = filter_prospectus(anns) if anns else None
    return {"code": s["code"], "name": s["name"], "hits": len(anns),
            "pick": tgt["title"] if tgt else None,
            "date": tgt["date"] if tgt else None}


rows = []
with ThreadPoolExecutor(max_workers=8) as ex:
    for r in ex.map(work, sample):
        rows.append(r)

err = [r for r in rows if "err" in r]
zero = [r for r in rows if "hits" in r and r["hits"] == 0]
picked = [r for r in rows if r.get("pick")]

# 疑似假阳性：标题里没有「招股说明书」或形如「关于…的公告」
def suspicious(title):
    return ("招股说明书" not in title) or title.startswith("关于") or title.endswith("的公告")


susp = [r for r in picked if suspicious(r["pick"])]

print(f"  查询失败 {len(err)}")
print(f"  0 条命中 {len(zero)}")
print(f"  选出正本 {len(picked)}  →  产出率 {len(picked)}/{len(rows)} = {len(picked)/max(1,len(rows)):.0%}")
print(f"  其中疑似假阳性 {len(susp)}")
print()
print("--- 选中的样本 ---")
for r in picked[:25]:
    flag = " ⚠️" if suspicious(r["pick"]) else ""
    print(f"  {r['code']} {r['name']:<8} {r['date']}  {r['pick'][:78]}{flag}")
print()
print("--- 0 命中的样本（前 15）---")
for r in zero[:15]:
    print(f"  {r['code']} {r['name']}")
