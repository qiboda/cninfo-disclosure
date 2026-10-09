# -*- coding: utf-8 -*-
r"""成长性筛选：从 by_date 已下载的 PDF 里抽取财务数据与「成长逻辑」证据。

用法:
  python bulk\screen_growth.py extract [--root R] [--since 2026-09-01] [--until 2026-12-31]
  python bulk\screen_growth.py check            # 打印抽取结果（含置信度与命中的原文）

产物（默认 --out bulk\_growth）:
  text\<date>_<code>_<kind>.txt   每份 PDF 的全文（空白已归一化）
  extract.json                    结构化抽取结果
  digest.txt                      摘要：金额、同比、变动原因 / 主营业务原文

为什么只做「抽取」不做「判定」：判据是「有没有成长逻辑」，属于定性问题，
数字只能做初筛，最终必须读「业绩变动原因说明 / 主营业务与行业前景」的原文。

巨潮公告的金额有四种排布，解析层必须都认（实测样本）：
  A 表格体带单位   「盈利：35,000万元-43,000万元」                         富祥股份
  B 表格体裸数字   「净利润 / 54,700 / ～ / 56,700 / 285.67」+「单位：万元」  东岳硅材
  C 叙述体         「预计…净利润为513,628.51万元至539,309.94万元」          中国巨石
  D 季报表格       「营业收入（元）/195,494,895.87/-1.89%/588,844,408.64/-5.73%」 沃华医药

三个实测踩过的坑（v3 修正）：
  1. 表格体的标签会被换行拆断（「归属于上市公司股」「东的净利润」）→ 标签匹配必须容忍空白。
  2. 「归属于上市公司股东的净利润」在「业绩变动原因」段里会被复述一次，
     首次命中往往落在那里（本川智能 300964）→ 必须**按能否在标签后 70 字内取到金额来打分**，
     不能取首次命中。
  3. 「预计净利润为正值且属于同向上升情形」这种表格前言会先命中短标签「净利润」，
     再往后取到的是**营业收入**那一行（川金诺 300505）→ 长标签优先 + 金额距离约束。
"""
import argparse
import csv
import io
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT_DEFAULT = r"C:\Users\iq112\Documents\cninfo"
OUT_DEFAULT = os.path.join(_HERE, "_growth")

# --------------------------------------------------------------- 文本归一化
_WS = re.compile(r"[ \t\u3000\xa0]+")
_NL = re.compile(r"\n{2,}")
_UNIT_GAP = re.compile(r"(?<=[\d,.])\s+(?=(?:万元|亿元|元|%|个百分点))")
# 页眉/页脚：PyMuPDF 会把「……股份有限公司招股说明书1-1-19」插进正文句子中间。
# 不剥掉会破坏下面的「扣除→净利润」邻近度判断（中塑股份 301686 因此取成了扣非值）。
RE_PAGEHEAD = re.compile(r"[\u4e00-\u9fa5]{2,24}(?:招股说明书|招股意向书|募集说明书)"
                         r"\s*\d{0,3}\s*[-－—]\s*\d{1,3}\s*[-－—]\s*\d{1,4}")
# 「扣除……净利润」的排除窗口必须按正则量、不能按固定字符数：页眉插进来会拉长距离
DEDUCT_BEFORE = re.compile(r"扣除(?:非经常性损益|非经常损益|非经常性)?[^。；\n]{0,90}$")


def norm(text):
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = _WS.sub(" ", t)
    t = re.sub(r"(万|亿)\s+元", r"\1元", t)      # 表格常把「万元」拆成「万 元」
    t = _UNIT_GAP.sub("", t)
    t = RE_PAGEHEAD.sub("", t)                   # 页眉会插进句子中间，破坏邻近度判断
    t = _NL.sub("\n", t)
    lines = [ln.strip() for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def flatten(text):
    """把换行压成空格 —— 表格体的数字和标签常被拆在不同行。

    顺带补一次「万 元 → 万元」：旧版 norm 没做这步，缓存的 text/ 文件里仍有这种拆法。
    """
    t = re.sub(r"(万|亿)\s+元", r"\1元", text)
    return re.sub(r"\s*\n\s*", " ", t)


def flex(label):
    """把标签编译成容忍任意空白的正则（表格体会把标签拆行）。"""
    return r"\s*".join(re.escape(c) for c in label)


def read_pdf(path):
    import fitz  # PyMuPDF 1.28.2；注意 page_count 必须在 with 块内取，块外抛 document closed
    with fitz.open(path) as doc:
        pages = [pg.get_text() for pg in doc]
        n = doc.page_count
    return n, norm("\n".join(pages))


# ----------------------------------------------------------------- 金额解析
NUM = r"\d[\d,]*(?:\.\d+)?"
UNIT = r"万\s*元|亿\s*元|元"
UNIT_TO_YI = {"元": 1e-8, "万元": 1e-4, "亿元": 1.0}
# 区间分隔符：破折号系、波浪号系、「至」，以及部分公告用的「到」
# （景旺电子 603228 / 永和股份 605020 / 国力电子 688103 都用「到」）
RANGE_SEP = r"[-—–~～至到]"
# 金额前的情态标记：一个表格里「盈利：本期区间」和「亏损：上年同期值」会同时出现，
# 符号必须取自紧贴金额的那个标记，不能全窗口搜「亏损」（富祥股份/行云科技踩过）
MARKER = r"(?:(盈利|亏损)\s*[：:]?\s*)?"

RE_UNIT_HINT = re.compile(r"单位[：:]\s*(万元|亿元|元)")


def _f(s):
    return float(s.replace(",", ""))


def _u(s):
    return s.replace(" ", "") if s else None


def to_yi(v, unit):
    return round(v * UNIT_TO_YI[unit], 4)


def auto_unit(v, unit_hint):
    """没有「单位：万元」提示时，按量级猜单位（亿元级数字当「元」处理）。"""
    if unit_hint:
        return unit_hint
    return "元" if v >= 1e6 else "万元"


def _sign(marker, window, pos):
    if marker == "亏损":
        return -1
    if marker == "盈利":
        return 1
    return -1 if "亏损" in window[max(0, pos - 6):pos] else 1


def pick_range(window, unit_hint=None):
    """在窗口里找金额区间。返回 (low_raw, high_raw, unit, sign) 或 None。

    依次尝试：带单位区间（A/C）→ 裸数字区间（B）→ 单值带单位。
    符号取自紧贴金额的「盈利/亏损」标记或金额前 6 字，不做全窗口搜索。
    """
    m = re.search(MARKER + r"(" + NUM + r")\s*(" + UNIT + r")\s*" + RANGE_SEP + r"\s*(" + NUM + r")\s*(" + UNIT + r")", window)
    if m:
        lo, hi = _f(m.group(2)), _f(m.group(4))
        u1, u2 = _u(m.group(3)), _u(m.group(5))
        unit = u1 if u1 == u2 else auto_unit(max(lo, hi), unit_hint)
        return lo, hi, unit, _sign(m.group(1), window, m.start(2))
    m = re.search(MARKER + r"(?<![\d,.])(\d[\d,]{2,}(?:\.\d+)?)\s*" + RANGE_SEP + r"\s*(\d[\d,]{2,}(?:\.\d+)?)(?![\d,.])", window)
    if m:
        lo, hi = _f(m.group(2)), _f(m.group(3))
        return lo, hi, auto_unit(max(lo, hi), unit_hint), _sign(m.group(1), window, m.start(2))
    m = re.search(MARKER + r"(" + NUM + r")\s*(" + UNIT + r")", window)
    if m:
        v = _f(m.group(2))
        return v, v, _u(m.group(3)), _sign(m.group(1), window, m.start(2))
    return None


PROFIT_LABELS = ["归属于上市公司股东的扣除非经常性损益的净利润",   # 仅用于排除，见下
                 "归属于上市公司股东的净利润",
                 "归属于母公司所有者的净利润", "归属于上市公司股东净利润",
                 "归属于挂牌公司股东的净利润", "归属于母公司股东的净利润",
                 "归母净利润", "净利润"]
REVENUE_LABELS = ["营业总收入", "营业收入"]
# 扣非口径的标签：绝不能当成「净利润」来取
DEDUCT_MARK = re.compile(r"扣除(?:非经常性损益|非经常损益)")


def best_amount(flat, labels, unit_hint=None, span=70):
    """全文扫描标签，返回第一个「标签后 span 字内确实有金额」的命中。

    为什么要 span 约束而不是取首次命中：见模块 docstring 坑 2、坑 3。
    """
    for lb in labels:
        if lb.startswith("归属于上市公司股东的扣除非"):
            continue
        pat = re.compile(flex(lb))
        for m in pat.finditer(flat):
            # 命中的若是「归属于上市公司股东的扣除非经常性损益的净利润」的前缀，跳过
            after = flat[m.end():m.end() + 14]
            if DEDUCT_MARK.match(after):
                continue
            win = flat[m.end():m.end() + span]
            pr = pick_range(win, unit_hint)
            if pr and pr[0] > 0 and pr[1] > 0:
                # 第 5 项 = 宽窗（240 字），只用于事后取同比；
                # 金额判定仍然只用 span，避免把下一行的数字误当本期值。
                return lb, m.group(0), win, pr, flat[m.end():m.end() + 240]
    return None


# ------------------------------------------------------------------- 变动原因
RE_REASON = re.compile(
    r"业绩变动原因(?:说明|的说明)?[^\n]{0,20}\n(.*?)(?=\n\s*[一二三四五六七八九十]+[、.]|\n\s*特此公告|"
    r"\n\s*风险提示|\n\s*其他(?:相关)?说明|\n\s*[0-9]+[、.]\s*(?:其他|风险|本次|备查))", re.S)


def add_reason(rec, text):
    m = RE_REASON.search(text)
    body = m.group(1).strip() if m else None
    if not body:
        lines = text.split("\n")
        for i, ln in enumerate(lines):
            if "原因" in ln and ("变动" in ln or "业绩" in ln or "增长" in ln):
                body = "\n".join(lines[i:i + 14]).strip()
                break
    if not body:
        i = text.find("变动原因")
        if i < 0:
            i = text.find("原因说明")
        if i >= 0:
            body = text[i:i + 900]
    if body:
        rec["reason"] = re.sub(r"\n+", "\n", body)[:1500]
    return rec


# --------------------------------------------------------------- 业绩预告/快报
def parse_preannounce(text):
    out = {}
    flat = flatten(text)
    uh = RE_UNIT_HINT.search(flat)
    unit_hint = uh.group(1) if uh else None

    hit = best_amount(flat, [l for l in PROFIT_LABELS if not l.startswith("归属于上市公司股东的扣除非")],
                      unit_hint, span=70)
    if hit:
        lb, raw, win, (lo, hi, unit, sign), wide = hit
        out["profit_label"] = lb
        out["profit_low_yi"] = round(to_yi(lo, unit) * sign, 4)
        out["profit_high_yi"] = round(to_yi(hi, unit) * sign, 4)
        out["profit_unit"] = unit
        out["profit_window"] = (raw + "|" + wide)[:300]

    hit = best_amount(flat, REVENUE_LABELS, unit_hint, span=70)
    if hit:
        lb, raw, win, (lo, hi, unit, sign), wide = hit
        # 营收行不会写「亏损」，但可能被「营业收入同比下降」等文字带偏，做量级保护
        out["revenue_label"] = lb
        out["revenue_low_yi"] = round(to_yi(lo, unit), 4)
        out["revenue_high_yi"] = round(to_yi(hi, unit), 4)
        out["revenue_unit"] = unit
        out["revenue_window"] = (raw + "|" + wide)[:300]

    # 同比：A/B 体在金额表里，C 体在重要提示/原因段里
    yoy = []
    for m in re.finditer(r"(?:比上年同期|较上年同期|同比)\s*(增长|增加|上升|下降|减少)\s*[：:]?\s*"
                         r"([-+]?[\d,]+(?:\.\d+)?)\s*%?\s*" + RANGE_SEP + r"\s*([-+]?[\d,]+(?:\.\d+)?)\s*%", flat):
        a, b = _f(m.group(2)), _f(m.group(3))
        yoy.append({"low": min(a, b), "high": max(a, b), "dir": m.group(1)})
    for m in re.finditer(r"(?:比上年同期|较上年同期|同比)\s*(增长|增加|上升|下降|减少)\s*(?:人民币)?\s*"
                         r"([-+]?[\d,]+(?:\.\d+)?)\s*%", flat):
        v = _f(m.group(2))
        yoy.append({"low": v, "high": v, "dir": m.group(1)})
    for m in re.finditer(r"(增长|下降)\s*([0-9.]+)%\s*" + RANGE_SEP + r"\s*([0-9.]+)%", flat):
        a, b = _f(m.group(2)), _f(m.group(3))
        if not any(y["low"] == min(a, b) and y["high"] == max(a, b) for y in yoy):
            yoy.append({"low": min(a, b), "high": max(a, b), "dir": m.group(1)})
    # 去重保序
    uniq, seen = [], set()
    for y in yoy:
        k = (y["low"], y["high"], y["dir"])
        if k not in seen:
            seen.add(k)
            uniq.append(y)
    if uniq:
        out["yoy"] = uniq[:6]
    return out


# ------------------------------------------------------------------- 三季报
Q3_ROWS = [("revenue", "营业收入（元）"),
           ("net_profit", "归属于上市公司股东的净利润（元）"),
           ("deduct_profit", "归属于上市公司股东的扣除非经常性损益的净利润（元）")]
RE_Q3_ROW = re.compile(r"\s*[（(]?\s*(?:元|万元|亿元)?\s*[）)]?\s*"
                       r"(" + NUM + r")\s*([-—]?[\d.]+%)\s*(" + NUM + r")\s*([-—]?[\d.]+%)")


def parse_q3(text):
    out = {}
    flat = flatten(text)
    for name, lb in Q3_ROWS:
        m = re.search(flex(lb) + RE_Q3_ROW.pattern, flat)
        if not m:
            continue
        out[name] = {
            "q3_yuan": _f(m.group(1)), "q3_yoy": m.group(2),
            "ytd_yuan": _f(m.group(3)), "ytd_yoy": m.group(4),
            "ytd_yi": round(_f(m.group(3)) * 1e-8, 4),
            "q3_yi": round(_f(m.group(1)) * 1e-8, 4),
        }
    return out


# ------------------------------------------------------------------- 招股书
# 表格体：标签后紧接 3 个数字（要求同量级，过滤目录页码/百分比噪声）
RE_TABLE3 = re.compile(r"(" + NUM + r")\s*(" + NUM + r")\s*(" + NUM + r")")

# 叙述体：「报告期内，公司营业收入分别为 70,043.05万元、86,622.18万元和89,547.00万元」
# 坑 1：分隔符里**不能含 ASCII 逗号** —— 它同时是千分位分隔符，
#       会把「净利润1,689,372,378.77元」切成 1,689 / 372 / 378.77（莫森泰克 920162 踩过）。
# 坑 2：值个数必须允许 2 个（力勤资源 001246 / 联亚药业 301569 / 宇特光电 920157 只披露两期）。
# 坑 3：亏损企业必须允许负号（粤芯半导体 301660 三年归母净利 -19.17 / -22.53 / -23.46 亿）。
def _narr_re(signed):
    s = r"[-－—]?" if signed else ""
    num = s + r"\d[\d,]*(?:\.\d+)?"
    return re.compile(
        r"(?P<n1>" + num + r")\s*(?P<u1>万\s*元|亿\s*元|元)?\s*[、，和及]\s*"
        r"(?P<n2>" + num + r")\s*(?P<u2>万\s*元|亿\s*元|元)?"
        r"(?:\s*[、，和及]\s*(?P<n3>" + num + r")\s*(?P<u3>万\s*元|亿\s*元|元)?)?")


RE_IPO_NARR = _narr_re(signed=False)
RE_IPO_NARR_S = _narr_re(signed=True)

IPO_REVENUE_LABELS = ["营业总收入", "营业收入"]
IPO_PROFIT_LABELS = ["归属于母公司所有者的净利润", "归属于上市公司股东的净利润",
                     "归属于母公司股东的净利润", "净利润"]

MAIN_BIZ_ANCHORS = ["发行人主营业务", "公司主营业务", "主营业务情况", "主营业务"]
BIZ_HINT = re.compile(r"(公司|产品|客户|销售|研发|生产|行业)")
TOC_MARK = re.compile(r"\.{4,}|…{2,}")


def _pick_main_biz(flat):
    best, best_score = None, 0
    for anchor in MAIN_BIZ_ANCHORS:
        for m in re.finditer(re.escape(anchor), flat):
            win = flat[m.start():m.start() + 900]
            if TOC_MARK.search(win[:200]):
                continue
            score = len(BIZ_HINT.findall(win)) - 3 * len(TOC_MARK.findall(win))
            if score > best_score:
                best, best_score = win, score
        if best and best_score >= 8:
            break
    return best


def _unit_of(units, values):
    for u in reversed(units):
        if u:
            return u.replace(" ", "")
    return auto_unit(max(values), None)


def _ipo_narrative(flat, labels, signed=False):
    """扫全文，收集「X分别为 a、b、c」候选，附带位置，供配对打分。"""
    rx = RE_IPO_NARR_S if signed else RE_IPO_NARR
    cands = []
    for lb in labels:
        for m in re.finditer(flex(lb) + r"[^。；\n]{0,14}?(?:分别)?为\s*" + rx.pattern, flat):
            # 排除扣非口径。标签列表里有短标签「净利润」，它会在
            # 「扣除非经常性损益后归属于母公司所有者的净利润」里二次命中，
            # 而「净利润」前 14 字只看到「……性损益后归属于母公司所有者的」，抓不到「扣除」。
            # （安达股份 920202 / 中塑股份 301686 / 力勤资源 001246 都被取成了扣非值。）
            if DEDUCT_BEFORE.search(flat[max(0, m.start() - 140):m.start()]):
                continue
            raw = [m.group("n1"), m.group("n2"), m.group("n3")]
            vals = [_f(x) for x in raw if x]
            if len(vals) < 2:
                continue
            units = [m.group("u1"), m.group("u2"), m.group("u3")][:len(vals)]
            unit = _unit_of(units, vals)
            yi = [round(v * UNIT_TO_YI[unit], 4) for v in vals]
            abs_ = [abs(v) for v in yi]
            if max(abs_) <= 0 or max(abs_) / max(min(abs_), 1e-6) > 30:
                continue          # 超过 30 倍波动多半是拼错的碎片
            cands.append({"src": "narrative", "unit": unit, "values": vals, "yi": yi,
                          "n": len(vals), "pos": m.start(), "label": lb,
                          "rank": 0 if lb.startswith("归属于") else 1,
                          "text": flat[m.start():m.end()][:200]})
    return cands


def _ipo_table(flat, labels):
    """退路：表格体，标签后 3 个同量级数字。"""
    for lb in labels:
        for m in re.finditer(flex(lb), flat):
            if "扣除" in flat[max(0, m.start() - 14):m.start()]:
                continue
            win = flat[m.end():m.end() + 60]
            t = RE_TABLE3.search(win)
            if not t:
                continue
            vals = [_f(t.group(i)) for i in (1, 2, 3)]
            if min(vals) <= 0 or max(vals) / min(vals) > 4 or min(vals) < 1000:
                continue
            yi = [round(v * 1e-4, 4) for v in vals]
            return {"src": "table", "unit": "万元", "values": vals, "yi": yi,
                    "text": (m.group(0) + "|" + win)[:200], "confidence": "low"}
    return None


def _best_alone(cands):
    return sorted(cands, key=lambda c: (c["n"], max(abs(v) for v in c["yi"])), reverse=True)[0]


# 「主要财务数据」表在**未压平的按行文本**里是干净的：标签独占一行，随后 3 行各一个数。
# 压平之后数字会连成一串没法切（「12,686.0410,006.087,924.10」），所以这条路径必须走 lines。
NUM_LINE = re.compile(r"^[-－—]?[\d,]+(?:\.\d+)?$")
YEAR_LINE = re.compile(r"^(20\d{2})\s*(?:年度|年)?$")


def _table_years(lines, i):
    """从表头行往回抓年份，返回**从左到右**的顺序。"""
    years = []
    for j in range(i - 1, max(-1, i - 25), -1):
        if YEAR_LINE.match(lines[j]):
            years.append(int(lines[j][:4]))
            if len(years) == 3:
                break
        elif years:
            break
    return list(reversed(years))


def _table_unit(lines, i):
    for j in range(i - 1, max(-1, i - 30), -1):
        m = re.search(r"单位[：:]\s*(万元|亿元|元)", lines[j])
        if m:
            return m.group(1)
    return None


def _ipo_table_lines(lines, labels, allow_neg=False):
    """找「标签独占一行 + 紧跟 3 个纯数字行」的表 —— 主要财务数据表。

    注意外层循环是 labels：短标签「净利润」和「归属于母公司所有者的净利润」在
    同一张表里相邻出现，必须让长标签先扫描全文，否则会先撞上「净利润」那一行。
    """
    for lb in labels:
        lbc = lb.replace(" ", "")
        for i, ln in enumerate(lines):
            if lbc not in ln or "扣除" in ln:
                continue
            head = re.sub(r"[（(][^）)]*[）)]$", "", ln)
            if len(head) - len(lbc) > 6:
                continue
            vals = []
            for j in range(i + 1, min(i + 8, len(lines))):
                if NUM_LINE.match(lines[j]):
                    vals.append(_f(lines[j]))
                    if len(vals) == 3:
                        break
                elif vals:
                    break
            if len(vals) != 3:
                continue
            av = [abs(v) for v in vals]
            if min(av) <= 0 or max(av) / min(av) > 30:
                continue
            if not allow_neg and min(vals) <= 0:
                continue
            unit = _table_unit(lines, i) or auto_unit(max(av), None)
            yrs = _table_years(lines, i)
            desc = len(yrs) == 3 and yrs[0] > yrs[-1]
            if desc:
                vals = list(reversed(vals))     # 表是「最新在前」，统一翻成升序
            return {"src": "line_table", "unit": unit, "values": vals,
                    "yi": [round(v * UNIT_TO_YI[unit], 4) for v in vals],
                    "years": yrs, "desc": desc, "label": lb,
                    "text": (lb + " | " + " / ".join("%s" % v for v in vals))}
    return None


def _ipo_financials(flat, lines=None):
    rev = _ipo_narrative(flat, IPO_REVENUE_LABELS)
    prof = _ipo_narrative(flat, IPO_PROFIT_LABELS, signed=True)
    out = {}
    if rev and prof:
        # 营收句与净利句紧邻（同一段「财务概况」/「主要财务数据」），用位置邻近度配对。
        # 不配对会命中「2026 年度盈利预测」段：力勤资源 001246 的归母净利曾被取成
        # 5,641,270.04 万元（564 亿），而报告期真实值是 10.50 / 17.68 / 28.62 亿。
        # 排序第一优先「两边的期数都要多」—— 否则会选中
        # 「……对应的营业收入和净利润金额分别为41,126.27万元和2,813.93万元」这类
        # 两值杂句（它俩位置只差 3 字，距离永远最小；安达股份/鸿富诚/文峰光电踩过）。
        pairs = sorted(((min(a["n"], b["n"]), min(a["rank"], b["rank"]),
                         abs(a["pos"] - b["pos"]), a, b)
                        for a in rev for b in prof),
                       key=lambda t: (-t[0], t[1], t[2]))
        nbest, rbest, dist, ra, rb = pairs[0]
        if dist <= 60000:
            out["revenue_3y"], out["profit_3y"] = ra, rb
            out["pair_dist"], out["pair_n"] = dist, nbest
        else:
            out["revenue_3y"], out["profit_3y"] = _best_alone(rev), _best_alone(prof)
            out["pair_dist"] = None
    elif rev:
        out["revenue_3y"] = _best_alone(rev)
    elif prof:
        out["profit_3y"] = _best_alone(prof)
    # 表路径只做兜底：它可能命中别的章节 / 别的单位 / 别的排序
    # （文峰光电 920296 的营收、联亚药业 301569 的净利都撞过错表）。
    # 中塑股份 301686 是唯一必须走这条路径的 —— 全篇没有非扣非的叙述句。
    if lines:
        if "revenue_3y" not in out:
            t = _ipo_table_lines(lines, IPO_REVENUE_LABELS)
            if t:
                out["revenue_3y"] = t
        if "profit_3y" not in out:
            t = _ipo_table_lines(lines, IPO_PROFIT_LABELS, allow_neg=True)
            if t:
                out["profit_3y"] = t
    if "revenue_3y" not in out:
        t = _ipo_table(flat, IPO_REVENUE_LABELS)
        if t:
            out["revenue_3y"] = t
    if "profit_3y" not in out:
        t = _ipo_table(flat, IPO_PROFIT_LABELS)
        if t:
            out["profit_3y"] = t
    return out


def parse_prospectus(text):
    out = {}
    flat = flatten(text)
    lines = [re.sub(r"\s+", "", l) for l in text.split("\n")]
    lines = [l for l in lines if l]
    out.update(_ipo_financials(flat, lines))
    biz = _pick_main_biz(flat)
    if biz:
        out["main_biz"] = biz.strip()[:1200]
    m = re.search(r"报告期(?:系|为|指)\s*([^。；]{0,60})", flat)
    if m:
        out["report_period"] = m.group(1).strip()
    for kw in ("募集资金投资项目概况", "募集资金投资项目", "募集资金运用"):
        i = flat.find(kw)
        if i >= 0:
            win = flat[i:i + 700]
            if not TOC_MARK.search(win[:150]):
                out["use_of_proceeds"] = win
                break
    return out


PARSERS = {"yjyg": parse_preannounce, "yjkb": parse_preannounce,
           "ipo": parse_prospectus, "q3": parse_q3}
REASON_KINDS = ("yjyg", "yjkb")


# --------------------------------------------------------------------- 主流程
def load_batch(root, since, until):
    p = os.path.join(root, "manifest_by_date.csv")
    rows = []
    with open(p, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if since <= r["date"] <= until:
                rows.append(r)
    rows.sort(key=lambda r: (r["date"], r["kind"], r["code"]))
    return rows


def build(args):
    outdir = args.out
    textdir = os.path.join(outdir, "text")
    os.makedirs(textdir, exist_ok=True)
    rows = load_batch(args.root, args.since, args.until)
    old = {}
    jp = os.path.join(outdir, "extract.json")
    if os.path.exists(jp) and not args.force:
        try:
            for r in json.load(open(jp, encoding="utf-8")):
                old[(r["date"], r["code"], r["kind"])] = r
        except Exception:
            pass
    print("批次 %d 份（%s ~ %s）" % (len(rows), args.since, args.until))
    results = []
    for i, r in enumerate(rows, 1):
        key = (r["date"], r["code"], r["kind"])
        tf = os.path.join(textdir, "%s_%s_%s.txt" % key)
        rec = {k: r[k] for k in ("date", "kind", "code", "name", "title", "size_bytes",
                                 "board", "filepath", "pdf_url")}
        try:
            if os.path.exists(tf) and old.get(key, {}).get("chars") and not args.force:
                # 再走一次 norm()：text/ 缓存的文本是用旧版归一化写的，
                # 而 norm 是幂等的，重跑零成本，省掉一次 300 万字 PDF 解析
                text = norm(open(tf, encoding="utf-8").read())
                rec["pages"] = old[key].get("pages")
                rec["cached_text"] = True
            else:
                npages, text = read_pdf(r["filepath"])
                rec["pages"] = npages
                with open(tf, "w", encoding="utf-8") as fh:
                    fh.write(text)
            rec["chars"] = len(text)
            rec["text_file"] = os.path.basename(tf)
            p = PARSERS.get(r["kind"])
            if p:
                rec.update(p(text))
            if r["kind"] in REASON_KINDS:
                add_reason(rec, text)
            print("  [%2d/%d] %-5s %-8s %-10s %s" % (
                i, len(rows), r["kind"], r["code"], r["name"],
                "净利 %s~%s亿" % (rec.get("profit_low_yi"), rec.get("profit_high_yi"))
                if rec.get("profit_low_yi") else ("有原因段" if rec.get("reason") else "无")))
        except Exception as exc:
            rec["error"] = repr(exc)
            print("  [%2d/%d] 失败 %s %s: %r" % (i, len(rows), r["kind"], r["code"], exc))
        results.append(rec)
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    write_digest(os.path.join(outdir, "digest.txt"), results)
    print("\n-> %s" % jp)
    return results


def write_digest(path, results):
    chunks = []
    for r in results:
        d = ["=" * 78,
             "%s  %s  %s %s" % (r["date"], r["kind"].upper(), r["code"], r["name"]),
             "%s" % r["title"]]
        for k in ("profit_label", "profit_low_yi", "profit_high_yi", "profit_unit",
                  "revenue_label", "revenue_low_yi", "revenue_high_yi", "revenue_unit",
                  "yoy", "profit_window", "revenue_window"):
            if k in r:
                d.append("  %-16s %s" % (k, json.dumps(r[k], ensure_ascii=False)[:300]))
        if "revenue" in r:
            d.append("  q3营收 %s" % json.dumps(r["revenue"], ensure_ascii=False))
        if "net_profit" in r:
            d.append("  q3净利 %s" % json.dumps(r["net_profit"], ensure_ascii=False))
        if r.get("report_period"):
            d.append("  报告期 %s" % r["report_period"])
        for k in ("revenue_3y", "profit_3y"):
            if k in r:
                d.append("  %-16s %s" % (k, json.dumps(r[k], ensure_ascii=False)[:400]))
        if r.get("reason"):
            d.append("  --- 业绩变动原因 ---")
            d.append(r["reason"])
        if r.get("main_biz"):
            d.append("  --- 主营业务 ---")
            d.append(r["main_biz"][:900])
        if r.get("use_of_proceeds"):
            d.append("  --- 募集资金投向 ---")
            d.append(r["use_of_proceeds"][:400])
        chunks.append("\n".join(d))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(chunks))


def cmd_check(args):
    results = json.load(open(os.path.join(args.out, "extract.json"), encoding="utf-8"))
    for r in results:
        if r["kind"] not in ("yjyg", "yjkb"):
            continue
        p = r.get("profit_low_yi")
        line = "%s %-6s %-5s 净利 %s~%s 亿" % (r["code"], r["name"], r["kind"], p, r.get("profit_high_yi"))
        if r.get("revenue_low_yi"):
            line += " | 营收 %s~%s 亿" % (r["revenue_low_yi"], r.get("revenue_high_yi"))
        print(line + ("  [%s]" % r["profit_unit"] if r.get("profit_unit") else ""))
        if p is None:
            print("     !! 未取到净利润 — 窗口: %s" % (r.get("profit_window") or "(无命中)"))
    print("\n---- 非预告 ----")
    for r in results:
        if r["kind"] == "q3":
            print("%s %-6s q3  营收 %s亿(%s) 净利 %s亿(%s)" % (
                r["code"], r["name"], r["revenue"]["ytd_yi"], r["revenue"]["ytd_yoy"],
                r["net_profit"]["ytd_yi"], r["net_profit"]["ytd_yoy"]))
        elif r["kind"] == "ipo":
            rv = r.get("revenue_3y", {})
            pf = r.get("profit_3y", {})
            print("%s %-6s ipo 营收%s %s | 净利%s %s" % (
                r["code"], r["name"], rv.get("src"), rv.get("yi"), pf.get("src"), pf.get("yi")))


def main():
    ap = argparse.ArgumentParser(description="成长性筛选：抽取 PDF 财务数据与成长逻辑证据")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--root", "-o", default=ROOT_DEFAULT)
    e.add_argument("--since", default="2026-09-01")
    e.add_argument("--until", default="2026-12-31")
    e.add_argument("--out", default=OUT_DEFAULT)
    e.add_argument("--force", action="store_true", help="忽略已抽好的文本，重新读 PDF")
    e.set_defaults(func=build)
    c = sub.add_parser("check")
    c.add_argument("--out", default=OUT_DEFAULT)
    c.set_defaults(func=cmd_check)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
