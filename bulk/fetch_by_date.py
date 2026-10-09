#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_by_date.py · 按「披露日期」归档巨潮增量文档

用户口径：
    把最新一批【定期报告】（默认 2026 年三季报）、【IPO 招股说明书】与
    【业绩预告】下载到 {root}/by_date/{YYYY-MM-DD}/{财报|IPO|业绩预告}/ 下，
    目录名即该文件的披露日期 —— 一眼看出哪天发布。
    三季报额外镜像一份到既有结构 {root}/reports/{年}/q3/ 并追加进 manifest.csv，
    让原数据集口径同样完整（镜像用硬链接，不额外占空间）。

流（--streams，逗号分隔）：
    q3    三季报正本       → by_date/{日期}/财报/       （额外镜像进 reports/{年}/q3/）
    ipo   首发招股说明书   → by_date/{日期}/IPO/
    yjyg  业绩预告族       → by_date/{日期}/业绩预告/   （预告/预增/预盈/预减/预亏/预平，含修正稿）
    yjkb  业绩快报         → by_date/{日期}/业绩快报/   （默认不启用）

与 bulk_cninfo.py 的分工：
    bulk_cninfo.py = 全量/存量抓取（5,927 只股票 × 类型 × 年份 → reports/{年}/{类}/）
    本脚本         = 增量/按日期抓取（全市场 + seDate 单日检索 → by_date/{日期}/…）

为什么按「单日」检索，而不是一个大区间：
    1) 巨潮 pageSize 上限是 30，大区间（如整个三季报季约 5,400 份）会撞分页上限，
       而单日量级最大约 1,700 条，可控；
    2) 单日检索天然带出「披露日期」，直接映射到目录名，不需要额外反查；
    3) 增量友好 —— 重复运行只会补新日期的数据，已存在文件自动跳过。

巨潮接口要点（踩过的坑，勿改）：
    - 日期参数真名是 seDate，格式 "起~止"（波浪号）；传 startDate/endDate 会被静默忽略。
    - 必须带 X-Requested-With / Referer，否则被反爬。
    - searchkey 与 category 同时为空 → 退化成「最新 30 条且 hasMore=False」。
      招股书没有 category，必须给 searchkey="招股说明书"。
    - stock 为空时 column 参数被忽略（三列返回完全相同），故全市场只需查一次。

用法：
    python fetch_by_date.py run --root "C:\\Users\\iq112\\Documents\\cninfo" \
        --since 2026-09-01 --until 2026-10-10 --report-year 2026
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

from cninfo_client import (  # noqa: E402
    CNINFO_PDF_BASE,
    CNINFO_QUERY_URL,
    DEFAULT_TIMEOUT,
    QUERY_HEADERS,
    DownloadError,
    download_pdf,
    safe_filename,
)
from prospectus import detect_board, filter_prospectus  # noqa: E402
from reports import EXCLUDE_KEYWORDS, REPORT_TYPES, filter_report  # noqa: E402

PAGE_SIZE = 30          # 巨潮服务端硬上限
# 单次「区间检索」的翻页上限。250 × 30 = 7500 条 —— 一整年的三季报（约 5,400 份
# = 180 页）能一次装下；装不下时 `_fill_range` 会自动二分区间递归，不会静默截断。
# 注意：翻页次数只取决于「结果总数 / 30」，跟区间开多宽无关，所以把区间放宽
# （例如 5 年一次查）不会更慢，反而省掉每天一次的请求开销。
MAX_PAGES_DEFAULT = 250

BY_DATE_DIR = "by_date"  # 日期目录的父目录名（避免与 reports/ prospectus/ _state/ 混在根下）
SUBDIR = {"q3": "财报", "ipo": "IPO", "yjyg": "业绩预告", "yjkb": "业绩快报"}

# 同一家公司同一天可能披露多份（如「业绩预告」+「业绩预告修正」同时挂网），
# 这些流不能用 `kind|code|date` 当唯一键，否则第二份会被判为「已归档」而漏掉。
# 追加标题哈希做区分；q3/ipo 保持原键格式，以免既有 by_date.jsonl 记录失配。
MULTI_PER_DAY = {"yjyg", "yjkb"}

# 三季报「正本」识别（关键）。巨潮的 category_sjdbg_szsh 是「季度报告」大类，
# 实测会把每季度初集中披露的【可转债转股情况公告】【股票期权自主行权结果公告】
# 【业绩预告/快报】【业绩说明会预告】一起带出来 —— 它们标题里同样含「第三季度」，
# 用「包含关键词」式匹配会误抓上百条（实测 2026-10-09 单日 128 条几乎全是这类）。
#
# 正规三季报标题形如「中国石油天然气股份有限公司2025年第三季度报告」/
# 「2025年三季度报告」—— 特征是以「(第)三季度报告」**结尾**（可带「全文」后缀）。
# 因此改用「锚定结尾」的正则，并叠加排除词兜底。
Q3_TITLE_RE = re.compile(
    r"(20\d{2}\s*年\s*)?(第三季度|三季度|三季)报告"
    r"(全文|正文|\(全文\)|（全文）)?\s*$"
)
Q3_EXTRA_EXCLUDE = [
    "公告", "说明会", "提示", "预告", "快报", "风险", "无法", "关于", "业绩",
    "转股", "行权", "激励", "督导", "核查意见", "法律意见", "问询",
    "摘要", "更正", "补充", "修改", "英文", "已取消",
] + EXCLUDE_KEYWORDS

# 业绩预告 / 业绩快报识别。
#
# 【关键】业绩预告**有**可用的 category，代码是 `category_yjygjxz_szsh`
# （yjyg + jxz = 业绩预告及修正）。这个码从巨潮公告检索页的前端包里抠出来的：
#   http://www.cninfo.com.cn/new/js/app/disclosure/notice/history-notice.js
#   → {"key": "category_yjygjxz_szsh", "value": "业绩预告"}
# 那个页面里完整的 67 个 category 是权威清单，**不要再靠猜拼法**。
#
# 踩过的坑：`category_yjyg_szsh` / `category_yjkb_szsh` / `category_yjyg` 等
# 十余种「看起来对」的拼法全部不存在，而巨潮对无效 category 的处理是
# **静默忽略** —— 不报错，直接退化成「全市场最新 30 条」（返回的是
# 「关于股东股份被司法强制卖出的公告」这类无关公告）。判别方法：把带 category
# 的返回 announcementId 与「完全不传 category」的基线做指纹比对，一致即被忽略。
#
# 实测（`probe_yjyg_cat.py`，2025-10 整月 / 2026-10-01~11 两窗口）：
#   | 窗口           | category | searchkey=业绩 宽词 | 宽词正则命中 | category 漏掉 |
#   | 2025-10 整月   |     129  |               1355 |         122 |            0 |
#   | 2026-10-01~11  |      20  |                 85 |          19 |            0 |
# → category 不但真过滤（噪声≈0），而且**全覆盖**正则能抓到的东西；
#   多出来的 7 条全部是业绩快报，即该 category 本身就含「业绩快报」。
#   所以检索量比宽词降一个数量级，且不必再靠搜索词兜底。
#
# 为什么不再用 `searchkey=业绩` 宽词：它还额外返回「业绩说明会 / 业绩考核指标 /
# 业绩补偿进展 / 业绩异常专项核查意见」等噪声（2025-10 是 1355 vs 129），
# 白白多翻 40 页。category 直接给干净集合。
YJYG_CATEGORY = "category_yjygjxz_szsh"
# 「业绩预告」族（预增/预盈/预减/预亏/预平都是预告的强弱表述，属同一披露类型）。
YJYG_TITLE_RE = re.compile(r"业绩\s*(预告|预增|预盈|预减|预亏|预平)")
# 「业绩快报」是另一种文件（已审财务数据的自愿快报），单独成流，不混进 yjyg。
YJKB_TITLE_RE = re.compile(r"业绩\s*快报")
# 排除词：category 已经很干净，这里只做兜底（既有的英文版 / 已取消公告等）。
#
# 这里**故意不继承** reports.EXCLUDE_KEYWORDS：那份清单含「更正/补充/修改」，
# 而「业绩预告更正公告」恰恰是必须留下的独立披露（它有自己的披露日期，且会改变
# 预告数值）。同一个坑别踩第二次。
YJYG_EXTRA_EXCLUDE = ["英文", "已取消", "摘要"]


_log_lock = threading.Lock()
_LOG_PATH = None


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with _log_lock:
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            # 控制台代码页不支持中文时才降级，日志文件始终是完整 UTF-8
            print(line.encode("ascii", "replace").decode("ascii"), flush=True)
        if _LOG_PATH:
            try:
                with open(_LOG_PATH, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass


# ─── 巨潮检索（全市场 + 区间 + 翻页） ────────────────────────

def _post(params, timeout):
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(CNINFO_QUERY_URL, data=data, headers=QUERY_HEADERS,
                                method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise DownloadError(f"巨潮 API HTTP {e.code} {e.reason}", e.code)
    except urllib.error.URLError as e:
        raise DownloadError(f"网络错误: {e.reason}")
    except json.JSONDecodeError:
        raise DownloadError("巨潮 API 返回非 JSON")
    except OSError as e:
        raise DownloadError(f"网络错误: {type(e).__name__}: {e}")


def _parse_ann(a, fallback_day):
    url = a.get("adjunctUrl") or ""
    title = (a.get("announcementTitle") or "").strip()
    if not url or not title:
        return None, None
    ts = a.get("announcementTime") or 0
    try:
        d = (datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts
             else fallback_day)
    except (ValueError, OSError):
        d = fallback_day
    return url, {
        "title": title,
        "date": d,
        "adjunct_url": url,
        "pdf_url": CNINFO_PDF_BASE + url,
        "code": (a.get("secCode") or a.get("stockCode") or "").strip(),
        "name": (a.get("secName") or "").strip(),
    }


def _scan_into(store, category, searchkey, since, until, timeout, max_pages):
    """把 [since, until]（date 对象）区间内披露的公告并入 store（键 = adjunctUrl）。

    返回 True 表示撞到了翻页上限、区间内的结果**可能不全**。
    """
    for page in range(1, max_pages + 1):
        r = _post({
            "pageNum": str(page), "pageSize": str(PAGE_SIZE), "column": "szse",
            "tabName": "fulltext", "plate": "", "stock": "", "searchkey": searchkey,
            "secid": "", "category": category, "trade": "", "seach": "",
            "seDate": f"{since.isoformat()}~{until.isoformat()}",
            "isFuzzy": "true", "sortName": "", "sortOrder": "",
        }, timeout)
        anns = r.get("announcements") or []
        if not anns:
            return False
        for a in anns:
            url, rec = _parse_ann(a, since.isoformat())
            if url and url not in store:
                store[url] = rec
        if not r.get("hasMore"):
            return False
    return True


def _fill_range(store, category, searchkey, since, until, timeout, max_pages,
                depth=0):
    """区间检索；撞到翻页上限就二分区间递归，直到单日为止。

    这是「按区间一次拉全」的关键兜底 —— 巨潮 pageSize 硬上限 30，
    一个宽区间（比如一整年的三季报 ~5400 份 = 180 页）可能超过 max_pages。
    二分后每半区间结果减半，通常就能一次装下。
    """
    if not _scan_into(store, category, searchkey, since, until, timeout, max_pages):
        return False
    if since >= until or depth >= 12:
        return True                      # 单日仍撞上限：真的截断了
    mid = since + timedelta(days=(until - since).days // 2)
    a = _fill_range(store, category, searchkey, since, mid, timeout, max_pages,
                    depth + 1)
    b = _fill_range(store, category, searchkey, mid + timedelta(days=1), until,
                    timeout, max_pages, depth + 1)
    return a or b


def scan_range(category, searchkey, since, until, timeout=DEFAULT_TIMEOUT,
               max_pages=MAX_PAGES_DEFAULT):
    """检索 [since, until] 区间内披露的全市场公告。

    返回 (公告列表, capped)。每条公告自带 date 字段，调用方按它分桶即可 ——
    所以一次区间检索就能填出多天的日期目录，不必一天发一个请求。
    """
    store = {}
    capped = _fill_range(store, category, searchkey, since, until, timeout,
                         max_pages)
    return list(store.values()), capped


def scan_day(category, searchkey, day, timeout=DEFAULT_TIMEOUT,
             max_pages=MAX_PAGES_DEFAULT):
    """单日检索（薄封装，便于探针/调试）。"""
    d = date.fromisoformat(day) if isinstance(day, str) else day
    return scan_range(category, searchkey, d, d, timeout, max_pages)


# ─── 正本挑选 ───────────────────────────────────────────────

def pick_q3(anns, year):
    """从「同一天、同一只股票」的公告里挑出三季报正本。

    两道闸门：标题必须以「(第)三季度报告」结尾（锚定，滤掉转股/行权/预告等
    同含「第三季度」的公告），且不含任何排除词；优先带目标年份者。
    """
    y = str(year)
    hit_year, hit_any = [], []
    for a in anns:
        t = a["title"].strip()
        if not Q3_TITLE_RE.search(t):
            continue
        if any(kw in t for kw in Q3_EXTRA_EXCLUDE):
            continue
        (hit_year if y in t else hit_any).append(a)
    cands = hit_year or hit_any
    if not cands:
        return None
    # 正本标题通常最短（带公司全称的长标题次之）
    cands.sort(key=lambda x: len(x["title"]))
    return cands[0]


def pick_ipo(anns):
    """招股书正本：复用既有过滤规则。"""
    return filter_prospectus(anns)


def pick_all(anns, pattern, year=None, extra_exclude=YJYG_EXTRA_EXCLUDE):
    """从一组公告里挑出**全部**匹配项（业绩预告族用）。

    与 pick_q3 的关键差别：三季报每家每季只有一份正本，故取一条；而业绩预告
    可能有「预告」+「预告修正」同日挂网，取一条会漏，故全部返回、按标题去重。
    """
    y = str(year) if year else ""
    hits, seen = [], set()
    for a in anns:
        t = a["title"].strip()
        if not pattern.search(t):
            continue
        if any(kw in t for kw in extra_exclude):
            continue
        key = (a["code"], t)
        if key in seen:
            continue
        seen.add(key)
        hits.append(a)
    if y:
        # 带目标年份的排在前面（防止往年同题材公告混入），但不丢弃其它
        hits.sort(key=lambda x: (0 if y in x["title"] else 1, len(x["title"])))
    return hits


def pick_yjyg(anns, year=None):
    """业绩预告族（预告/预增/预盈/预减/预亏/预平，含修正稿）。"""
    return pick_all(anns, YJYG_TITLE_RE, year)


def pick_yjkb(anns, year=None):
    """业绩快报。"""
    return pick_all(anns, YJKB_TITLE_RE, year, extra_exclude=[
        "说明会", "业绩说明", "摘要", "问询", "督导", "核查意见",
    ])


# ─── 状态 ───────────────────────────────────────────────────

class Index:
    """已归档索引：_state/by_date.jsonl（追加）+ manifest_by_date.csv（重写）。"""

    COLUMNS = ["date", "kind", "code", "name", "title", "size_bytes",
               "board", "filepath", "pdf_url", "archived_at"]

    def __init__(self, root):
        self.root = root
        self.state_dir = os.path.join(root, "_state")
        self.jsonl = os.path.join(self.state_dir, "by_date.jsonl")
        self.csv = os.path.join(root, "manifest_by_date.csv")
        self.lock = threading.Lock()
        self.records = {}
        if os.path.exists(self.jsonl):
            with open(self.jsonl, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.records[rec.get("key")] = rec
        self.fh = open(self.jsonl, "a", encoding="utf-8")

    @staticmethod
    def key(kind, code, date_str, title=""):
        base = f"{kind}|{code}|{date_str}"
        if kind in MULTI_PER_DAY:
            h = hashlib.md5((title or "").strip().encode("utf-8")).hexdigest()[:8]
            return f"{base}|{h}"
        return base

    def has(self, kind, code, date_str, title=""):
        return self.key(kind, code, date_str, title) in self.records

    def add(self, rec):
        with self.lock:
            self.records[rec["key"]] = rec
            self.fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.fh.flush()

    def close(self):
        self.fh.close()

    def write_csv(self):
        rows = sorted(self.records.values(), key=lambda r: (r.get("date", ""),
                                                            r.get("kind", ""),
                                                            r.get("code", "")))
        with open(self.csv, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(self.COLUMNS)
            for r in rows:
                w.writerow([r.get(c, "") for c in self.COLUMNS])
        return self.csv, len(rows)


MANIFEST_COLUMNS = ["code", "name", "kind", "year", "title", "date",
                    "size_bytes", "board", "filepath", "pdf_url"]


class ReportMirror:
    """把三季报镜像进既有结构 reports/{年}/q3/，并追加进 manifest.csv。

    既有数据集（bulk_cninfo.py 的产物）以 `reports/{年}/{类型}/` 为准，其
    manifest.csv 的 `filepath` 是绝对路径、`kind` 为 `report`。这里保持完全一致，
    这样 `reports/2026/q3/` 补齐后，原数据集口径不需要任何额外说明就成立。

    镜像是**硬链接**（同一卷 NTFS 上两个路径指向同一份数据），整季 5,400 份
    约 3~5 GB 的重复占用可以省掉；跨卷或 FS 不支持时自动退回复制。
    """

    def __init__(self, root):
        self.root = root
        self.path = os.path.join(root, "manifest.csv")
        self.lock = threading.Lock()
        self.rows = []
        self.have = set()          # 已存在于 manifest.csv 的 filepath（大小写不敏感）
        self.appended = 0
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    self.rows.append(r)
                    fp = (r.get("filepath") or "").strip()
                    if fp:
                        self.have.add(os.path.normcase(os.path.abspath(fp)))

    def _append_row(self, row):
        new_file = not os.path.exists(self.path)
        with open(self.path, "a", encoding="utf-8-sig" if new_file else "utf-8",
                  newline="") as fh:
            w = csv.writer(fh)
            if new_file:
                w.writerow(MANIFEST_COLUMNS)
            w.writerow([row.get(c, "") for c in MANIFEST_COLUMNS])
        self.appended += 1

    def sort_manifest(self):
        """把 manifest.csv 重排回 bulk_cninfo.py 的排序口径（年 → kind → code）。

        镜像行是追加到文件末尾的，不重排的话，那份 96k 行的既有清单里会多出一批
        位置不对的行（既有清单由 `bulk_cninfo.write_manifest` 按同一 key 排序生成）。
        调用方负责决定是否触发（run 里仅在本次有新镜像时触发）。
        """
        with open(self.path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fields = list(reader.fieldnames or MANIFEST_COLUMNS)
            rows = list(reader)
        rows.sort(key=lambda r: (str(r.get("year") or ""), r.get("kind") or "",
                                 r.get("code") or ""))
        with open(self.path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        return len(rows)

    def mirror(self, ann, size_bytes, src_path):
        """把已下载的三季报 src_path 镜像到 reports/{年}/q3/。返回目标路径。"""
        if not src_path or not os.path.exists(src_path):
            return None
        year = str(ann.get("year") or date.fromisoformat(ann["date"]).year)
        out_dir = os.path.join(self.root, "reports", year, "q3")
        os.makedirs(out_dir, exist_ok=True)
        target = os.path.join(out_dir, os.path.basename(src_path))
        norm = os.path.normcase(os.path.abspath(target))

        with self.lock:
            if norm in self.have:
                return target
            if not (os.path.exists(target) and os.path.getsize(target) > 1024):
                try:
                    os.link(src_path, target)          # 硬链接：零额外占用
                except OSError:
                    shutil.copy2(src_path, target)     # 跨卷等场景退回复制
            self._append_row({
                "code": ann["code"], "name": ann["name"], "kind": "report",
                "year": year, "title": ann["title"], "date": ann["date"],
                "size_bytes": size_bytes,
                "board": detect_board(ann["title"]) or "",
                "filepath": target, "pdf_url": ann["pdf_url"],
            })
            self.have.add(norm)
        return target


def load_existing(root):
    """读既有 manifest.csv，得出已经全量下过的内容，避免重复下载。

    招股书返回 {代码: 已归档的最新披露日期}：只有在「新候选日期 <= 已归档日期」
    时才跳过 —— 这样同一家公司的再次 IPO（新招股书）仍能被抓到。
    三季报返回 {(代码, 年份)} 集合。
    """
    path = os.path.join(root, "manifest.csv")
    have_pros, have_q3 = {}, set()
    if not os.path.exists(path):
        return have_pros, have_q3
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            kind = (r.get("kind") or "").strip()
            code = (r.get("code") or "").strip()
            rd = (r.get("date") or "").strip()
            if kind == "prospectus":
                if rd > have_pros.get(code, ""):
                    have_pros[code] = rd
            elif kind == "report" and "q3" in (r.get("filepath") or ""):
                have_q3.add((code, (r.get("year") or "").strip()))
    return have_pros, have_q3


# ─── 下载 ───────────────────────────────────────────────────

def download_retry(pdf_url, out_dir, filename, attempts=3, timeout=120):
    last = None
    for i in range(attempts):
        try:
            return download_pdf(pdf_url, out_dir, filename, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.2 * (i + 1) + random.random())
    raise DownloadError(f"{type(last).__name__}: {last}")


def archive_one(kind, ann, root, idx, mirror=None, force=False, timeout=120):
    """归档一条：落盘 {root}/by_date/{日期}/{财报|IPO}/...，写索引，三季报额外镜像。"""
    d = ann["date"]
    code, name = ann["code"], ann["name"]
    sub = SUBDIR[kind]

    if kind == "q3":
        suffix = REPORT_TYPES["q3"]["filename_suffix"]      # "年第三季度报告"
        year = ann.get("year") or date.fromisoformat(d).year
        filename = safe_filename(f"{code}_{name}_{year}{suffix}.pdf")
    elif kind in ("yjyg", "yjkb"):
        # 用公告标题本身做文件名（业绩预告的标题自带期间，如「2026年前三季度业绩预告」，
        # 比代码+简称更能说明是哪一期）。标题里若已含公司简称就不重复拼，避免超长。
        title = ann["title"].strip()
        base = f"{code}_{title}" if (name and name in title) else f"{code}_{name}_{title}"
        if len(base) > 120:
            # 个别公告标题极长（带「关于……的公告」全套修饰），Windows 单路径
            # 上限 260 字符，截断并挂短哈希防同名碰撞。
            base = base[:110] + "_" + hashlib.md5(base.encode("utf-8")).hexdigest()[:6]
        filename = safe_filename(base + ".pdf")
    else:
        filename = safe_filename(f"{code}_{name}_招股说明书.pdf")

    out_dir = os.path.join(root, BY_DATE_DIR, d, sub)
    filepath = os.path.join(out_dir, filename)

    if not force and os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
        size = os.path.getsize(filepath)
        status = "cached"
    else:
        res = download_retry(ann["pdf_url"], out_dir, filename, timeout=timeout)
        filepath, size = res["filepath"], res["size_bytes"]
        status = "ok"
        idx.add({
            "key": Index.key(kind, code, d, ann["title"]),
            "date": d, "kind": kind, "code": code, "name": name,
            "title": ann["title"], "size_bytes": size,
            "board": detect_board(ann["title"]) or "",
            "filepath": filepath, "pdf_url": ann["pdf_url"],
            "archived_at": datetime.now().isoformat(timespec="seconds"),
        })

    mirrored = None
    if kind == "q3" and mirror is not None:
        mirrored = mirror.mirror(ann, size, filepath)
    return {"status": status, "path": filepath, "size": size, "mirror": mirrored}


# ─── 主流程 ─────────────────────────────────────────────────

def daterange(a, b):
    cur = a
    while cur <= b:
        yield cur
        cur += timedelta(days=1)


def collect_range(since, until, streams, year, timeout, max_pages):
    """检索 [since, until] 区间内的候选正本。返回 [(kind, ann), ...]。

    一条公告自带的 `date` 就是它的披露日期，所以**一次区间检索能填出多天的
    日期目录** —— 不必一天发一个请求。这是从「逐日扫描」改过来的原因：
    逐日扫描每天至少一次请求（哪怕当天什么都没披露），跨 5 年就是 1700+ 次；
    区间扫描的请求数只取决于命中总数，与区间宽度无关。
    """
    picked = []

    if "q3" in streams:
        # 两条检索路径取并集，提高正本召回：
        #   1) category_sjdbg_szsh（季度报告大类，覆盖绝大多数）
        #   2) 无 category + searchkey 全文检索（历史教训：中国联通/东方证券等
        #      少数公司正本被归到了季度报告 category 之外）
        anns, capped = scan_range(REPORT_TYPES["q3"]["category"], "", since, until,
                                  timeout=timeout, max_pages=max_pages)
        if capped:
            log(f"  ! {since}~{until} 三季报(category)分页撞上限未拆开，可能不全")
        try:
            extra, capped2 = scan_range("", REPORT_TYPES["q3"]["search_key"],
                                        since, until, timeout=timeout,
                                        max_pages=max_pages)
        except DownloadError as e:
            log(f"  ~ {since}~{until} 三季报(searchkey)兜底检索失败：{e.message}")
            extra, capped2 = [], False
        if capped2:
            log(f"  ! {since}~{until} 三季报(searchkey)分页撞上限未拆开，可能不全")
        seen = {a["adjunct_url"] for a in anns}
        anns += [a for a in extra if a["adjunct_url"] not in seen]

        # 按 (代码, 披露日) 分组：区间检索会把同一家公司在不同日期的公告混在一起，
        # 直接按代码分组会把「今天的正式报告」和「昨天的更正稿」混为一批去挑。
        groups = {}
        for a in anns:
            groups.setdefault((a["code"], a["date"]), []).append(a)
        for (_code, _d), lst in groups.items():
            tgt = pick_q3(lst, year)
            if tgt:
                picked.append(("q3", dict(tgt, year=year)))

    if "ipo" in streams:
        anns, capped = scan_range("", "招股说明书", since, until,
                                  timeout=timeout, max_pages=max_pages)
        if capped:
            log(f"  ! {since}~{until} 招股书分页撞上限未拆开，可能不全")
        groups = {}
        for a in anns:
            groups.setdefault((a["code"], a["date"]), []).append(a)
        for (_code, _d), lst in groups.items():
            tgt = pick_ipo(lst)
            if tgt:
                picked.append(("ipo", tgt))

    # 业绩预告 / 业绩快报：走权威 category_yjygjxz_szsh（见文件头注释）。
    # 该 category 本身就同时含「业绩预告」和「业绩快报」，故一次检索喂两个正则。
    if "yjyg" in streams or "yjkb" in streams:
        anns, capped = scan_range(YJYG_CATEGORY, "", since, until,
                                  timeout=timeout, max_pages=max_pages)
        if capped:
            log(f"  ! {since}~{until} 业绩类分页撞上限未拆开，可能不全")
        if "yjyg" in streams:
            for a in pick_yjyg(anns, year):
                picked.append(("yjyg", a))
        if "yjkb" in streams:
            for a in pick_yjkb(anns, year):
                picked.append(("yjkb", a))

    return picked


def cmd_run(args):
    global _LOG_PATH
    root = os.path.abspath(args.root)
    os.makedirs(os.path.join(root, "_state"), exist_ok=True)
    _LOG_PATH = os.path.join(root, "_state",
                             f"fetch_by_date-{datetime.now():%Y%m%d-%H%M%S}.log")

    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until)
    streams = [s.strip() for s in args.streams.split(",") if s.strip()]
    for s in streams:
        if s not in SUBDIR:
            raise SystemExit(f"未知流:{s}（可选 {','.join(SUBDIR)}）")

    idx = Index(root)
    mirror = ReportMirror(root)
    have_pros, have_q3 = (set(), set()) if args.force else load_existing(root)

    log(f"根目录   : {root}")
    log(f"日期区间 : {since} ~ {until}（{((until - since).days + 1)} 天）")
    log(f"数据流   : {','.join(streams)}  三季报年份={args.report_year}")
    log(f"已归档   : {len(idx.records)} 条（历史 manifest 招股书 {len(have_pros)} / 三季报 {len(have_q3)}）")
    log(f"既有清单 : manifest.csv {len(mirror.rows)} 行（三季报将镜像到 reports/{args.report_year}/q3/）")

    todo = []
    stats = {"cand": 0, "skip_known": 0, "skip_idx": 0}
    try:
        picked = collect_range(since, until, streams, args.report_year,
                               args.timeout, args.max_pages)
    except DownloadError as e:
        log(f"  x {since}~{until} 检索失败：{e.message}")
        picked = []
    stats["cand"] = len(picked)
    for kind, ann in picked:
        code = ann["code"]
        if kind == "q3" and (code, str(args.report_year)) in have_q3:
            stats["skip_known"] += 1
            continue
        if kind == "ipo" and ann["date"] <= have_pros.get(code, ""):
            stats["skip_known"] += 1
            continue
        if idx.has(kind, code, ann["date"], ann["title"]):
            stats["skip_idx"] += 1
            continue
        todo.append((kind, ann))

    # 统计覆盖到哪些披露日（区间检索的可见证据）
    days_hit = len({a["date"] for _k, a in picked})
    log(f"检索完成：候选正本 {stats['cand']} 条，覆盖 {days_hit} 个披露日；"
        f"跳过（既有清单 {stats['skip_known']} / 已归档 {stats['skip_idx']}）"
        f"→ 待下载 {len(todo)} 条")

    for kind, ann in sorted(todo, key=lambda x: (x[1]["date"], x[0], x[1]["code"])):
        log(f"  + {ann['date']} {kind:>4} {ann['code']} {ann['name']} | {ann['title'][:56]}")

    if args.dry_run:
        log("--dry-run：不下载")
        idx.close()
        return 0

    if not todo:
        _, n = idx.write_csv()
        log(f"无新增。索引共 {n} 条 → {idx.csv}")
        idx.close()
        return 0

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(archive_one, k, a, root, idx, mirror, args.force,
                          args.timeout * 4): (k, a)
                for k, a in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            kind, ann = futs[fut]
            try:
                r = fut.result()
                ok += 1
                log(f"  [{i}/{len(todo)}] {r['status']:<6} {ann['date']} {kind:>3} "
                    f"{ann['code']} {ann['name']} ({r['size'] / 1024:.0f}KB)"
                    + (f" → 镜像 {os.path.basename(r['mirror'])}" if r.get("mirror") else ""))
            except Exception as e:  # noqa: BLE001
                fail += 1
                log(f"  [{i}/{len(todo)}] FAIL   {ann['date']} {kind:>3} "
                    f"{ann['code']} {ann['name']} :: {type(e).__name__}: {e}")

    csv_path, n = idx.write_csv()
    idx.close()
    log(f"完成：成功 {ok} / 失败 {fail}；索引共 {n} 条 → {csv_path}")
    if mirror.appended:
        n = mirror.sort_manifest()
        log(f"镜像：新增 {mirror.appended} 份三季报 → "
            f"{os.path.join(root, 'reports', str(args.report_year), 'q3')}"
            f"（manifest.csv 已并入并重排，共 {n} 行）")
    return 0 if fail == 0 else 1


def cmd_list(args):
    """列出某天（或区间）会归档什么，不做下载。"""
    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until)
    streams = [s.strip() for s in args.streams.split(",") if s.strip()]
    for s in streams:
        if s not in SUBDIR:
            raise SystemExit(f"未知流:{s}（可选 {','.join(SUBDIR)}）")
    total = 0
    picked = collect_range(since, until, streams, args.report_year,
                           args.timeout, args.max_pages)
    by_day = {}
    for kind, ann in picked:
        by_day.setdefault(ann["date"], []).append((kind, ann))
    for ds in sorted(by_day):
        rows = by_day[ds]
        print(f"\n=== {ds}  ({len(rows)} 条)")
        for kind, ann in sorted(rows, key=lambda x: (x[0], x[1]["code"])):
            total += 1
            print(f"  {kind:>4} {ann['code']} {ann['name']} | {ann['title'][:70]}")
    print(f"\n合计候选 {total} 条，覆盖 {len(by_day)} 个披露日")
    return 0


def cmd_mirror(args):
    """按 `_state/by_date.jsonl` 把已下载的三季报补镜像进 reports/{年}/q3/。

    用于修复/回填：目录搬迁后、或早期版本尚未带镜像功能时跑一次即可。
    幂等 —— 已存在的镜像与已在 manifest.csv 里的行都会跳过。
    """
    root = os.path.abspath(args.root)
    idx = Index(root)
    mirror = ReportMirror(root)
    done = missing = 0
    for rec in sorted(idx.records.values(), key=lambda r: (r.get("date", ""),
                                                           r.get("code", ""))):
        if rec.get("kind") != "q3":
            continue
        src = rec.get("filepath") or ""
        if not src or not os.path.exists(src):
            missing += 1
            log(f"  ! 源文件缺失：{src}")
            continue
        ann = {
            "code": rec.get("code", ""), "name": rec.get("name", ""),
            "title": rec.get("title", ""), "date": rec.get("date", ""),
            "pdf_url": rec.get("pdf_url", ""),
        }
        tgt = mirror.mirror(ann, rec.get("size_bytes") or 0, src)
        if tgt:
            done += 1
            log(f"  ~ {ann['date']} {ann['code']} {ann['name']} → {tgt}")
    idx.close()
    mirror.sort_manifest()
    log(f"镜像完成：三季报 {done} 条；新增 manifest.csv {mirror.appended} 行；缺失源 {missing} 条")
    return 0


def cmd_migrate(args):
    """目录搬迁：把早期直接落在 `{root}/{日期}/` 的目录移入 `{root}/by_date/{日期}/`。

    同时修正 `manifest_by_date.csv` 与 `_state/by_date.jsonl` 里的绝对路径，
    使索引与磁盘一致（幂等，可重复执行）。
    """
    root = os.path.abspath(args.root)
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    legacy = sorted(n for n in os.listdir(root)
                    if date_re.match(n) and os.path.isdir(os.path.join(root, n)))
    if not legacy:
        log(f"无需搬迁：{root} 下没有 {date_re.pattern} 形式的目录")
    by_date = os.path.join(root, BY_DATE_DIR)
    moved = 0
    for n in legacy:
        src, dst = os.path.join(root, n), os.path.join(by_date, n)
        if os.path.exists(dst):
            log(f"  ! {n}：目标已存在，跳过（请手工核对）")
            continue
        os.makedirs(by_date, exist_ok=True)
        shutil.move(src, dst)
        moved += 1
        log(f"  → {n} 移入 {BY_DATE_DIR}\\{n}")

    # 修正索引里的绝对路径前缀
    def fix(path):
        for n in legacy:
            old = os.path.join(root, n) + os.sep
            if path.startswith(old):
                return os.path.join(by_date, n) + os.sep + path[len(old):]
        return path

    csv_path = os.path.join(root, "manifest_by_date.csv")
    fixed_csv = 0
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            new = fix(r.get("filepath") or "")
            if new != (r.get("filepath") or ""):
                r["filepath"] = new
                fixed_csv += 1
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=Index.COLUMNS)
            w.writeheader()
            w.writerows(rows)

    jsonl = os.path.join(root, "_state", "by_date.jsonl")
    fixed_jsonl = 0
    if os.path.exists(jsonl):
        out = []
        with open(jsonl, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                new = fix(rec.get("filepath") or "")
                if new != (rec.get("filepath") or ""):
                    rec["filepath"] = new
                    fixed_jsonl += 1
                out.append(rec)
        with open(jsonl, "w", encoding="utf-8") as fh:
            for rec in out:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    log(f"搬迁完成：移动 {moved} 个日期目录；修正 manifest_by_date.csv {fixed_csv} 行、"
        f"by_date.jsonl {fixed_jsonl} 条")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="按披露日期归档巨潮增量文档（三季报 / IPO 招股书 / 业绩预告）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, helptext in (("run", "检索并下载"), ("list", "只列出不下载")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--root", "-o", required=True, help="落盘根目录")
        sp.add_argument("--since", required=True, help="起始披露日 YYYY-MM-DD")
        sp.add_argument("--until", required=True, help="结束披露日 YYYY-MM-DD")
        sp.add_argument("--streams", default="q3,ipo,yjyg,yjkb",
                        help="逗号分隔：q3=三季报 ipo=招股书 yjyg=业绩预告 "
                             "yjkb=业绩快报（默认 q3,ipo,yjyg,yjkb；"
                             "yjyg/yjkb 共用同一次 category 检索，加 yjkb 不额外发请求）")
        sp.add_argument("--report-year", type=int, default=date.today().year,
                        help="定期报告所属年份（默认今年）")
        sp.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help="单请求超时秒数")
        sp.add_argument("--max-pages", type=int, default=MAX_PAGES_DEFAULT,
                        help="单次区间检索的翻页上限（撞上限会自动二分区间递归，"
                             f"默认 {MAX_PAGES_DEFAULT}）")
        if name == "run":
            sp.add_argument("--workers", type=int, default=6, help="并发下载线程数")
            sp.add_argument("--force", action="store_true",
                            help="忽略既有 manifest 与本地文件，强制重下")
            sp.add_argument("--dry-run", action="store_true", help="只检索不下载")

    mp = sub.add_parser("mirror", help="按索引把已下载三季报补镜像进 reports/{年}/q3/")
    mp.add_argument("--root", "-o", required=True, help="落盘根目录")

    mg = sub.add_parser("migrate", help="把 {root}/{日期}/ 旧目录搬进 {root}/by_date/")
    mg.add_argument("--root", "-o", required=True, help="落盘根目录")
    return p


def main():
    args = build_parser().parse_args()
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "mirror":
        return cmd_mirror(args)
    if args.cmd == "migrate":
        return cmd_migrate(args)
    return cmd_list(args)


if __name__ == "__main__":
    raise SystemExit(main())
