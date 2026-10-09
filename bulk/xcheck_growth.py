# -*- coding: utf-8 -*-
"""xcheck_growth.py —— 用东方财富结构化接口交叉校验 PDF 抽出来的数字。

PDF 抽取最危险的失败模式不是「抽不到」，而是「抽到了但不对」——
一个错误的净利区间会让一只票从 D 档跳进 A 档。这里拿一个**独立数据源**
（东财业绩预告/业绩报表接口）来对账。

接口（urllib 即可，无需 requests）：
    https://datacenter-web.eastmoney.com/api/data/v1/get
    reportName=RPT_PUBLIC_OP_NEWPREDICT  业绩预告
    reportName=RPT_LICO_FN_CPD           业绩报表（实际值）
    filter=(REPORTDATE='2026-09-30')

坑（踩过）：同一只票在 `RPT_PUBLIC_OP_NEWPREDICT` 里是**一行一个口径**，
`PREDICT_FINANCE` 分别是「归属于上市公司股东的净利润」「扣除非经常性损益后的
净利润」「营业收入」。用 `{code: row}` 建索引会被最后一行的**营业收入**覆盖，
于是晶晨股份 688099 的净利 12.6~13.1 亿被拿去和营收 70.8~71.8 亿比，报出
假差异。必须按 `(code, PREDICT_FINANCE)` 建索引。
"""
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://data.eastmoney.com/",
}
FIN_PARENT = "归属于上市公司股东的净利润"
FIN_DEDUCT = "扣除非经常性损益后的净利润"
FIN_REV = "营业收入"


def api(report, filt, cols="ALL", size=500):
    q = urllib.parse.urlencode({
        "reportName": report, "columns": cols, "filter": filt,
        "pageNumber": 1, "pageSize": size, "source": "WEB", "client": "WEB",
    })
    req = urllib.request.Request(API + "?" + q, headers=HDRS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def yuan2yi(v):
    if v in (None, ""):
        return None
    try:
        return round(float(v) * 1e-8, 4)
    except (TypeError, ValueError):
        return None


def span(a, b):
    if a is None and b is None:
        return "-"
    if a is not None and b is not None and abs(a - b) > 1e-9:
        return "%.4g~%.4g" % (a, b)
    return "%.4g" % (a if a is not None else b)


def verdict(mine_lo, mine_hi, elo, ehi):
    """PDF 抽到的区间是否落在东财区间内（东财是官方口径原文）。"""
    if elo is None:
        return "东财无值"
    tol = 0.02
    if mine_lo is None:
        return "PDF缺净利"
    ok_lo = abs(mine_lo - elo) <= max(tol, abs(elo) * 0.02)
    ok_hi = (mine_hi is None) or abs(mine_hi - ehi) <= max(tol, abs(ehi) * 0.02)
    return "OK" if (ok_lo and ok_hi) else "**差异**"


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "_growth")
    with open(os.path.join(root, "extract.json"), encoding="utf-8") as f:
        recs = json.load(f)
    mine = {r["code"]: r for r in recs if r["kind"] == "yjyg"}

    j = api("RPT_PUBLIC_OP_NEWPREDICT", "(REPORT_DATE='2026-09-30')")
    rows = (j.get("result") or {}).get("data") or []
    idx = {}
    for r in rows:
        idx.setdefault(r["SECURITY_CODE"], {})[r["PREDICT_FINANCE"]] = r
    print("东财业绩预告 2026-09-30：%d 行 / %d 只" % (len(rows), len(idx)))
    print()

    hdr = "%-8s %-8s | %-16s %-16s %-6s | %-16s %-16s %-6s | %s"
    print(hdr % ("code", "name", "PDF归母(亿)", "东财归母(亿)", "判定",
                 "PDF营收(亿)", "东财营收(亿)", "判定", "同比(PDF/东财)"))
    print("-" * 132)
    bad = 0
    for code, r in sorted(mine.items(), key=lambda kv: kv[1]["name"]):
        e = idx.get(code) or {}
        ep, er = e.get(FIN_PARENT) or {}, e.get(FIN_REV) or {}
        elo, ehi = yuan2yi(ep.get("PREDICT_AMT_LOWER")), yuan2yi(ep.get("PREDICT_AMT_UPPER"))
        rlo, rhi = yuan2yi(er.get("PREDICT_AMT_LOWER")), yuan2yi(er.get("PREDICT_AMT_UPPER"))
        vp = verdict(r.get("profit_low_yi"), r.get("profit_high_yi"), elo, ehi)
        vr = verdict(r.get("revenue_low_yi"), r.get("revenue_high_yi"), rlo, rhi)
        yoy = ""
        if ep:
            yoy = "%s / %s" % (fmt_pdf_yoy(r.get("yoy")),
                               "%s~%s" % (ep.get("ADD_AMP_LOWER"), ep.get("ADD_AMP_UPPER")))
        if "差异" in vp:
            bad += 1
        print(hdr % (code, r["name"], span(r.get("profit_low_yi"), r.get("profit_high_yi")),
                     span(elo, ehi), vp,
                     span(r.get("revenue_low_yi"), r.get("revenue_high_yi")),
                     span(rlo, rhi), vr, yoy))
    print("-" * 132)
    print("归母净利口径差异：%d / %d" % (bad, len(mine)))

    # 落盘给 rank_growth 合并用：东财是官方口径原文，PDF 窗口漏掉的同比用它补
    dump = {}
    for code, r in mine.items():
        e = idx.get(code) or {}
        ep, er, ed = e.get(FIN_PARENT) or {}, e.get(FIN_REV) or {}, e.get(FIN_DEDUCT) or {}
        elo, ehi = yuan2yi(ep.get("PREDICT_AMT_LOWER")), yuan2yi(ep.get("PREDICT_AMT_UPPER"))
        rlo, rhi = yuan2yi(er.get("PREDICT_AMT_LOWER")), yuan2yi(er.get("PREDICT_AMT_UPPER"))
        dump[code] = {
            "name": r["name"],
            "em_profit": [yuan2yi(ep.get("PREDICT_AMT_LOWER")), yuan2yi(ep.get("PREDICT_AMT_UPPER"))],
            "em_profit_yoy": [ep.get("ADD_AMP_LOWER"), ep.get("ADD_AMP_UPPER")],
            "em_profit_type": ep.get("PREDICT_TYPE"),
            "em_revenue": [yuan2yi(er.get("PREDICT_AMT_LOWER")), yuan2yi(er.get("PREDICT_AMT_UPPER"))],
            "em_revenue_yoy": [er.get("ADD_AMP_LOWER"), er.get("ADD_AMP_UPPER")],
            "em_deduct": [yuan2yi(ed.get("PREDICT_AMT_LOWER")), yuan2yi(ed.get("PREDICT_AMT_UPPER"))],
            "em_deduct_yoy": [ed.get("ADD_AMP_LOWER"), ed.get("ADD_AMP_UPPER")],
            "pdf_profit": [r.get("profit_low_yi"), r.get("profit_high_yi")],
            "pdf_revenue": [r.get("revenue_low_yi"), r.get("revenue_high_yi")],
            "verdict": verdict(r.get("profit_low_yi"), r.get("profit_high_yi"), elo, ehi),
            "em_reason": (ep.get("CHANGE_REASON_EXPLAIN") or "")[:900],
            "em_content": ep.get("PREDICT_CONTENT") or "",
        }
    out = os.path.join(root, "em_yjyg.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=1)
    print("-> %s" % out)

    # 实际值对账（已出正式季报的）
    j2 = api("RPT_LICO_FN_CPD", "(REPORTDATE='2026-09-30')")
    row2 = ((j2.get("result") or {}).get("data") or [])
    print("\n东财业绩报表 2026-09-30 命中 %d 条" % len(row2))
    for r in row2:
        c = r["SECURITY_CODE"]
        m2 = next((x for x in recs if x["code"] == c), None)
        print("  %s %s 东财营收=%s 净利=%s" % (c, r.get("SECURITY_NAME_ABBR"),
                                           r.get("TOTAL_OPERATE_INCOME"), r.get("PARENT_NETPROFIT")))
        if m2 and m2.get("revenue"):
            print("     PDF: 前三季营收=%.4f亿 净利=%.4f亿" % (
                m2["revenue"]["ytd_yi"], m2["net_profit"]["ytd_yi"]))


def fmt_pdf_yoy(lst):
    if not lst:
        return "-"
    return ";".join("%s%s~%s%%" % (y.get("dir") or "", y.get("low"), y.get("high")) for y in lst)


if __name__ == "__main__":
    sys.exit(main())
