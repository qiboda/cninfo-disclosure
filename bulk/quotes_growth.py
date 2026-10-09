# -*- coding: utf-8 -*-
"""给成长股筛选补「当下股价」维度。

数据源：腾讯行情 `qt.gtimg.cn`（快照，可一次批量）+ `web.ifzq.gtimg.cn`
（前复权日 K，用来算年初至今 / 近 60 日涨跌幅）。
产出 `_growth/quotes.json`，供 `rank_growth.py` / `report_growth.py` 消费。

为什么单独一层而不是塞进 rank_growth.py：行情是**会变**的、且必须能单独重跑。
把「哪天的价格」固定下来写进产物，报告才可复现。

为什么不用东方财富：`push2.eastmoney.com` 在连续请求后会给 IP 级限流，一律
`http.client.RemoteDisconnected: Remote end closed connection without response`，
间隔 5 秒重试 8 次、换 `push2delay.` / `82.push2.` / 去掉 `ut` 参数都不恢复。
腾讯行情同样免费、同样批量，且实测稳定（见 `probe_quote_tencent.py`）。

关键判断（这是这一层的意义所在）：
  预告/财报给的是**新的**盈利数字，而行情接口的 PE 用的是**旧的**盈利
  （静态用上年年报、TTM 用最近已披露的滚动十二个月）。所以必须自己算：
    * `pe_ttm` / `pe_static` / `pe_dyn` —— 市场当前看到的口径
    * `pe_fwd_3q`                      —— 市值 ÷ 本次前三季净利中值
    * `pe_fwd_year`                    —— 市值 ÷ 前三季年化净利（×4/3）
  三者的落差就是「成长有没有被价格反映」的直接证据：`pe_fwd_year` 远低于
  `pe_ttm`，说明市场还没按新盈利重估。

腾讯快照字段下标（0-based，已用东财年报库反推 PE(静) 逐只验证，见探针）：
  3 当前价 / 4 昨收 / 5 今开 / 6 成交量(手) / 30 时间
  31 涨跌额 / 32 涨跌幅% / 33 最高 / 34 最低 / 37 成交额(万) / 38 换手率%
  39 市盈率(TTM) / 44 流通市值(亿) / 45 总市值(亿) / 46 市净率
  47 涨停价 / 48 跌停价 / 49 量比 / 52 市盈率(动) / 53 市盈率(静)
  72 流通股本 / 73 总股本
验证：600176 总市值 1544.01 亿 ÷ 2025 年报归母 32.8546 亿 = 47.00 = [53] ✓
      300821 总市值 205.80 亿 ÷ 2025 年报归母 -0.1931 亿 = -1065.8 = [53] ✓
"""
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
GROWTH = os.path.join(_HERE, "_growth")

SNAP_URL = "https://qt.gtimg.cn/q="
KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
# 港股行情用港元计价，而公司财报用人民币 —— 不换算就会把市值/人民币利润直接相除，
# 力勤资源 001246 会因此得到 11.68 倍的假 PE（实际约 9.97 倍）。
FX_URL = "https://hq.sinajs.cn/list=HKDCNY"
FX_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"),
    "Referer": "https://finance.sina.com.cn/",
}
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"),
    "Referer": "https://gu.qq.com/",
}

# 已在其他市场上市的「A 股在审」标的：A 股代码查不到，改查它真正的上市地。
# 力勤资源 001246 是回 A 发行，本体在港交所（02245.HK）。
MARKET_ALIAS = {
    "001246": "hk02245",
}

# 腾讯快照下标
I_PRICE, I_PREV, I_OPEN, I_VOL = 3, 4, 5, 6
I_TIME = 30
I_CHG, I_CHG_PCT, I_HIGH, I_LOW = 31, 32, 33, 34
I_AMOUNT_WAN, I_TURNOVER, I_PE_TTM = 37, 38, 39
I_FLOAT_MV, I_TOTAL_MV, I_PB = 44, 45, 46
I_LIMIT_UP, I_LIMIT_DOWN, I_VOL_RATIO = 47, 48, 49
I_PE_DYN, I_PE_STATIC = 52, 53
I_FLOAT_SHARES, I_TOTAL_SHARES = 72, 73

IDX_NOTE = {
    "price": I_PRICE, "prev_close": I_PREV, "open": I_OPEN,
    "chg_pct": I_CHG_PCT, "high": I_HIGH, "low": I_LOW,
    "turnover_pct": I_TURNOVER, "pe_ttm": I_PE_TTM,
    "float_mv_yi": I_FLOAT_MV, "total_mv_yi": I_TOTAL_MV, "pb": I_PB,
    "pe_dyn": I_PE_DYN, "pe_static": I_PE_STATIC,
}


def market_symbol(code):
    """按代码前缀推腾讯的行情符号。

    实测：`sh` 沪市（60/68/69/900xxx），`sz` 深市（00/20/30xxxx），
    `bj` 北交所（4/8/920xxx），`hk` 港股（5 位、补零）。

    ⚠️ 北交所的 `92xxxx` 必须**先于**沪市判断 —— 早先写成
    `startswith(("60","68","69","9"))`，`920157` 被归成 `sh920157`，
    服务端返回 `v_pv_none_match="1"`，5 只北交所票全部判为「无行情」。
    """
    if code in MARKET_ALIAS:
        return MARKET_ALIAS[code]
    if code.startswith(("4", "8", "920")):
        return "bj" + code
    if code.startswith(("60", "68", "69", "900")):
        return "sh" + code
    if code.startswith(("00", "20", "30")):
        return "sz" + code
    return "sz" + code


def norm_name(name):
    """去掉「N」「C」「U」「ST」「*」等前后缀与空格，便于与清单里的简称比对。"""
    n = (name or "").replace(" ", "").replace("*", "").replace("-", "")
    for pre in ("N", "C", "U", "XD", "XR", "DR"):
        if n.startswith(pre) and len(n) > len(pre) + 1:
            n = n[len(pre):]
            break
    for suf in ("SW",):
        if n.endswith(suf) and len(n) > len(suf) + 1:
            n = n[:-len(suf)]
    return n


def name_match(want, got):
    """清单简称与行情简称是否同一家。

    不能拿前 3 字硬比：行情里新股的简称常短于招股书全称
    （920157 清单「宇特光电」/ 行情「N宇特」→ 去 N 后只有 2 字）。
    只要一个是另一个的前缀、或前 2 字相同，就认。
    """
    if not want or not got:
        return True
    if want.startswith(got) or got.startswith(want):
        return True
    return want[:2] == got[:2]


def _get(url, timeout=25, attempts=4):
    """带退避重试的 GET。腾讯也会偶发掐连接。"""
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            last = e
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
    raise last


def fetch_fx():
    """取 HKD→CNY 汇率（新浪财经，`hq.sinajs.cn/list=HKDCNY`）。

    腾讯行情没有汇率接口（`q=hkHKDCNY` 等一律返回 `v_pv_none_match="1"`）。
    港股标的的市值是港元、财报是人民币，必须换算后才能算 PE。
    返回 `{"rate": 0.8536, "date": "2026-10-09", ...}`；取不到时返回 rate=None，
    调用方必须显式降级（不能默认 1.0，那正是这个 bug 的来源）。
    """
    try:
        req = urllib.request.Request(FX_URL, headers=FX_HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            txt = resp.read().decode("gbk", "replace")
    except Exception as e:  # noqa: BLE001
        return {"rate": None, "error": "%s: %s" % (type(e).__name__, e)}
    m = re.search(r'"([^"]*)"', txt)
    if not m:
        return {"rate": None, "error": "无法解析响应: %s" % txt[:120]}
    parts = m.group(1).split(",")
    # 形如 `22:55:55,0.8536,0.8544,0.8543,21,0.8544,0.8544,0.8523,0.8536,港元人民币,2026-10-09`
    rate = date_s = None
    for p in parts:
        p = p.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", p):
            date_s = p
        elif rate is None and re.match(r"^\d\.\d+$", p):
            rate = float(p)
    return {"rate": rate, "date": date_s, "raw": m.group(1),
            "source": "新浪财经 hq.sinajs.cn/list=HKDCNY"}


def fetch_snapshot(codes):
    """批量取行情快照。返回 {code: {字段名: 值}}。"""
    codes = list(codes)
    out = {}
    for i in range(0, len(codes), 40):
        chunk = codes[i:i + 40]
        syms = [market_symbol(c) for c in chunk]
        raw = _get(SNAP_URL + ",".join(syms))
        text = raw.decode("gbk", "replace")
        by_sym = {}
        for line in text.strip().split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, val = line.partition("=")
            by_sym[key.strip().lstrip("v_")] = val.strip().strip('"').split("~")
        for c, sym in zip(chunk, syms):
            p = by_sym.get(sym)
            if not p or len(p) < 50 or not (p[I_PRICE] or "").strip():
                continue
            out[c] = _parse_row(p)
        if i + 40 < len(codes):
            time.sleep(0.4)
    return out


def _f(p, i):
    if i >= len(p):
        return None
    v = (p[i] or "").strip()
    if v in ("", "-", "—"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_row(p):
    rec = {"name_quote": p[1], "code_quote": p[2]}
    for name, i in IDX_NOTE.items():
        rec[name] = _f(p, i)
    # 0 / 负值都是「没有意义」的占位：港股（力勤资源）PE 动/静返回 0.0，
    # 上年亏损的公司 PE 静为负。留 0 会让人误读成「PE=0」。
    for k in ("pe_dyn", "pe_static", "pe_ttm"):
        if rec.get(k) is not None and rec[k] <= 0:
            rec[k] = None
    rec["amount_yi"] = round(_f(p, I_AMOUNT_WAN) / 1e4, 4) if _f(p, I_AMOUNT_WAN) else None
    rec["time"] = (p[I_TIME] if I_TIME < len(p) else "") or ""
    rec["float_shares"] = _f(p, I_FLOAT_SHARES)
    rec["total_shares"] = _f(p, I_TOTAL_SHARES)
    if rec.get("prev_close") == rec.get("price"):
        rec["unlisted_or_suspended"] = True
    return rec


def fetch_kline(symbol, start, end, count=700):
    """前复权日 K。返回 [[date, open, close, high, low, volume], ...]（升序）。"""
    url = "%s?param=%s,day,%s,%s,%d,qfq" % (KLINE_URL, symbol, start, end, count)
    j = json.loads(_get(url).decode("utf-8"))
    d = (j.get("data") or {}).get(symbol) or {}
    rows = d.get("qfqday") or d.get("day") or []
    return rows


def price_trend(symbol, today):
    """算年初至今 / 近 60 日涨跌幅（%）。返回 dict，缺数据则字段为 None。"""
    start = "%d-11-01" % (today.year - 1)
    try:
        rows = fetch_kline(symbol, start, today.isoformat())
    except Exception as e:  # noqa: BLE001
        return {"trend_error": "%s: %s" % (type(e).__name__, e)}
    if not rows:
        return {}
    closes = []
    for r in rows:
        try:
            closes.append((r[0], float(r[2])))
        except (IndexError, ValueError):
            continue
    if len(closes) < 2:
        return {}
    last_date, last = closes[-1]
    out = {"trend_last_date": last_date, "trend_last_close": last}

    ytd_base = None
    for d, c in closes:
        if d < "%d-01-01" % today.year:
            ytd_base = c
        else:
            break
    if ytd_base:
        out["chg_ytd_pct"] = round((last / ytd_base - 1.0) * 100.0, 2)
        out["ytd_base_date"] = [d for d, c in closes if c == ytd_base][-1]

    if len(closes) > 60:
        base60 = closes[-61][1]
        out["chg_60d_pct"] = round((last / base60 - 1.0) * 100.0, 2)
        out["d60_base_date"] = closes[-61][0]
    return out


def _range_from_note(note):
    """从 `profit_note`（形如 `5.47~5.67` 或 `0.215`）解析出区间（亿元）。"""
    if not note:
        return None
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(note).replace(",", ""))
    vals = [float(x) for x in nums]
    if len(vals) >= 2:
        return min(vals[0], vals[1]), max(vals[0], vals[1])
    if len(vals) == 1:
        return vals[0], vals[0]
    return None


def prog_3q_yi(row):
    """本次披露的「前三季」净利中值（亿元）。**按 source 分流**，不能一把抓。

    - `业绩预告`：`profit_note` 是区间（`5.47~5.67`），取中值；
    - `定期报告`：`profit_note` 可能是「扣非0.9065亿」这种另一口径的注，
      必须直接用 `profit_yi`（归母累计数）；
    - `招股书三年财务`：`profit_note` 是三个**完整年度**（`0.3497 / 0.7147 / 2.691`），
      根本没有「前三季」概念 —— 早先误取前两个数取平均（301716 鸿富诚因此
      算出 PE前3Q=761.61），这里直接返回 None，改由 `pe_last_annual` 承接。
    """
    src = (row.get("source") or "").strip()
    if src == "招股书三年财务":
        return None
    if src == "业绩预告":
        rr = _range_from_note(row.get("profit_note"))
        if rr:
            return sum(rr) / 2.0
    try:
        v = float(row.get("profit_yi") or "")
    except ValueError:
        return None
    return v if v else None


def last_annual_yi(row):
    """最近一个**完整会计年度**的净利（亿元）。

    **只有招股书行有这个数**：它的 `profit_yi` 就是三年里的最后一年（最近完整年度）。
    业绩预告 / 三季报行的 `profit_yi` 是**本次披露的前三季累计数**，不是完整年度 ——
    早先不加区分地返回它，导致 600176 中国巨石的 `pe_last_annual` 被算成 29.33
    （与 `pe_fwd_3q` 重复），而市场口径的静态 PE 是 **47.0**（= 1544.01 / 2025 年报 32.8546）。
    完整年度净利只能来自行情接口的 `pe_static` 反推：市值 ÷ pe_static。
    """
    if (row.get("source") or "").strip() != "招股书三年财务":
        return None
    try:
        v = float(row.get("profit_yi") or "")
    except ValueError:
        return None
    return v if v else None


def compute_pe(rows, quotes, fx=None):
    """由 `rank_growth.csv` 的财务 + 行情快照派生全部估值字段（无网络副作用）。"""
    for r in rows:
        q = quotes.get(r["code"])
        if not q:
            continue
        # ── 币种归一到人民币 ──
        # 港股行情是港元，而公司财报是人民币。不换算就会把 334 亿港元
        # 直接除以 28.62 亿人民币，得到 11.68 倍的假 PE（实际约 9.97 倍）。
        mv_raw = q.get("total_mv_yi")
        rate = (fx or {}).get("rate")
        is_hk = market_symbol(r["code"]).startswith("hk")
        if is_hk and mv_raw and rate:
            mv_yi = round(mv_raw * rate, 4)
            q["total_mv_cny_yi"] = mv_yi
            q["fx_note"] = ("行情 %s 亿港元 × HKD/CNY %s（%s）→ %s 亿人民币"
                            % (mv_raw, rate, (fx or {}).get("date") or "?", mv_yi))
        else:
            mv_yi = mv_raw
            q["total_mv_cny_yi"] = mv_raw
            if is_hk:
                q["fx_note"] = "⚠️ 未取到 HKD/CNY 汇率，市值仍为港元，PE 不可信"
        prof_3q = prog_3q_yi(r)
        q["profit_3q_yi"] = round(prof_3q, 4) if prof_3q else None
        if mv_yi and prof_3q and prof_3q > 0:
            q["pe_fwd_3q"] = round(mv_yi / prof_3q, 2)
            q["pe_fwd_year"] = round(mv_yi / (prof_3q * 4.0 / 3.0), 2)
        else:
            q["pe_fwd_3q"] = None
            q["pe_fwd_year"] = None
        last = last_annual_yi(r)
        q["profit_last_annual_yi"] = last
        q["pe_last_annual"] = (round(mv_yi / last, 2) if mv_yi and last and last > 0
                               else None)
        # 由行情自带的静态 PE 反推「最近完整年度」净利，供所有行参考
        if mv_yi and q.get("pe_static") and q["pe_static"] > 0:
            q["profit_static_yi"] = round(mv_yi / q["pe_static"], 4)
        else:
            q["profit_static_yi"] = None
        # 估值提示：亏损股给 PE 只会误导
        if q.get("pe_ttm") is None:
            q["pe_flag"] = "亏损或无可比 PE"
        elif q["pe_ttm"] >= 100:
            q["pe_flag"] = "PE 三位数（高估或利润处于低点）"
        elif q.get("pe_fwd_year") and q["pe_fwd_year"] < q["pe_ttm"] * 0.6:
            q["pe_flag"] = "前瞻 PE 明显低于 TTM —— 市场尚未按新盈利重估"
        else:
            q["pe_flag"] = ""
    return quotes


def build(root=GROWTH, with_trend=True):
    csv_path = os.path.join(root, "rank_growth.csv")
    with io.open(csv_path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    codes = [r["code"] for r in rows]

    print("查询 %d 只的行情快照（腾讯 qt.gtimg.cn）…" % len(codes))
    raw = fetch_snapshot(codes)

    quotes, mismatched, missing = {}, [], []
    for r in rows:
        code, want = r["code"], norm_name(r["name"])
        q = raw.get(code)
        if not q:
            missing.append(code)
            continue
        got = norm_name(q.get("name_quote"))
        if not name_match(want, got):
            mismatched.append((code, r["name"], q.get("name_quote")))
            continue
        quotes[code] = q

    if with_trend:
        today = date.today()
        for n, code in enumerate(sorted(quotes), 1):
            sym = market_symbol(code)
            tr = price_trend(sym, today)
            quotes[code].update(tr)
            flag = "" if "trend_error" not in tr else "  (走势取数失败)"
            print("  [%2d/%2d] %-6s %-6s 年初至今=%s%%  近60日=%s%%%s" % (
                n, len(quotes), code, sym,
                tr.get("chg_ytd_pct"), tr.get("chg_60d_pct"), flag))
            time.sleep(0.25)

    # ── 汇率（港股标的必须换算，否则 PE 是错的）──
    fx = fetch_fx()
    if fx.get("rate"):
        print("HKD/CNY = %s（%s，%s）" % (fx["rate"], fx.get("date"), fx.get("source")))
    else:
        print("⚠️ HKD/CNY 取数失败：%s —— 港股标的的 PE 将不可信" % fx.get("error"))

    # ── 自算前瞻 PE ──
    compute_pe(rows, quotes, fx)

    # 港股口径提醒
    for code, q in quotes.items():
        if market_symbol(code).startswith("hk"):
            q["currency_note"] = "港股，市值/价格以港元计价；PE 已按 HKD/CNY 换算为人民币口径"

    payload = {
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "腾讯行情 qt.gtimg.cn（快照）+ web.ifzq.gtimg.cn（前复权日 K）"
                  " + 新浪财经 hq.sinajs.cn（HKD/CNY 汇率）",
        "fx": fx,
        "field_notes": {
            "price": "最新价", "prev_close": "昨收", "chg_pct": "当日涨跌幅%",
            "pe_dyn": "市盈率(动态，按最新季度年化)",
            "pe_static": "市盈率(静态，按上年年报)",
            "pe_ttm": "市盈率(TTM，按最近已披露的滚动十二个月)",
            "pb": "市净率", "total_mv_yi": "总市值(亿)", "float_mv_yi": "流通市值(亿)",
            "turnover_pct": "换手率%",
            "chg_ytd_pct": "年初至今涨跌幅%（以去年最后一个交易日收盘为基准）",
            "chg_60d_pct": "近 60 个交易日涨跌幅%",
            "pe_fwd_3q": "总市值 ÷ 本次前三季净利(预告中值)",
            "pe_fwd_year": "总市值 ÷ (本次前三季净利 × 4/3)，线性年化",
            "pe_last_annual": "总市值 ÷ 最近完整年度净利。**只有招股书行有值** —— "
                              "预告/季报行没有完整年度净利，故为 None",
            "profit_static_yi": "由行情静态 PE 反推的最近完整年度净利(亿)：市值 ÷ pe_static",
            "total_mv_cny_yi": "归一到人民币后的总市值(亿)。港股行 = 港元市值 × HKD/CNY；"
                               "其余等于 total_mv_yi",
            "fx_note": "币种换算说明（港股行才有）",
        },
        "index_map": IDX_NOTE,
        "quotes": quotes,
        "no_quote": missing,
        "name_mismatch": mismatched,
    }
    out = os.path.join(root, "quotes.json")
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    print("拿到行情 %d / %d 只 → %s" % (len(quotes), len(codes), out))
    if missing:
        print("  无行情（多为一二级市场尚无交易，如未上市）: %s" % ",".join(missing))
    if mismatched:
        print("  ⚠️ 名称不符已剔除：")
        for c, a, b in mismatched:
            print("     %s 清单=%s 行情=%s" % (c, a, b))
    return payload


def view(root=GROWTH):
    path = os.path.join(root, "quotes.json")
    with io.open(path, encoding="utf-8") as fh:
        j = json.load(fh)
    print("快照时间：%s" % j["fetched_at"])
    print("数据源：%s" % j["source"])
    hdr = ("%-8s %-11s %9s %7s %7s %7s %7s %8s %8s %8s %8s" % (
        "代码", "名称", "总市值亿", "PE动", "PE静", "PE_TTM", "PB",
        "PE前3Q", "PE年化", "年初至今%", "近60日%"))
    print(hdr)
    print("-" * len(hdr))
    for code, q in sorted(j["quotes"].items(),
                          key=lambda kv: -(kv[1].get("total_mv_yi") or 0)):
        print("%-8s %-11s %9s %7s %7s %7s %7s %8s %8s %8s %8s" % (
            code, (q.get("name_quote") or "")[:10], q.get("total_mv_yi"),
            q.get("pe_dyn"), q.get("pe_static"), q.get("pe_ttm"), q.get("pb"),
            q.get("pe_fwd_3q"), q.get("pe_fwd_year"),
            q.get("chg_ytd_pct"), q.get("chg_60d_pct")))
    if j.get("no_quote"):
        print()
        print("无行情（尚未上市或停牌）：%s" % ",".join(j["no_quote"]))
    return 0


def recompute(root=GROWTH):
    """不联网：只用已有的 `quotes.json` + `rank_growth.csv` 重算估值字段。

    改过 `prog_3q_yi` / `last_annual_yi` 的口径后，用它免去重新抓行情的代价
    （也避免反复打腾讯接口）。
    """
    path = os.path.join(root, "quotes.json")
    with io.open(path, encoding="utf-8") as fh:
        j = json.load(fh)
    with io.open(os.path.join(root, "rank_growth.csv"), encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    fx = j.get("fx")
    if not fx or not fx.get("rate"):
        print("本地没有汇率记录，联网取一次 HKD/CNY …")
        fx = fetch_fx()
        if fx.get("rate"):
            j["fx"] = fx
    compute_pe(rows, j["quotes"], fx)
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump(j, fh, ensure_ascii=False, indent=1)
    print("已重算 %d 只的估值字段（快照仍为 %s，HKD/CNY=%s）→ %s"
          % (len(j["quotes"]), j["fetched_at"], (fx or {}).get("rate"), path))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build(with_trend="--no-trend" not in sys.argv)
    elif cmd == "recompute":
        recompute()
    elif cmd == "view":
        view()
    else:
        raise SystemExit("用法: quotes_growth.py [build|recompute|view] [--no-trend]")
