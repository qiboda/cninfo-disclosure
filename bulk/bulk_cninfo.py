#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cninfo-disclosure 批量驱动器 —— 下载 A 股 2022 年至今的
全部定期报告（年报 / 半年报 / 一季报 / 三季报）与 IPO 招股说明书。

复用 scripts/ 下的底座与筛选规则：
  cninfo_client.query_by_stock  ← 按「代码,orgId」精确定位 + seDate 日期范围
  reports.REPORT_TYPES / filter_report
  prospectus.filter_prospectus / detect_board

特性：
  - 全 A 股自动枚举（沪深主板 / 创业板 / 科创板 / 北交所，排除 B 股）
  - 并发下载（默认 6 线程）+ 失败重试 + 断点续传（state JSONL）
  - 落盘目录：{root}/reports/{年份}/{类型}/ 与 {root}/prospectus/
  - 产出 manifest.csv 清单

用法：
  python bulk_cninfo.py survey --root D:\\cninfo --sample 40      # 抽测规模（不下载）
  python bulk_cninfo.py run    --root D:\\cninfo --sample 30      # 小样本试跑
  python bulk_cninfo.py run    --root D:\\cninfo                   # 全量
"""

import argparse
import csv
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

from cninfo_client import (  # noqa: E402
    DEFAULT_TIMEOUT,
    DownloadError,
    detect_column,
    download_pdf,
    query_by_stock,
    safe_filename,
)
from reports import REPORT_TYPES, filter_report  # noqa: E402
from prospectus import detect_board, filter_prospectus  # noqa: E402

UNIVERSE_URL = "http://www.cninfo.com.cn/new/data/szse_stock.json"
UNIVERSE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)

# 报告类型 → 覆盖的报告年度（"2022 年到现在"按财报所属年度口径）
DEFAULT_YEARS = {
    "annual": [2022, 2023, 2024, 2025],
    "semi": [2022, 2023, 2024, 2025, 2026],
    "q1": [2022, 2023, 2024, 2025, 2026],
    "q3": [2022, 2023, 2024, 2025, 2026],
}

PROSPECTUS_FROM = "2022-01-01"
PROSPECTUS_TO = "2099-12-31"

_print_lock = threading.Lock()
# 由启动器设置：日志同时写入该 UTF-8 文件（shell 重定向会把中文写成乱码）
_LOG_FILE = os.environ.get("CNINFO_LOG")


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with _print_lock:
        print(line, flush=True)
        if _LOG_FILE:
            try:
                with open(_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass


# ─── 股票池 ─────────────────────────────────────────────────

def _dedup_legacy(stocks):
    """
    去掉北交所「旧代码」重复条目。

    实测：同一家北交所公司会同时存在旧代码（430xxx / 83xxxx / 87xxxx）与新代码
    （920xxx），两者公告集合完全相同（抽验 30/30 完全一致）；转板公司（如
    833874 泰祥股份 → 301192）则是旧码保留历史、新码承载现况。
    因此：若某简称同时出现在「旧码段」和「非旧码段」，丢弃旧码条目。
    实测「同简称且都在旧码段」的组数为 0，故该规则无歧义。
    """
    by_name = {}
    for s in stocks:
        by_name.setdefault(s["name"], []).append(s)

    kept = []
    dropped = []
    for name, lst in by_name.items():
        if len(lst) == 1:
            kept.append(lst[0])
            continue
        legacy = [s for s in lst if s["code"].startswith(("4", "8"))]
        modern = [s for s in lst if not s["code"].startswith(("4", "8"))]
        if legacy and modern:
            kept.extend(modern)
            dropped.extend(legacy)
        else:
            kept.extend(lst)
    return sorted(kept, key=lambda x: x["code"]), dropped


def load_universe(root, refresh=False):
    """加载全市场股票池（含沪深主板/创业板/科创板/北交所），排除 B 股，去除旧码重复。"""
    cache = os.path.join(root, "_state", "universe.json")
    os.makedirs(os.path.dirname(cache), exist_ok=True)

    if os.path.exists(cache) and not refresh:
        age_days = (time.time() - os.path.getmtime(cache)) / 86400
        if age_days < 7:
            with open(cache, "r", encoding="utf-8") as f:
                raw = json.load(f)
            kept, dropped = _dedup_legacy(raw)
            return kept

    req = urllib.request.Request(
        UNIVERSE_URL, headers={"User-Agent": UNIVERSE_UA, "Referer": "http://www.cninfo.com.cn/"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    stocks = []
    for s in data.get("stockList", []):
        code = s.get("code", "")
        if not code or len(code) != 6 or not code.isdigit():
            continue
        if s.get("category") != "A股":          # 排除 B 股等
            continue
        col = detect_column(code)
        if col is None:
            continue
        stocks.append({
            "code": code,
            "name": s.get("zwjc") or code,
            "orgId": s.get("orgId") or "",
            "column": col,
            "stock_param": f"{code},{s.get('orgId') or ''}",
        })

    with open(cache, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False)

    kept, dropped = _dedup_legacy(stocks)
    return kept


# ─── 查询（带重试） ─────────────────────────────────────────

def query_retry(stock_param, column, start, end, category="", searchkey="",
                attempts=3, timeout=DEFAULT_TIMEOUT, page_size=30, max_pages=40):
    last = None
    for i in range(attempts):
        try:
            return query_by_stock(
                stock_param, column, start, end,
                category=category, searchkey=searchkey,
                page_size=page_size, max_pages=max_pages, timeout=timeout,
            )
        except Exception as e:  # noqa: BLE001 —— 含 TimeoutError/SSL/连接重置等
            last = e
            time.sleep(1.2 * (i + 1) + random.random())
    raise DownloadError(f"{type(last).__name__}: {last}")


def download_retry(pdf_url, out_dir, filename, attempts=3, timeout=120):
    last = None
    for i in range(attempts):
        try:
            return download_pdf(pdf_url, out_dir, filename, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.2 * (i + 1) + random.random())
    raise DownloadError(f"{type(last).__name__}: {last}")


# ─── 单个任务 ───────────────────────────────────────────────

def pick_report_target(anns, rtype, year):
    """在候选公告中挑正本。

    先按「标题含目标年份」筛（防止跨年串档），挑不到再放宽到全年份——
    因为存在标题不含年份的正本（实测：锦江酒店正本标题就是「锦江酒店年报」）。
    seDate 已经限定了披露窗口，放宽年份不会引入跨年文档。
    """
    dated = [a for a in anns if str(year) in a["title"]]
    target = filter_report(dated, report_type=rtype) if dated else None
    if target is None:
        target = filter_report(anns, report_type=rtype)
    return target


def do_report_task(stock, rtype, year, root, timeout):
    """下载一只股票某一年的某类定期报告。返回状态 dict。"""
    rt = REPORT_TYPES[rtype]
    start, end = rt["date_range"](year)

    anns = query_retry(stock["stock_param"], stock["column"], start, end,
                       category=rt["category"], timeout=timeout)
    target = pick_report_target(anns, rtype, year)

    # 兜底：巨潮对部分公司（如中国联通/东方证券/四川成渝）把年报正本归到了
    # 年报 category 之外，带 category 查只能拿到「摘要」。去掉 category、
    # 改用 searchkey 全文检索才能捞到正本。仅在主查询无果时才发起，避免翻倍开销。
    if target is None:
        try:
            more = query_retry(stock["stock_param"], stock["column"], start, end,
                               category="", searchkey=rt["search_key"], timeout=timeout)
        except DownloadError:
            more = []
        if more:
            seen = {a["adjunct_url"] for a in anns}
            merged = list(anns) + [a for a in more if a["adjunct_url"] not in seen]
            target = pick_report_target(merged, rtype, year)

    if target is None:
        return {"status": "empty",
                "reason": "未找到公告" if not anns else "仅摘要/更正版"}

    out_dir = os.path.join(root, "reports", str(year), rtype)
    filename = safe_filename(f"{stock['code']}_{stock['name']}_{year}{rt['filename_suffix']}.pdf")
    filepath = os.path.join(out_dir, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
        return {
            "status": "ok", "cached": True, "path": filepath,
            "size": os.path.getsize(filepath), "title": target["title"],
            "date": target["date"], "pdf_url": target["pdf_url"],
        }

    res = download_retry(target["pdf_url"], out_dir, filename, timeout=timeout)
    return {
        "status": "ok", "cached": False, "path": res["filepath"],
        "size": res["size_bytes"], "title": target["title"],
        "date": target["date"], "pdf_url": target["pdf_url"],
    }


def do_prospectus_task(stock, root, timeout):
    """下载一只股票的 IPO 招股说明书（仅 2022 年至今披露的）。

    必须带 searchkey：该场景没有 category，若 searchkey 也为空，巨潮接口会
    退化成「最新 30 条且 hasMore=False」，导致招股书永远检索不到。
    """
    anns = query_retry(stock["stock_param"], stock["column"],
                       PROSPECTUS_FROM, PROSPECTUS_TO,
                       category="", searchkey="招股说明书",
                       timeout=timeout, page_size=30, max_pages=10)
    if not anns:
        return {"status": "empty", "reason": "窗口内无公告"}

    target = filter_prospectus(anns)
    if not target:
        return {"status": "empty", "reason": "无首发招股书正本"}

    out_dir = os.path.join(root, "prospectus")
    filename = safe_filename(f"{stock['code']}_{stock['name']}_招股说明书.pdf")
    filepath = os.path.join(out_dir, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
        return {
            "status": "ok", "cached": True, "path": filepath,
            "size": os.path.getsize(filepath), "title": target["title"],
            "date": target["date"], "board": detect_board(target["title"]),
            "pdf_url": target["pdf_url"],
        }

    res = download_retry(target["pdf_url"], out_dir, filename, timeout=timeout)
    return {
        "status": "ok", "cached": False, "path": res["filepath"],
        "size": res["size_bytes"], "title": target["title"],
        "date": target["date"], "board": detect_board(target["title"]),
        "pdf_url": target["pdf_url"],
    }


def run_task(task, root, timeout):
    stock, kind, rtype, year = task
    key = f"{stock['code']}|{'prospectus' if kind == 'prospectus' else rtype}|{year or '-'}"
    try:
        if kind == "prospectus":
            res = do_prospectus_task(stock, root, timeout)
        else:
            res = do_report_task(stock, rtype, year, root, timeout)
    except DownloadError as e:
        res = {"status": "fail", "reason": e.message}
    except Exception as e:  # noqa: BLE001
        res = {"status": "fail", "reason": f"{type(e).__name__}: {e}"}
    res.update({"key": key, "code": stock["code"], "name": stock["name"],
                "kind": kind, "year": year, "at": datetime.now().isoformat(timespec="seconds")})
    return res


# ─── 状态（断点续传） ───────────────────────────────────────

class State:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.records = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # 失败记录允许重试，其余视为已完成
                    if rec.get("status") != "fail":
                        self.records[rec.get("key")] = rec
        self.fh = open(path, "a", encoding="utf-8")

    def done(self, key):
        return key in self.records

    def add(self, rec):
        with self.lock:
            self.records[rec["key"]] = rec
            self.fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.fh.flush()

    def close(self):
        self.fh.close()


# ─── 主流程 ─────────────────────────────────────────────────

def build_tasks(stocks, types, years_map, with_prospectus):
    tasks = []
    for s in stocks:
        for rtype in types:
            for y in years_map[rtype]:
                tasks.append((s, "report", rtype, y))
        if with_prospectus:
            tasks.append((s, "prospectus", None, None))
    return tasks


def write_manifest(root, state):
    rows = [r for r in state.records.values() if r.get("status") == "ok"]
    rows.sort(key=lambda r: (str(r.get("year") or ""), r.get("kind"), r["code"]))
    path = os.path.join(root, "manifest.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "kind", "year", "title", "date",
                    "size_bytes", "board", "filepath", "pdf_url"])
        for r in rows:
            w.writerow([r.get("code"), r.get("name"), r.get("kind"), r.get("year") or "",
                        r.get("title", ""), r.get("date", ""), r.get("size", ""),
                        r.get("board") or "", r.get("path", ""), r.get("pdf_url", "")])
    return path, len(rows)


def cmd_run(args):
    root = os.path.abspath(args.root)
    for sub in ("reports", "prospectus", "_state"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)

    stocks = load_universe(root, refresh=args.refresh_universe)
    if args.codes:
        want = {c.strip() for c in args.codes.split(",") if c.strip()}
        stocks = [s for s in stocks if s["code"] in want]
    if args.sample:
        random.seed(args.seed)
        stocks = random.sample(stocks, min(args.sample, len(stocks)))

    types = [t for t in (args.types.split(",") if args.types else list(DEFAULT_YEARS)) if t]
    override_years = [int(y) for y in args.years.split(",")] if args.years else None
    years_map = {t: (override_years if override_years else DEFAULT_YEARS[t]) for t in types}

    tasks = build_tasks(stocks, types, years_map, with_prospectus=not args.no_prospectus)
    if args.report_only:
        tasks = [t for t in tasks if t[1] == "report"]
    if args.prospectus_only:
        tasks = [t for t in tasks if t[1] == "prospectus"]

    state = State(os.path.join(root, "_state", "done.jsonl"))
    pending = [t for t in tasks if not state.done(run_key(t))]

    log(f"股票池 {len(stocks)} 只 | 任务 {len(tasks)} 个 | 待办 {len(pending)} 个 "
        f"| 并发 {args.workers} | 落盘 {root}")
    if args.dry_run:
        log("--dry-run：仅统计，不执行")
        return

    done = ok = empty = fail = 0
    bytes_total = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_task, t, root, args.timeout): t for t in pending}
        for fut in as_completed(futs):
            rec = fut.result()
            state.add(rec)
            done += 1
            if rec["status"] == "ok":
                ok += 1
                bytes_total += rec.get("size", 0) or 0
            elif rec["status"] == "empty":
                empty += 1
            else:
                fail += 1

            if done % args.progress == 0 or done == len(pending):
                el = time.time() - t0
                rate = done / el if el else 0
                eta = (len(pending) - done) / rate / 3600 if rate else 0
                log(f"{done}/{len(pending)} ok={ok} empty={empty} fail={fail} "
                    f"{bytes_total/1e9:.1f}GB {rate:.2f}任务/秒 ETA {eta:.1f}h")

    path, n = write_manifest(root, state)
    state.close()
    log(f"完成：成功 {ok} / 空 {empty} / 失败 {fail}，共 {bytes_total/1e9:.2f}GB")
    log(f"清单：{path}（{n} 条）")


def run_key(task):
    stock, kind, rtype, year = task
    return f"{stock['code']}|{'prospectus' if kind == 'prospectus' else rtype}|{year or '-'}"


def cmd_survey(args):
    """抽样实测：不下载，只统计各类型/年份的可得数量与公告总量。"""
    root = os.path.abspath(args.root)
    os.makedirs(os.path.join(root, "_state"), exist_ok=True)
    stocks = load_universe(root, refresh=args.refresh_universe)
    random.seed(args.seed)
    sample = random.sample(stocks, min(args.sample, len(stocks)))
    log(f"股票池 {len(stocks)} 只；抽样 {len(sample)} 只做规模测算")

    stats = {}
    for rtype, rt in REPORT_TYPES.items():
        for year in DEFAULT_YEARS[rtype]:
            stats[(rtype, year)] = {"n": 0, "hits": 0, "bytes": 0}

    def one(s):
        out = []
        for rtype, rt in REPORT_TYPES.items():
            for year in DEFAULT_YEARS[rtype]:
                start, end = rt["date_range"](year)
                try:
                    anns = query_retry(s["stock_param"], s["column"], start, end,
                                       category=rt["category"], timeout=args.timeout)
                except Exception:  # noqa: BLE001
                    continue
                anns = [a for a in anns if str(year) in a["title"]]
                tgt = filter_report(anns, report_type=rtype) if anns else None
                out.append((rtype, year, len(anns), tgt))
        # 招股书（无 category，必须带 searchkey）
        try:
            panns = query_retry(s["stock_param"], s["column"], PROSPECTUS_FROM,
                                PROSPECTUS_TO, category="", searchkey="招股说明书",
                                timeout=args.timeout, page_size=30, max_pages=10)
            ptgt = filter_prospectus(panns) if panns else None
        except Exception:  # noqa: BLE001
            panns, ptgt = [], None
        out.append(("prospectus", None, len(panns), ptgt))
        return out

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, rows in enumerate(pool.map(one, sample), 1):
            for rtype, year, n, tgt in rows:
                key = (rtype, year)
                stats.setdefault(key, {"n": 0, "hits": 0, "bytes": 0})
                stats[key]["n"] += 1
                if tgt:
                    stats[key]["hits"] += 1
            if i % 10 == 0:
                log(f"抽测 {i}/{len(sample)}")

    print("\n" + "=" * 78)
    print(f"抽样 {len(sample)} 只股票的可得率（样本内命中数 / 样本数）")
    print("=" * 78)
    print(f"{'类型':<14}{'财报年':<8}{'命中':<10}{'命中率':<10}")
    for rtype in list(REPORT_TYPES) + ["prospectus"]:
        years = DEFAULT_YEARS.get(rtype, [None])
        for year in years:
            st = stats.get((rtype, year))
            if not st or st["n"] == 0:
                continue
            print(f"{rtype:<14}{str(year or '-'):<8}{st['hits']:<10}"
                  f"{st['hits']/st['n']*100:.1f}%")

    total_stocks = len(stocks)
    est_files = 0
    for (rtype, year), st in stats.items():
        if rtype == "prospectus":
            continue
        rate = st["hits"] / st["n"] if st["n"] else 0
        est_files += rate * total_stocks
    pst = stats.get(("prospectus", None))
    if pst and pst["n"]:
        est_files += pst["hits"] / pst["n"] * total_stocks

    print("\n" + "=" * 78)
    print(f"全市场预估文件数 ≈ {int(est_files):,} 个"
          f"（{total_stocks} 只股票 × 各类型可得出率）")
    print("=" * 78)
    print("注：体积与耗时需实际下载若干样本后按平均大小/速率外推。")


def build_parser():
    p = argparse.ArgumentParser(description="cninfo-disclosure 批量下载驱动器")
    sub = p.add_subparsers(dest="command", required=True)

    for name, helptext in (("run", "执行下载"), ("survey", "抽样规模测算")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--root", "-o", default=r"D:\cninfo", help="落盘根目录")
        sp.add_argument("--workers", type=int, default=6, help="并发线程数（默认 6）")
        sp.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="请求超时秒数")
        sp.add_argument("--sample", type=int, default=0, help="随机抽样 N 只股票")
        sp.add_argument("--seed", type=int, default=42, help="抽样随机种子")
        sp.add_argument("--codes", type=str, default="", help="指定股票代码，逗号分隔")
        sp.add_argument("--refresh-universe", action="store_true", help="强制刷新股票池")
        if name == "run":
            sp.add_argument("--types", type=str, default="", help="annual,semi,q1,q3")
            sp.add_argument("--years", type=str, default="", help="覆盖财报年度，如 2022,2023")
            sp.add_argument("--no-prospectus", action="store_true", help="不下载招股书")
            sp.add_argument("--prospectus-only", action="store_true", help="只下载招股书")
            sp.add_argument("--report-only", action="store_true", help="只下载财报")
            sp.add_argument("--progress", type=int, default=50, help="每 N 个任务打印进度")
            sp.add_argument("--dry-run", action="store_true", help="只统计不执行")
    return p


def main():
    args = build_parser().parse_args()
    if args.workers < 1:
        raise SystemExit("--workers 必须 >= 1")
    if args.command == "run":
        if args.prospectus_only and args.report_only:
            raise SystemExit("--prospectus-only 与 --report-only 不能同时使用")
        cmd_run(args)
    else:
        cmd_survey(args)


if __name__ == "__main__":
    main()
