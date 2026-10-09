# -*- coding: utf-8 -*-
"""离线验证 fetch_by_date 的三层失败防御（不联网）。

场景 1  整年区间永远 504  → 应二分降到单日、全部记进 _FAILED_RANGES、不抛异常
场景 2  第一次请求 503，第二次成功 → _post 的退避重试应救回来
场景 3  整年区间 504、子区间正常 → _fill_range 的二分应救回来，_FAILED_RANGES 为空
场景 4  403（永久错误）→ 不应重试，直接抛出
"""
import os
import sys
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

import fetch_by_date as F                     # noqa: E402
from cninfo_client import DownloadError       # noqa: E402

REAL_POST = F._post
REAL_SLEEP = F.time.sleep
F.time.sleep = lambda *_a: None               # 测试里不要真睡

fails = []


def check(label, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + label + ("  " + detail if detail else ""))
    if not cond:
        fails.append(label)


# ─── 场景 1：整年永远 504 ────────────────────────────────────
print("场景 1：整年永远 504 → 二分到单日、全部记账、不抛异常")
calls = []


def always504(params, timeout, attempts=F._RETRY_ROUNDS):
    calls.append(params["seDate"])
    raise DownloadError("巨潮 API HTTP 504 Gateway Time-out", 504)


F._post = always504
del F._FAILED_RANGES[:]
store = {}
try:
    F._fill_range(store, "cat", "", date(2022, 1, 1), date(2022, 12, 31), 30, 250)
    raised = None
except Exception as e:                        # noqa: BLE001
    raised = e
F._post = REAL_POST
check("不抛异常", raised is None, repr(raised) if raised else "")
check("全部记账（365 个单日）", len(F._FAILED_RANGES) == 365,
      "实际 %d 条" % len(F._FAILED_RANGES))
check("记账的是单日区间",
      all(a == b for a, b, _ in F._FAILED_RANGES),
      "首条 %r" % (F._FAILED_RANGES[0][:2] if F._FAILED_RANGES else None,))
check("store 为空", not store)

# ─── 场景 2：单次 503 后成功 → _post 重试救回 ────────────────
# 注意：重试循环在 `_post` **内部**，所以要替换的是 urllib 的 urlopen，
# 而不是 `_post` 本身（换掉 `_post` 就把被测代码整个绕过去了）。
print("\n场景 2：首次 503 后成功 → _post 退避重试救回")
import urllib.error                            # noqa: E402

REAL_URLOPEN = F.urllib.request.urlopen
n = {"i": 0}


class FakeResp(object):
    def __init__(self, payload):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def flaky_urlopen(req, timeout=None):
    n["i"] += 1
    if n["i"] < 3:
        raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable",
                                     None, None)
    return FakeResp(b'{"announcements": [], "hasMore": false}')


F.urllib.request.urlopen = flaky_urlopen
try:
    r = F._post({}, 30)
    ok, err = (isinstance(r, dict) and r.get("hasMore") is False), None
except Exception as e:                          # noqa: BLE001
    ok, err = False, e
F.urllib.request.urlopen = REAL_URLOPEN
check("第三次尝试返回了结果", ok, err or "共调用 %d 次" % n["i"])
check("恰好重试到第 3 次", n["i"] == 3, "实际 %d 次" % n["i"])

# 场景 2b：4 次全挂 → 抛出，且带 status_code
print("\n场景 2b：连续 4 次 503 → 用尽重试后抛出")
n2 = {"i": 0}


def dead_urlopen(req, timeout=None):
    n2["i"] += 1
    raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", None, None)


F.urllib.request.urlopen = dead_urlopen
try:
    F._post({}, 30)
    raised2 = None
except DownloadError as e:
    raised2 = e
F.urllib.request.urlopen = REAL_URLOPEN
check("抛出 DownloadError", raised2 is not None)
check("尝试了 4 次（_RETRY_ROUNDS）", n2["i"] == F._RETRY_ROUNDS, "实际 %d 次" % n2["i"])
check("status_code 保留为 503", getattr(raised2, "status_code", None) == 503)

# ─── 场景 3：整年 504、子区间正常 → 二分救回 ─────────────────
print("\n场景 3：仅整年区间 504，子区间正常 → 二分救回")
seen = []


def year_only_504(params, timeout, attempts=F._RETRY_ROUNDS):
    span = params["seDate"]
    seen.append(span)
    if span == "2022-01-01~2022-12-31":
        raise DownloadError("巨潮 API HTTP 504 Gateway Time-out", 504)
    return {"announcements": [], "hasMore": False}   # 空结果，不触发翻页二分


F._post = year_only_504
del F._FAILED_RANGES[:]
store = {}
F._fill_range(store, "cat", "", date(2022, 1, 1), date(2022, 12, 31), 30, 250)
F._post = REAL_POST
check("无失败区间", not F._FAILED_RANGES, str(F._FAILED_RANGES[:2]))
check("只请求了 3 次（整年 + 两个半区）", len(seen) == 3, "实际 %d 次：%s" % (len(seen), seen))

# ─── 场景 4：403 是永久错误，不该重试 ────────────────────────
print("\n场景 4：403 不重试，直接抛")
n4 = {"i": 0}


def always403(params, timeout, attempts=F._RETRY_ROUNDS):
    n4["i"] += 1
    raise DownloadError("巨潮 API HTTP 403 Forbidden", 403)


F._post = always403
try:
    F._post({}, 30)
    raised4 = None
except DownloadError as e:
    raised4 = e
F._post = REAL_POST
check("抛出 DownloadError", raised4 is not None)
check("只调用 1 次", n4["i"] == 1, "实际 %d 次" % n4["i"])
check("code 保留为 403", getattr(raised4, "status_code", None) == 403)

F.time.sleep = REAL_SLEEP
print("\n" + ("全部通过" if not fails else "失败项：%s" % fails))
sys.exit(1 if fails else 0)
