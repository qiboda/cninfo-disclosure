#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 4：给招股书 PDF 链接分类 —— 真 PDF / 老式 HTML 存档 / 404。

只读前 8 字节判定，不落盘。
用法：python probe_urls.py [root] [sample]
"""
import collections
import json
import os
import random
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")
sys.stdout.reconfigure(encoding="utf-8")

from cninfo_client import query_by_stock, DOWNLOAD_HEADERS  # noqa: E402
from prospectus import filter_prospectus  # noqa: E402

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"E:\cninfo"
SAMPLE = int(sys.argv[2]) if len(sys.argv) > 2 else 150

uni = json.load(open(ROOT + r"\_state\universe.json", encoding="utf-8"))
have = {f[:6] for f in os.listdir(ROOT + r"\prospectus")
        if f[:6].isdigit() and f[6:7] == "_"}
missing = [s for s in uni if s["code"] not in have]
random.seed(7)
missing = random.sample(missing, min(SAMPLE, len(missing)))
print(f"抽样 {len(missing)} / 缺失 {len(uni) - len(have)}")

lock = threading.Lock()


def classify(url):
    try:
        req = urllib.request.Request(url, headers=DOWNLOAD_HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=30) as r:
            head = r.read(8)
            ct = (r.headers.get("Content-Type") or "")
        if head[:5] == b"%PDF-":
            return "pdf"
        if "html" in ct or head[:5] == b"<!---" or head[:5] == b"<!DOC":
            return "html"
        return "other"
    except urllib.error.HTTPError as e:
        return f"http{e.code}"
    except Exception as e:  # noqa: BLE001
        return f"err:{type(e).__name__}"


def work(s):
    try:
        anns = query_by_stock(s["stock_param"], s["column"], "1990-01-01", "2099-12-31",
                              category="", searchkey="招股说明书",
                              page_size=30, max_pages=10)
    except Exception as e:  # noqa: BLE001
        return ("query-fail", None)
    tgt = filter_prospectus(anns) if anns else None
    if not tgt:
        return ("no-pick", None)
    return (classify(tgt["pdf_url"]), tgt)


rows = []
with ThreadPoolExecutor(max_workers=8) as ex:
    for r in ex.map(work, missing):
        rows.append(r)

c = collections.Counter(k for k, _ in rows)
print("\n=== 链接分类 ===")
for k, v in c.most_common():
    print(f"  {k:<14} {v:>4}  {v/len(rows):.0%}")

print("\n=== 老式 HTML 存档样例 ===")
html_rows = [t for k, t in rows if k == "html"]
for t in html_rows[:12]:
    print(f"  {t['date']}  {t['title'][:60]}  {t['pdf_url']}")
print(f"  合计 {len(html_rows)} 条")

print("\n=== 404 样例 ===")
n404 = [t for k, t in rows if str(k).startswith("http4")]
for t in n404[:8]:
    print(f"  {t['date']}  {t['title'][:60]}  {t['pdf_url']}")
