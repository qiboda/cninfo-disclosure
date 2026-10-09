# -*- coding: utf-8 -*-
"""探针：确认腾讯行情 `qt.gtimg.cn` 的字段下标，并用东财年报库交叉验证 PE(静)。

背景：东财 `push2.eastmoney.com` 行情端点在连续请求后会被 IP 级限流
（`RemoteDisconnected`），无法用于批量取数 → 改用腾讯行情。

用法：python probe_quote_tencent.py
"""
import json
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

TENCENT = "https://qt.gtimg.cn/q="
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://gu.qq.com/",
}

# 下标 → 含义（本探针要验证的假设）
IDX = {
    1: "名称", 2: "代码", 3: "当前价", 4: "昨收", 5: "今开", 6: "成交量(手)",
    31: "时间", 32: "涨跌额", 33: "涨跌幅%", 34: "最高", 35: "最低",
    37: "成交量(手)", 38: "成交额(万)", 39: "换手率%", 40: "市盈率(TTM)",
    44: "振幅%", 45: "流通市值(亿)", 46: "总市值(亿)", 47: "市净率",
    48: "涨停价", 49: "跌停价", 50: "量比", 52: "均价",
    53: "市盈率(动)", 54: "市盈率(静)",
    72: "流通股本", 73: "总股本",
}


def tencent(codes):
    raw = urllib.request.urlopen(
        urllib.request.Request(TENCENT + ",".join(codes), headers=HEADERS),
        timeout=20).read().decode("gbk", "replace")
    out = {}
    for line in raw.strip().split(";"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').split("~")
    return out


def em_annual(code):
    """东财年报库取最近年报归母净利（元）。"""
    params = {
        "reportName": "RPT_LICO_FN_CPD", "columns": "ALL", "pageNumber": "1",
        "pageSize": "10", "sortColumns": "REPORTDATE", "sortTypes": "-1",
        "source": "WEB", "client": "WEB",
        "filter": '(SECURITY_CODE="%s")' % code,
    }
    req = urllib.request.Request(
        "https://datacenter-web.eastmoney.com/api/data/v1/get?"
        + urllib.parse.urlencode(params),
        headers={"User-Agent": HEADERS["User-Agent"],
                 "Referer": "https://data.eastmoney.com/"})
    j = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
    rows = (j.get("result") or {}).get("data") or []
    return [(r["REPORTDATE"][:10], r.get("PARENT_NETPROFIT")) for r in rows[:4]]


def main():
    codes = ["sh600176", "sz300821", "sz002107", "sh688099", "sz300373"]
    q = tencent(codes)
    for key, p in q.items():
        print("=== %s  %s  字段数=%d" % (key, p[1] if len(p) > 1 else "?", len(p)))
        for i in sorted(IDX):
            if i < len(p):
                print("    [%2d] %-12s %s" % (i, IDX[i], p[i]))
        mv = float(p[46]) if len(p) > 46 and p[46] else None
        pe_s = float(p[54]) if len(p) > 54 and p[54] else None
        pe_d = float(p[53]) if len(p) > 53 and p[53] else None
        pe_t = float(p[40]) if len(p) > 40 and p[40] else None
        if mv and pe_s:
            print("    └ PE静反推上年净利 = %.4f 亿" % (mv / pe_s))
        if mv and pe_d:
            print("    └ PE动反推年化净利 = %.4f 亿" % (mv / pe_d))
        if mv and pe_t:
            print("    └ PE_TTM反推滚动净利 = %.4f 亿" % (mv / pe_t))

    print()
    print("--- 东财年报库交叉验证（归母净利，元）---")
    for c in ("600176", "300821", "002107", "688099", "300373"):
        try:
            rows = em_annual(c)
        except Exception as e:  # noqa: BLE001
            print("  %s 查询失败 %s" % (c, e))
            continue
        for d, v in rows:
            if v:
                print("  %s %s 归母 %.4f 亿" % (c, d, v / 1e8))


if __name__ == "__main__":
    main()
