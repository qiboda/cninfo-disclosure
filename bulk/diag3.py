#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断 3：对某个 (类型, 年份) 的未命中公司做三分类归因。

分类逻辑（以 annual 2025 为例，披露截止 2026-04-30）：
  A. 空壳/退市 —— 巨潮已无任何现存公告
  B. 当时尚未上市 —— 截止日之前无任何公告，但之后有
  C. 真·漏档 —— 截止日之前已有公告（说明当时在正常披露），却检索不到该报告
C 是唯一的真问题。
"""
import collections
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from bulk_cninfo import load_universe, query_retry  # noqa: E402
from reports import REPORT_TYPES  # noqa: E402

root = r"C:\Users\iq112\Documents\cninfo"
rtype = sys.argv[1] if len(sys.argv) > 1 else "annual"
year = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8

# 披露窗口起点：晚于该时点才出现首条公告 → 当时尚未上市，本就没有这份报告
_win_start, _win_end = REPORT_TYPES[rtype]["date_range"](year)
from datetime import date, timedelta  # noqa: E402
_today = date.today()
_recent_start = (_today - timedelta(days=120)).isoformat()
_recent_end = _today.isoformat()
_before_end = (date.fromisoformat(_win_start) - timedelta(days=1)).isoformat()

universe = load_universe(root)
latest = {}
with open(os.path.join(root, "_state", "done.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            r = json.loads(line)
            latest[r["key"]] = r

missing = [s for s in universe
           if not (latest.get(f"{s['code']}|{rtype}|{year}", {}).get("status") == "ok")]
print(f"== {rtype} {year}（披露截止 {_win_end}，窗口起点 {_win_start}）：未命中 {len(missing)} 家 ==")


def classify(s):
    try:
        recent = query_retry(s["stock_param"], s["column"], _recent_start, _recent_end,
                             category="", searchkey="", timeout=40, page_size=30, max_pages=1)
    except Exception:  # noqa: BLE001
        return ("<查询失败>", s)
    if not recent:
        return ("A_已退市或长期停牌", s)
    # 仍在市：再看披露窗口起点之前是否已有公告（判断当时是否已上市）
    try:
        before = query_retry(s["stock_param"], s["column"], "1990-01-01", _before_end,
                             category="", searchkey="", timeout=40, page_size=30, max_pages=1)
    except Exception:  # noqa: BLE001
        return ("<查询失败>", s)
    return ("C_在市且已上市但仍漏档" if before else "B_当时尚未上市", s)


buckets = collections.defaultdict(list)
with ThreadPoolExecutor(max_workers=workers) as pool:
    for kind, s in pool.map(classify, missing):
        buckets[kind].append(s)

total = len(missing)
print()
for kind in sorted(buckets):
    lst = buckets[kind]
    print(f"  {kind:<12} {len(lst):>5} 家  ({len(lst)/total*100:5.1f}%)")

for kind in sorted(buckets):
    if kind.startswith("C") or kind.startswith("<"):
        print(f"\n需要处理的【{kind}】明细：")
        for s in buckets[kind][:80]:
            print(f"   - {s['code']} {s['name']} (col={s['column']})")

out = os.path.join(root, "_state", f"diag_{rtype}_{year}.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({k: [s["code"] for s in v] for k, v in buckets.items()}, f,
              ensure_ascii=False, indent=1)
print(f"\n明细已写入 {out}")
