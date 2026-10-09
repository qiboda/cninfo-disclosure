# -*- coding: utf-8 -*-
"""探针：盘点「做成长性筛选」可用的取数手段。

1) 本机有哪些 PDF / 表格 / 网络库
2) 已有业绩预告 PDF 能不能抽出正文（决定能否从自己下载的文件里解析数字）
3) 东方财富的结构化财务接口是否可用（备选取数路径）

用法: python bulk\probe_fin.py
输出: bulk\probe_fin.out.txt
"""
import importlib
import io
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = os.path.join(_HERE, "probe_fin.out.txt")
_buf = []


def say(s=""):
    print(s)
    _buf.append(str(s))


say("=" * 70)
say("1) 库可用性")
say("=" * 70)
for m in ("pdfplumber", "pypdf", "PyPDF2", "fitz", "pdfminer", "pandas",
          "requests", "numpy", "bs4", "lxml", "openpyxl"):
    try:
        mod = importlib.import_module(m)
        say("  OK   %-12s %s" % (m, getattr(mod, "__version__", "?")))
    except Exception as exc:
        say("  --   %-12s %s" % (m, type(exc).__name__))

ROOT = r"C:\Users\iq112\Documents\cninfo"
say()
say("=" * 70)
say("2) 已有业绩预告 / 业绩快报 PDF 抽样")
say("=" * 70)
samples = []
for dirpath, _dirnames, filenames in os.walk(os.path.join(ROOT, "by_date")):
    if os.path.basename(dirpath) in ("业绩预告", "业绩快报"):
        for fn in filenames:
            if fn.lower().endswith(".pdf"):
                samples.append(os.path.join(dirpath, fn))
samples.sort()
say("  找到 %d 份" % len(samples))
for p in samples[:4]:
    say("    %s" % os.path.relpath(p, ROOT))

if samples:
    target = samples[0]
    say()
    say("  抽正文: %s" % os.path.relpath(target, ROOT))
    text = None
    try:
        import pdfplumber
        with pdfplumber.open(target) as pdf:
            say("  页数 %d" % len(pdf.pages))
            text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except Exception as exc:
        say("  pdfplumber 失败: %r" % (exc,))
        try:
            from pypdf import PdfReader
            text = "\n".join((pg.extract_text() or "") for pg in PdfReader(target).pages)
        except Exception as exc2:
            say("  pypdf 也失败: %r" % (exc2,))
    if text:
        say("  正文长度 %d 字符" % len(text))
        say("  ---- 前 2500 字 ----")
        say(text[:2500])
        say("  ---- 含数字的行 ----")
        for ln in text.splitlines():
            if any(ch.isdigit() for ch in ln) and len(ln.strip()) > 8:
                say("    " + ln.strip()[:160])

say()
say("=" * 70)
say("3) 东方财富结构化财务接口探测")
say("=" * 70)
try:
    import requests
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    # 业绩报表（按报告期拉全市场主要财务指标）
    params = {
        "reportName": "RPT_LICO_FN_CPD",
        "columns": "ALL",
        "filter": '(REPORTDATE=\'2026-06-30\')',
        "pageNumber": 1,
        "pageSize": 3,
        "sortColumns": "TOTAL_OPERATE_INCOME",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
    }
    r = requests.get(url, params=params, timeout=20, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"})
    say("  HTTP %s len=%d" % (r.status_code, len(r.text)))
    j = r.json()
    say("  success=%s  pages=%s  count=%s" % (
        j.get("success"), (j.get("result") or {}).get("pages"),
        (j.get("result") or {}).get("count")))
    for row in ((j.get("result") or {}).get("data") or [])[:3]:
        say("    %s %s 营收=%s 净利=%s 营收同比=%s 净利同比=%s" % (
            row.get("SECURITY_CODE"), row.get("SECURITY_NAME_ABBR"),
            row.get("TOTAL_OPERATE_INCOME"), row.get("PARENT_NETPROFIT"),
            row.get("YSTZ"), row.get("SJLTZ")))
except Exception as exc:
    say("  失败: %r" % (exc,))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(_buf))
print("\n-> %s" % OUT)
