#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断 2：未命中公司里，有多少是「退市空壳」（巨潮无任何现存公告）。

判据：不带 category、不带 searchkey 查询该股票 → 巨潮退化为「最新 30 条」模式；
返回 0 条即说明该代码当前无任何公告，属退市/长期停牌空壳，不应计入覆盖率分母。
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from bulk_cninfo import load_universe, query_retry  # noqa: E402

root = r"C:\Users\iq112\Documents\cninfo"
universe = load_universe(root)

latest = {}
with open(os.path.join(root, "_state", "done.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            r = json.loads(line)
            latest[r["key"]] = r

# 收集所有未命中的 (code) —— 任一类型/年份未命中即计入
missing_codes = set()
for s in universe:
    for rtype, years in (("annual", [2022, 2023, 2024, 2025]),
                         ("semi", [2022, 2023, 2024, 2025, 2026]),
                         ("q1", [2022, 2023, 2024, 2025, 2026]),
                         ("q3", [2022, 2023, 2024, 2025, 2026])):
        for y in years:
            rec = latest.get(f"{s['code']}|{rtype}|{y}")
            if not (rec and rec["status"] == "ok"):
                missing_codes.add(s["code"])
                break

all_codes = [s["code"] for s in universe]
by_code = {s["code"]: s for s in universe}
print(f"全市场 {len(all_codes)} 只；至少有一项未命中的 {len(missing_codes)} 只")

random.seed(int(os.environ.get("SEED", "11")))
sample = random.sample(sorted(missing_codes), min(120, len(missing_codes)))

dead, alive = [], []
for code in sample:
    s = by_code[code]
    try:
        anns = query_retry(s["stock_param"], s["column"], "1990-01-01", "2099-12-31",
                           category="", searchkey="", timeout=40, page_size=30, max_pages=1)
    except Exception:  # noqa: BLE001
        continue
    (dead if not anns else alive).append((code, s["name"]))

print(f"\n抽样 {len(sample)} 只未命中公司：")
print(f"  【无任何公告 = 退市/空壳】{len(dead)} 只，占 {len(dead)/len(sample)*100:.1f}%")
print(f"  【仍有公告 = 真·漏档嫌疑】{len(alive)} 只")
for code, name in alive[:40]:
    print(f"     - {code} {name}")
