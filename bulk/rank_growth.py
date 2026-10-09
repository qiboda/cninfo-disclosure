# -*- coding: utf-8 -*-
"""rank_growth.py —— 把 _growth/extract.json 汇总成「规模 + 成长」榜单。

用法：
    python rank_growth.py build   [--since 2026-09-01] [--until 2026-12-31]
    python rank_growth.py print

产物：
    bulk/_growth/rank_growth.csv   榜单（UTF-8-SIG，Excel 直接打开）
    bulk/_growth/rank_growth.json  同内容的机器可读版

设计要点
--------
1. 同比增速**只在各自的窗口里取**。`profit_window` / `revenue_window` 是
   extract 阶段从标签往后截的 70 字，窗口外的百分比（比如营收的 61.26%）
   绝不能算到净利头上 —— 气派科技 688216 就是营收 +61.26% 而净利是扭亏为盈。
2. 「高利润/高营收」是**规模**门槛，「成长」是**增速**门槛，两者分开打分，
   最后再合成 tier。阈值集中放在 THRESHOLDS，改一处即可。
3. IPO 招股书给的是 2023→2025 三年数，能直接算 CAGR，是判断「超级成长股」
   最硬的证据；业绩预告只有单季/单年区间，只能算同比。两类不给同一个分。
"""

import argparse
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DEFAULT = os.path.join(HERE, "_growth")

# ---------------------------------------------------------------- 阈值
THRESHOLDS = {
    "scale_profit_yi": 1.0,      # 净利 >= 1 亿 视为「高利润」
    "scale_revenue_yi": 10.0,    # 营收 >= 10 亿 视为「高营收」
    "growth_rev_yoy": 20.0,      # 营收同比 >= 20%
    "growth_profit_yoy": 30.0,   # 净利同比 >= 30%
    "super_rev_cagr": 25.0,      # 营收 CAGR >= 25%
    "super_profit_cagr": 30.0,   # 净利 CAGR >= 30%
    "super_profit_yi": 1.0,      # 且净利体量 >= 1 亿（避免小基数噪音）
}

# ---------------------------------------------------------------- 窗口内同比
RE_PCT_RANGE = re.compile(r"([-－—]?[\d.]+)\s*%\s*[-—–~～至到]\s*([-－—]?[\d.]+)\s*%")
RE_PCT_ONE = re.compile(r"([-－—]?[\d.]+)\s*%")
RE_UP = re.compile(r"(增长|增加|上升|提升)")
RE_DOWN = re.compile(r"(下降|减少|下滑|降低)")
# 同比锚点：**必须先找锚点再取百分号**。否则鼎龙股份 300054 的营收 240 字窗里
# 「营业收入约29.15亿元，同比增长8%……净利润……同比增长62%-66%」会先撞上
# 62%-66%（那是净利的），营收同比被错标成 +62%~66%。
RE_ANCHOR = re.compile(r"(?:同比|较上年同期|比上年同期|与上年同期相比|较去年同期)")
QUAL = [
    (re.compile(r"扭亏为盈|实现盈利"), "扭亏为盈"),
    (re.compile(r"由盈转亏|转为亏损|出现亏损"), "由盈转亏"),
    (re.compile(r"基本持平|与上年同期基本持平"), "基本持平"),
    (re.compile(r"亏损(?:收窄|减少)"), "亏损收窄"),
    (re.compile(r"亏损(?:扩大|增加)"), "亏损扩大"),
]


def win_yoy(window):
    """从窗口文本里取同比。返回 {low, high, dir, kind} 或 None。

    顺序：① 第一个同比锚点后 30 字内的百分号；② 没有锚点才退到裸的
    「增长/下降 X%~Y%」或第一个百分号。
    """
    if not window:
        return None
    body = window.split("|", 1)[1] if "|" in window else window
    body = body.replace(" ", "")

    a = RE_ANCHOR.search(body)
    if a:
        seg = body[a.end():a.end() + 30]
        r = _pct_in(seg, body, a.end())
        if r:
            return r
        # 锚点太远（如「与上年同期不具备可比性」）→ 不硬猜
    r = _pct_in(body[:200], body, 0)
    if r:
        return r
    # 全文没有百分号时，认定性表述（气派科技 688216 的净利就是「同比扭亏为盈」）
    for rx, label in QUAL:
        if rx.search(body):
            return {"low": None, "high": None, "dir": label, "kind": "qual"}
    return None


def _pct_in(seg, body, off):
    m = RE_PCT_RANGE.search(seg)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return {"low": min(lo, hi), "high": max(lo, hi),
                "dir": _dir(body[max(0, off + m.start() - 14):off + m.end()]), "kind": "pct"}
    m = RE_PCT_ONE.search(seg)
    if m:
        v = float(m.group(1))
        seg2 = body[max(0, off + m.start() - 14):off + m.end()]
        d = _dir(seg2)
        if d == "?" and v < 0:
            d = "下降"
        return {"low": v, "high": v, "dir": d, "kind": "pct"}
    return None


def _dir(seg):
    if RE_UP.search(seg):
        return "增长"
    if RE_DOWN.search(seg):
        return "下降"
    return "?"


# ---------------------------------------------------------------- 每类记录 → 一行
def _mid(lo, hi):
    if lo is None:
        return hi
    if hi is None:
        return lo
    return round((lo + hi) / 2.0, 4)


def _cagr(first, last, years):
    if not first or first <= 0 or last is None or years <= 0:
        return None
    return round(((last / first) ** (1.0 / years) - 1.0) * 100.0, 2)


def row_yjyg(r):
    prof = _mid(r.get("profit_low_yi"), r.get("profit_high_yi"))
    rev = _mid(r.get("revenue_low_yi"), r.get("revenue_high_yi"))
    py = win_yoy(r.get("profit_window")) or win_yoy(r.get("revenue_window"))
    ry = win_yoy(r.get("revenue_window"))
    return {
        "code": r["code"], "name": r["name"], "kind": "业绩预告", "date": r["date"],
        "revenue_yi": rev, "profit_yi": prof,
        "profit_note": _span(r.get("profit_low_yi"), r.get("profit_high_yi")),
        "revenue_note": _span(r.get("revenue_low_yi"), r.get("revenue_high_yi")),
        "profit_basis": r.get("profit_label") or "",
        "revenue_basis": r.get("revenue_label") or "",
        "profit_yoy": _fmt(py), "profit_yoy_sort": _sort(py),
        "revenue_yoy": _fmt(ry), "revenue_yoy_sort": _sort(ry),
        "revenue_cagr": None, "profit_cagr": None,
        "period": "2026Q3", "source": "业绩预告",
    }


def _qpct(s):
    """季报的同比是字符串 '-5.73%' / '44.78%'。"""
    if not s:
        return None
    m = re.search(r"([-－—]?[\d.]+)", str(s))
    if not m:
        return None
    v = float(m.group(1))
    if str(s).strip().startswith(("-", "－", "—")):
        v = -abs(v)
    return v


def row_q3(r):
    rev = r.get("revenue") or {}
    prof = r.get("net_profit") or {}
    ded = r.get("deduct_profit") or {}
    ry = _qpct(rev.get("ytd_yoy"))
    py = _qpct(prof.get("ytd_yoy"))
    return {
        "code": r["code"], "name": r["name"], "kind": "三季报", "date": r["date"],
        "revenue_yi": rev.get("ytd_yi"), "profit_yi": prof.get("ytd_yi"),
        "profit_note": "扣非%.4g亿" % ded["ytd_yi"] if ded.get("ytd_yi") is not None else "",
        "revenue_note": "",
        "profit_basis": "归母净利润", "revenue_basis": "营业收入",
        "profit_yoy": _ymark(py), "profit_yoy_sort": py,
        "revenue_yoy": _ymark(ry), "revenue_yoy_sort": ry,
        "revenue_cagr": None, "profit_cagr": None,
        "period": "2026前三季度", "source": "定期报告",
    }


def _ymark(v):
    if v is None:
        return ""
    return ("增长 " if v >= 0 else "下降 ") + ("%.2f%%" % abs(v))



def row_ipo(r):
    rev = (r.get("revenue_3y") or {}).get("yi") or []
    prof = (r.get("profit_3y") or {}).get("yi") or []
    n = min(len(rev), len(prof)) if prof else 0
    ry = None
    py = None
    if len(rev) >= 2:
        ry = {"low": round((rev[-1] / rev[-2] - 1) * 100, 2), "high": None, "dir": "", "kind": "pct"}
        ry["high"] = ry["low"]
        ry["dir"] = "增长" if ry["low"] >= 0 else "下降"
    if len(prof) >= 2 and prof[-2] and prof[-2] > 0:
        v = round((prof[-1] / prof[-2] - 1) * 100, 2)
        py = {"low": v, "high": v, "dir": "增长" if v >= 0 else "下降", "kind": "pct"}
    # CAGR 需要首末都为正；亏损企业给不出有意义的值
    yrs = max(len(rev) - 1, 1)
    rc = _cagr(rev[0] if rev else None, rev[-1] if rev else None, yrs)
    pc = _cagr(prof[0] if prof else None, prof[-1] if prof else None, max(len(prof) - 1, 1))
    return {
        "code": r["code"], "name": r["name"], "kind": "IPO招股书", "date": r["date"],
        "revenue_yi": rev[-1] if rev else None,
        "profit_yi": prof[-1] if prof else None,
        "profit_note": " / ".join("%.4g" % v for v in prof),
        "revenue_note": " / ".join("%.4g" % v for v in rev),
        "profit_basis": (r.get("profit_3y") or {}).get("label") or "",
        "revenue_basis": (r.get("revenue_3y") or {}).get("label") or "",
        "profit_yoy": _fmt(py), "profit_yoy_sort": _sort(py),
        "revenue_yoy": _fmt(ry), "revenue_yoy_sort": _sort(ry),
        "revenue_cagr": rc, "profit_cagr": pc,
        "period": "2023-2025", "source": "招股书三年财务",
        "n_hist": n,
    }


def _span(lo, hi):
    if lo is None and hi is None:
        return ""
    if lo is not None and hi is not None and abs(lo - hi) > 1e-9:
        return "%.4g~%.4g" % (lo, hi)
    return "%.4g" % (lo if lo is not None else hi)


def _fmt(y):
    if not y:
        return ""
    d = y.get("dir") or ""
    if y.get("kind") == "qual":
        return d
    lo, hi = y.get("low"), y.get("high")
    if lo is None:
        return d
    if hi is None or abs(hi - lo) < 1e-9:
        s = "%.2f%%" % lo
    else:
        s = "%.2f%%~%.2f%%" % (lo, hi)
    return (d + " " + s).strip()


def _sort(y):
    """排序/阈值用的带符号值。**必须带符号** —— 飞龙股份 002536 的窗口是
    「下降 59.20%~66.87%」，若直接返回 66.87 会被当成 +66.87% 高速成长。"""
    if not y or y.get("low") is None:
        return None
    v = y.get("high", y.get("low"))
    d = y.get("dir") or ""
    if d == "下降" or y.get("low") < 0:
        return -abs(v)
    return abs(v)


def _em_yoy(em, key):
    """东财 ADD_AMP_LOWER/UPPER 已带符号（-66.87/-59.2），直接成对返回。"""
    v = em.get(key) or []
    if len(v) != 2 or v[0] is None or v[1] is None:
        return None
    lo, hi = float(v[0]), float(v[1])
    return {"low": min(lo, hi), "high": max(lo, hi),
            "dir": "增长" if max(lo, hi) >= 0 else "下降", "kind": "pct"}


def merge_em(rows, root):
    """把东财官方同比补进 PDF 抽不到的窗口，并留下对账结论。"""
    p = os.path.join(root, "em_yjyg.json")
    if not os.path.exists(p):
        return rows
    with open(p, encoding="utf-8") as f:
        em = json.load(f)
    for x in rows:
        e = em.get(x["code"])
        if not e or x["kind"] != "业绩预告":
            continue
        x["xcheck"] = e.get("verdict", "")
        x["em_type"] = e.get("em_profit_type") or ""
        x["em_profit"] = _span(e.get("em_profit")[0], e.get("em_profit")[1]) if e.get("em_profit") else ""
        x["em_profit_yoy"] = _fmt(_em_yoy(e, "em_profit_yoy")) or ""
        x["yoy_src"] = "PDF"
        if x.get("profit_yoy_sort") is None:
            y = _em_yoy(e, "em_profit_yoy")
            if y:
                x["profit_yoy"] = _fmt(y)
                x["profit_yoy_sort"] = _sort(y)
                x["yoy_src"] = "东财"
        # 扭亏 / 低基数：同比百分比看着惊人，但不是经营性内生增速
        ty = x.get("em_type") or ""
        yv = x.get("profit_yoy_sort")
        x["low_base"] = bool(ty in ("扭亏", "首亏") or (yv is not None and abs(yv) >= 1000))
    return rows


# ---------------------------------------------------------------- 打分
def score(row, th=THRESHOLDS):
    rev = row.get("revenue_yi")
    prof = row.get("profit_yi")
    big_profit = prof is not None and prof >= th["scale_profit_yi"]
    big_rev = rev is not None and rev >= th["scale_revenue_yi"]
    row["flag_scale"] = bool(big_profit or big_rev)
    row["scale_why"] = (
        ("净利%.4g亿" % prof if big_profit else "")
        + ("/" if big_profit and big_rev else "")
        + ("营收%.4g亿" % rev if big_rev else "")
    )

    ry = row.get("revenue_yoy_sort")
    py = row.get("profit_yoy_sort")
    fast = (ry is not None and ry >= th["growth_rev_yoy"]) or \
           (py is not None and py >= th["growth_profit_yoy"])
    row["flag_growth"] = bool(fast)
    parts = []
    if ry is not None and ry >= th["growth_rev_yoy"]:
        parts.append("营收+%.2f%%" % ry)
    if py is not None and py >= th["growth_profit_yoy"]:
        parts.append("净利+%.2f%%" % py)
    # 定性提速
    for f, lab in (("revenue_yoy", row.get("revenue_yoy")), ("profit_yoy", row.get("profit_yoy"))):
        if lab and ("扭亏为盈" in lab or "亏损收窄" in lab):
            parts.append(lab)
            row["flag_growth"] = True
    row["growth_why"] = "/".join(parts)
    if row.get("low_base"):
        row["growth_why"] = (row["growth_why"] + " [低基数/扭亏]").strip()

    rc, pc = row.get("revenue_cagr"), row.get("profit_cagr")
    row["flag_super"] = bool(
        rc is not None and rc >= th["super_rev_cagr"]
        and pc is not None and pc >= th["super_profit_cagr"]
        and prof is not None and prof >= th["super_profit_yi"]
    )
    row["super_why"] = ("营收CAGR %.1f%% / 净利CAGR %.1f%%" % (rc, pc)) if (rc is not None and pc is not None) else ""

    if row["flag_super"]:
        row["tier"] = "A 超级成长"
    elif prof is not None and prof < 0:
        row["tier"] = "X 未盈利"
    elif row["flag_scale"] and row["flag_growth"]:
        row["tier"] = "B 高规模+高增速"
    elif row["flag_growth"]:
        row["tier"] = "C 高增速"
    elif row["flag_scale"]:
        row["tier"] = "D 仅规模"
    else:
        row["tier"] = "E 观察"
    return row


# ---------------------------------------------------------------- 组装
def build(root, since, until):
    src = os.path.join(root, "extract.json")
    with open(src, encoding="utf-8") as f:
        recs = json.load(f)
    rows = []
    for r in recs:
        d = r.get("date") or ""
        if since and d < since:
            continue
        if until and d > until:
            continue
        if r.get("kind") == "yjyg":
            rows.append(row_yjyg(r))
        elif r.get("kind") == "q3":
            rows.append(row_q3(r))
        elif r.get("kind") == "ipo":
            rows.append(row_ipo(r))
    # 先把东财官方同比补进来，再打分 —— 否则行云科技 300209（PDF 窗口没抓到
    # 「同比+431.84%~500.98%」）会被判成「仅规模」，档位差两级。
    rows = merge_em(rows, root)
    rows = [score(x) for x in rows]
    order = {"A 超级成长": 0, "B 高规模+高增速": 1, "C 高增速": 2, "D 仅规模": 3, "X 未盈利": 4, "E 观察": 5}
    rows.sort(key=lambda x: (order.get(x["tier"], 9),
                             -(x.get("profit_yoy_sort") or -999),
                             -(x.get("profit_yi") or 0)))

    csv_path = os.path.join(root, "rank_growth.csv")
    cols = ["tier", "kind", "code", "name", "date", "period",
            "revenue_yi", "profit_yi", "revenue_note", "profit_note",
            "revenue_yoy", "profit_yoy", "revenue_cagr", "profit_cagr",
            "revenue_basis", "profit_basis",
            "flag_scale", "scale_why", "flag_growth", "growth_why", "flag_super", "super_why",
            "xcheck", "em_type", "em_profit", "em_profit_yoy", "yoy_src", "low_base",
            "source", "code_note"]
    for x in rows:
        x.setdefault("code_note", "")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for x in rows:
            w.writerow(x)
    with open(os.path.join(root, "rank_growth.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    return rows, csv_path


def cmd_build(a):
    rows, p = build(a.root, a.since, a.until)
    tally = {}
    for x in rows:
        tally[x["tier"]] = tally.get(x["tier"], 0) + 1
    print("榜单 %d 行 -> %s" % (len(rows), p))
    for k in sorted(tally):
        print("  %-12s %d" % (k, tally[k]))
    return 0


def cmd_print(a):
    rows, _ = build(a.root, a.since, a.until)
    print("%-12s %-9s %-6s %-6s %-10s %10s %10s %-14s %-14s" %
          ("tier", "kind", "code", "date", "name", "营收亿", "净利亿", "营收同比", "净利同比"))
    for x in rows:
        print("%-12s %-9s %-6s %-6s %-10s %10s %10s %-14s %-14s" % (
            x["tier"], x["kind"], x["code"], x["date"], x["name"],
            "" if x["revenue_yi"] is None else "%.3f" % x["revenue_yi"],
            "" if x["profit_yi"] is None else "%.3f" % x["profit_yi"],
            x["revenue_yoy"] or "-", x["profit_yoy"] or "-"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="成长性榜单")
    ap.add_argument("cmd", choices=["build", "print"])
    ap.add_argument("--root", default=OUT_DEFAULT)
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--until", default="2026-12-31")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "print": cmd_print}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
