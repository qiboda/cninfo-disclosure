# -*- coding: utf-8 -*-
"""探针：北交所（92xxxx）在腾讯行情里的符号前缀。"""
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Referer": "https://gu.qq.com/"}

syms = ["bj920157", "sh920157", "sz920157", "bj920202", "bj430047",
        "bj920157,sh920157"]
for s in syms:
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request("https://qt.gtimg.cn/q=" + s, headers=HEADERS),
            timeout=20).read().decode("gbk", "replace")
    except Exception as e:  # noqa: BLE001
        print("%-10s FAIL %s %s" % (s, type(e).__name__, e))
        continue
    raw = raw.strip()
    print("%-10s -> %s" % (s, raw[:220] if raw else "(空)"))
