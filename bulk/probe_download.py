#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针 3：定位招股书 PDF 下载被反爬拦截的真实原因。

对同一批 URL 换多种请求头 / 协议 / 主机重试，比对状态码与文件头。
用法：python probe_download.py [root]
"""
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\scripts")
sys.stdout.reconfigure(encoding="utf-8")

from cninfo_client import query_by_stock, USER_AGENT  # noqa: E402
from prospectus import filter_prospectus  # noqa: E402

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"E:\cninfo"
uni = {s["code"]: s for s in json.load(open(ROOT + r"\_state\universe.json", encoding="utf-8"))}

WIN_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")

VARIANTS = [
    ("current       ", {"User-Agent": USER_AGENT, "Referer": "http://www.cninfo.com.cn/"}),
    ("accept-pdf    ", {"User-Agent": USER_AGENT, "Referer": "http://www.cninfo.com.cn/",
                        "Accept": "application/pdf,*/*"}),
    ("referer-https ", {"User-Agent": USER_AGENT, "Referer": "https://www.cninfo.com.cn/"}),
    ("no-referer    ", {"User-Agent": USER_AGENT}),
    ("win-ua        ", {"User-Agent": WIN_UA, "Referer": "http://www.cninfo.com.cn/"}),
    ("full-browser  ", {"User-Agent": WIN_UA,
                        "Referer": "http://www.cninfo.com.cn/new/disclosure/stock",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Accept-Encoding": "identity",
                        "Connection": "keep-alive"}),
]


def probe(url):
    print(f"\nURL: {url}")
    for name, hdr in VARIANTS:
        try:
            req = urllib.request.Request(url, headers=hdr, method="GET")
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read(64 * 1024)
                total = r.headers.get("Content-Length")
                print(f"  {name} {r.status} len={len(data)} cl={total} "
                      f"ct={r.headers.get('Content-Type')} head={data[:16]!r}")
        except urllib.error.HTTPError as e:
            print(f"  {name} HTTP {e.code} {e.reason}")
        except Exception as e:  # noqa: BLE001
            print(f"  {name} {type(e).__name__}: {e}")


for code in ["600218", "600519"]:
    s = uni[code]
    anns = query_by_stock(s["stock_param"], s["column"], "1990-01-01", "2099-12-31",
                          category="", searchkey="招股说明书", page_size=30, max_pages=10)
    tgt = filter_prospectus(anns) if anns else None
    print("=" * 70)
    print(f"{code} {s['name']} 选中={tgt['title'][:50] if tgt else None}")
    if tgt:
        probe(tgt["pdf_url"])
