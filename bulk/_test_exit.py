# -*- coding: utf-8 -*-
"""端到端验证：检索失败必须让 cmd_run 返回非零退出码（不联网）。

这是「静默丢档」的直接回归测试 —— 2022 年那次一整年 6,893 条公告被丢掉，
而 `fetch_by_date.py run` 的退出码是 0，调用方（backfill_yjyg.ps1）完全无感。
"""
import argparse
import os
import shutil
import sys
import tempfile
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

import fetch_by_date as F                     # noqa: E402
from cninfo_client import DownloadError       # noqa: E402

F.time.sleep = lambda *_a: None

fails = []


def check(label, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + label + ("  " + detail if detail else ""))
    if not cond:
        fails.append(label)


def fake_args(**kw):
    a = argparse.Namespace(root="", since="2022-01-01", until="2022-01-31",
                           streams="yjyg", report_year=2026, timeout=30,
                           max_pages=250, force=False, workers=2, dry_run=True)
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def stub_post(code):
    def _p(params, timeout, attempts=F._RETRY_ROUNDS):
        raise DownloadError(f"巨潮 API HTTP {code} x", code)
    return _p


REAL_POST = F._post
root = tempfile.mkdtemp(prefix="cninfo-504test-")

try:
    # ① 全部区间 504 → 非零退出码
    print("场景 5：检索全挂 → cmd_run 必须返回非零")
    F._post = stub_post(504)
    rc = F.cmd_run(fake_args(root=root))
    check("退出码非零", rc != 0, "实际 %r" % rc)
    F._post = REAL_POST

    # ② 全部区间正常且无候选 → 0
    print("\n场景 6：检索正常但无候选 → 退出码 0")
    F._post = lambda params, timeout, attempts=F._RETRY_ROUNDS: {
        "announcements": [], "hasMore": False}
    rc = F.cmd_run(fake_args(root=root))
    check("退出码 0", rc == 0, "实际 %r" % rc)

    # ③ 永久错误（403）→ 也不许静默过
    print("\n场景 7：403 永久错误 → 同样非零")
    F._post = stub_post(403)
    rc = F.cmd_run(fake_args(root=root))
    check("退出码非零", rc != 0, "实际 %r" % rc)
    F._post = REAL_POST
finally:
    F._post = REAL_POST
    shutil.rmtree(root, ignore_errors=True)

print("\n" + ("全部通过" if not fails else "失败项：%s" % fails))
sys.exit(1 if fails else 0)
