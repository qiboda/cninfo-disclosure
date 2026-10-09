# -*- coding: utf-8 -*-
r"""查看 _growth\extract.json 的抽取完整性（配合 screen_growth.py 用）。

用法: python bulk\show_growth.py [yjyg|ipo|q3|all]
"""
import io
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

P = os.path.join(_HERE, "_growth", "extract.json")
recs = json.load(open(P, encoding="utf-8"))
want = sys.argv[1] if len(sys.argv) > 1 else "all"

FIELDS = ("periods", "profit_low", "profit_high", "profit_sign", "yoy", "yoy_range",
          "revenue_narr", "profit_narr", "reason", "main_rows", "main_biz", "fin_table")

for r in recs:
    if want != "all" and r["kind"] != want:
        continue
    got = [k for k in FIELDS if r.get(k)]
    miss = [k for k in FIELDS[:9] if not r.get(k)]
    print("%s %s %-8s %-6s 字%6d  有=%s" % (
        r["date"], r["kind"], r["code"], r["name"], r.get("chars", 0), ",".join(got)))
    if not got:
        print("     缺: %s" % ",".join(miss))
