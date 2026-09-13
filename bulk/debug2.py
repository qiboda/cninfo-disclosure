#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证北交所新旧代码（430017 vs 920017）公告是否等价，以决定去重策略。"""
import sys
import collections

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\bulk")
sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")

from bulk_cninfo import load_universe, query_retry
from reports import REPORT_TYPES

u = load_universe(r"D:\cninfo")
idx = {s["code"]: s for s in u}

pairs = [("430017", "920017"), ("833874", "301192"), ("430047", "920047")]

for old, new in pairs:
    a, b = idx.get(old), idx.get(new)
    if not a or not b:
        print(f"\n{old} vs {new}: 有一条不在池中 (old={bool(a)}, new={bool(b)})")
        continue
    print(f"\n{'='*70}")
    print(f"{a['name']}: 旧码 {old}(col={a['column']}) vs 新码 {new}(col={b['column']})")
    sets = {}
    for label, s in (("old", a), ("new", b)):
        anns = query_retry(s["stock_param"], s["column"], "2022-01-01", "2099-12-31",
                           category="", timeout=40)
        sets[label] = {x["adjunct_url"] for x in anns}
        print(f"  {label} ({s['code']}): {len(anns)} 条公告")
        for x in anns[:4]:
            print(f"      - [{x['date']}] {x['title']}")
    inter = sets["old"] & sets["new"]
    print(f"  交集 {len(inter)} | 仅旧 {len(sets['old']-sets['new'])} | 仅新 {len(sets['new']-sets['old'])}")

print(f"\n{'='*70}")
print("旧码(4/8开头)中，简称在池内是否还有非旧码条目 —— 决定去重规则")
buckets = collections.defaultdict(list)
for s in u:
    buckets[s["name"]].append(s)
old_pref = []
for name, lst in buckets.items():
    if len(lst) < 2:
        continue
    olds = [s for s in lst if s["code"].startswith(("4", "8"))]
    news = [s for s in lst if not s["code"].startswith(("4", "8"))]
    if olds and news:
        old_pref.append((name, [s["code"] for s in olds], [s["code"] for s in news]))
print(f"  可去重的组数: {len(old_pref)}")
for row in old_pref[:10]:
    print("   ", row)

only_old = [n for n, l in buckets.items()
            if len(l) > 1 and all(s["code"].startswith(("4", "8")) for s in l)]
print(f"  同简称但都在旧码段的组数（不能简单去重）: {len(only_old)}")
for n in only_old[:10]:
    print("   ", n, [s["code"] for s in buckets[n]])
