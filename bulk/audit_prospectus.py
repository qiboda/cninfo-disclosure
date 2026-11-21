#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计：检查现有 prospectus 清单里的标题是否真的是「首发招股说明书」。

只读 manifest.csv，不发网络请求。

用法：python audit_prospectus.py [root]
"""
import collections
import csv
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"E:\cninfo"
MANIFEST = os.path.join(ROOT, "manifest.csv")

rows = []
# manifest.csv 带 UTF-8 BOM（表头首字段实际是 "\ufeffcode"），必须用 utf-8-sig
with open(MANIFEST, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        if r.get("kind") == "prospectus":
            rows.append(r)

print(f"manifest 招股书行：{len(rows)}")
print(f"不同股票代码：{len({r['code'] for r in rows})}")

by_year = collections.Counter((r.get("date") or "")[:4] for r in rows)
print("按披露年份：", dict(sorted(by_year.items())))

strict_ipo = [r for r in rows if "首次公开发行" in r["title"] or "首次公开" in r["title"]]
has_kw = [r for r in rows if "招股说明书" in r["title"]]
starts_about = [r for r in rows if r["title"].startswith("关于")]
has_summary = [r for r in rows if "概要" in r["title"] or "摘要" in r["title"]]
no_kw = [r for r in rows if "招股说明书" not in r["title"]]

print()
print(f"标题含「首次公开发行」：{len(strict_ipo)}")
print(f"标题含「招股说明书」  ：{len(has_kw)}")
print(f"标题不含「招股说明书」：{len(no_kw)}   ← 基本是假阳性")
print(f"标题以「关于」开头    ：{len(starts_about)}   ← 多为过程/相关公告")
print(f"标题含「概要/摘要」    ：{len(has_summary)}   ← 非全文")

suspect = [r for r in rows
           if ("招股说明书" not in r["title"]) or r["title"].startswith("关于")
           or "概要" in r["title"] or "摘要" in r["title"]]
print()
print(f"=== 疑似非正本合计 {len(suspect)} / {len(rows)} ===")
for r in suspect[:30]:
    print(f"  {r['code']} {r['name']:<8} {r['date']}  {r['title'][:88]}")
if len(suspect) > 30:
    print(f"  … 另 {len(suspect) - 30} 条")
