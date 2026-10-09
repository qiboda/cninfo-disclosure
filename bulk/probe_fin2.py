# -*- coding: utf-8 -*-
r"""探针 2：用 fitz(PyMuPDF) + urllib 探「成长性筛选」的两条取数路径。

A) 本地 PDF：业绩预告 / 业绩快报能不能稳定抽出 净利润、营收、同比增幅
B) 结构化接口：东方财富数据中心能不能直接给全市场多期财务指标（无 requests，用 urllib）

用法: python bulk\probe_fin2.py
输出: bulk\probe_fin2.out.txt
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = os.path.join(_HERE, "probe_fin2.out.txt")
_buf = []


def say(s=""):
    print(s)
    _buf.append(str(s))


ROOT = r"C:\Users\iq112\Documents\cninfo"

# ---------------------------------------------------------------- A) 本地 PDF
say("=" * 74)
say("A) 本地业绩预告 PDF 抽数（fitz）")
say("=" * 74)

samples = []
for dirpath, _d, filenames in os.walk(os.path.join(ROOT, "by_date")):
    if os.path.basename(dirpath) in ("业绩预告", "业绩快报"):
        samples += [os.path.join(dirpath, f) for f in filenames if f.lower().endswith(".pdf")]
samples.sort()
say("可用 %d 份\n" % len(samples))

NUM = r"[-+]?[\d,]+(?:\.\d+)?"
try:
    import fitz
    for path in samples[:2]:
        say("-" * 74)
        say(os.path.basename(path))
        with fitz.open(path) as doc:
            npages = doc.page_count
            text = "\n".join(pg.get_text() for pg in doc)
        say("页数 %d  正文字符 %d" % (npages, len(text)))
        flat = re.sub(r"[ \t\u3000]+", " ", text)
        # 抓「归属于上市公司股东的净利润」「营业收入」附近的行
        for kw in ("归属于上市公司股东的净利润", "净利润", "营业收入", "比上年同期", "盈利", "亏损"):
            hits = [ln.strip() for ln in flat.splitlines() if kw in ln]
            if hits:
                say("  [%s] %d 行，前 3:" % (kw, len(hits)))
                for ln in hits[:3]:
                    say("      %s" % ln[:150])
        # 表格区（数字密集行）
        dens = [ln.strip() for ln in flat.splitlines()
                if len(re.findall(NUM, ln)) >= 2 and len(ln.strip()) > 10]
        say("  数字密集行共 %d 行，前 8:" % len(dens))
        for ln in dens[:8]:
            say("      %s" % ln[:150])

except Exception as exc:
    say("fitz 抽数失败: %r" % (exc,))

# ---------------------------------------------------------- B) 结构化接口
say()
say("=" * 74)
say("B) 东方财富数据中心接口（urllib）")
say("=" * 74)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://data.eastmoney.com/"}


def em(report_name, columns="ALL", filt=None, page_size=3,
       sort_cols=None, sort_types="-1"):
    q = {"reportName": report_name, "columns": columns, "pageNumber": 1,
         "pageSize": page_size, "source": "WEB", "client": "WEB"}
    if filt:
        q["filter"] = filt
    if sort_cols:
        q["sortColumns"] = sort_cols
        q["sortTypes"] = sort_types
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


TESTS = [
    ("全市场业绩报表(2026H1)", "RPT_LICO_FN_CPD", "(REPORTDATE='2026-06-30')",
     "TOTAL_OPERATE_INCOME"),
    ("全市场业绩报表(2026Q3)", "RPT_LICO_FN_CPD", "(REPORTDATE='2026-09-30')",
     "TOTAL_OPERATE_INCOME"),
    ("业绩预告(2026三季)", "RPT_PUBLIC_OP_NEWPREDICT", "(REPORT_DATE='2026-09-30')", None),
]

for label, report, filt, sortc in TESTS:
    say("-" * 74)
    say("%s  [%s]" % (label, report))
    try:
        j = em(report, filt=filt, sort_cols=sortc)
        res = j.get("result") or {}
        say("  success=%s count=%s pages=%s" % (j.get("success"), res.get("count"), res.get("pages")))
        if j.get("message"):
            say("  message=%s" % j["message"])
        for row in (res.get("data") or [])[:3]:
            keys = [k for k in row if any(t in k for t in
                    ("CODE", "NAME", "INCOME", "NETPROFIT", "TZ", "DATE", "PREDICT", "CHANGE"))]
            say("    " + "  ".join("%s=%s" % (k, row[k]) for k in keys[:12]))
    except Exception as exc:
        say("  失败: %r" % (exc,))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(_buf))
print("\n-> %s" % OUT)
