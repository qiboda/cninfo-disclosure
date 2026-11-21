#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：验证「1990-01-01 起」的招股书检索能否覆盖老公司，并检查 filter_prospectus 的挑选质量。

用法：python probe_prospectus.py [root]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

from cninfo_client import query_by_stock, detect_column  # noqa: E402
from prospectus import filter_prospectus, detect_board  # noqa: E402

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"E:\cninfo"
FROM, TO = "1990-01-01", "2099-12-31"

TARGETS = [
    ("000001", "平安银行", "1991 深发展"),
    ("000002", "万科A", "1991"),
    ("600519", "贵州茅台", "2001"),
    ("600036", "招商银行", "2002"),
    ("601398", "工商银行", "2006"),
    ("688981", "中芯国际", "2020 科创板"),
    ("301718", "通则康威", "2026 创业板"),
    ("000301", "东方盛虹", "现有的假招股书样本"),
]

with open(os.path.join(ROOT, "_state", "universe.json"), encoding="utf-8") as f:
    uni = {s["code"]: s for s in json.load(f)}

for code, name, note in TARGETS:
    s = uni.get(code)
    print("=" * 78)
    if not s:
        print(f"{code} {name} （{note}）→ 不在 universe")
        continue
    print(f"{code} {name} （{note}） stock_param={s['stock_param']} column={s['column']}")
    try:
        anns = query_by_stock(s["stock_param"], s["column"], FROM, TO,
                              category="", searchkey="招股说明书",
                              page_size=30, max_pages=10)
    except Exception as e:  # noqa: BLE001
        print(f"  查询失败：{type(e).__name__}: {e}")
        continue
    print(f"  命中 {len(anns)} 条")
    for a in anns[:10]:
        print(f"    {a['date']}  {a['title'][:90]}")
    tgt = filter_prospectus(anns)
    if tgt:
        print(f"  → 选中：{tgt['date']} | {tgt['title'][:100]}")
        print(f"    板块={detect_board(tgt['title'])}  {tgt['pdf_url']}")
    else:
        print("  → 未选出正本")
