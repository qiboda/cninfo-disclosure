# -*- coding: utf-8 -*-
"""探针：腾讯日 K 线接口（算年初至今 / 近 60 日涨跌幅要用）。

用法：python probe_kline_tencent.py
"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://gu.qq.com/",
}


def try_url(name, url):
    print("--- %s" % name)
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers=HEADERS), timeout=20).read()
    except Exception as e:  # noqa: BLE001
        print("    FAIL %s: %s" % (type(e).__name__, e))
        return None
    print("    bytes=%d  head=%r" % (len(raw), raw[:120]))
    return raw


def main():
    # 前复权日 K
    u1 = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
          "param=sz300821,day,2026-01-01,2026-10-09,320,qfq")
    raw = try_url("ifzq fqkline", u1)
    if raw:
        j = json.loads(raw.decode("utf-8"))
        d = (j.get("data") or {}).get("sz300821") or {}
        print("    keys=%s" % list(d.keys()))
        for k in ("qfqday", "day"):
            if k in d:
                rows = d[k]
                print("    %s 行数=%d 首=%s 末=%s" % (k, len(rows), rows[0], rows[-1]))
                break

    # 备用：不带复权
    u2 = ("https://web.ifzq.gtimg.cn/appstock/app/kline/kline?"
          "param=sz300821,day,,,320")
    raw = try_url("ifzq kline", u2)

    # 备用：腾讯 newfqkline
    u3 = ("https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get?"
          "param=sz300821,day,2026-01-01,2026-10-09,320,qfq")
    try_url("proxy newfqkline", u3)


if __name__ == "__main__":
    main()
