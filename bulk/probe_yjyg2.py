#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_yjyg2.py — 找出业绩预告真正的 category 代码（不要再猜）。

上一轮的坑：category_yjyg_szsh / category_yjkb_szsh 是**无效代码**，但巨潮不报错，
而是**静默忽略 category 返回全市场**（返回的标题是「股东股份被司法强制卖出公告」之类，
明显与业绩预告无关）。这会让「筛选」变成「没筛选」，非常危险。

本轮的思路：不去猜代码，而是**从已知的业绩预告公告本身**反查 —— 把它的原始 JSON
所有字段打出来，看有没有 category / categoryName / announcementType 之类的线索。
同时对一批候选代码做「ignored vs valid」判别：若某 category 的返回结果与
「不加 category」的返回结果完全一致，说明它被忽略了。
"""

import json
import os
import sys
import urllib.parse
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))

from cninfo_client import (  # noqa: E402
    CNINFO_QUERY_URL,
    DEFAULT_TIMEOUT,
    QUERY_HEADERS,
)

OUT = os.path.join(_HERE, "probe_yjyg2.out.txt")
buf = []


def say(s=""):
    print(s)
    buf.append(s)


def post(**over):
    p = {
        "pageNum": "1", "pageSize": "30", "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": "", "searchkey": "", "secid": "", "category": "",
        "trade": "", "seach": "", "seDate": "", "isFuzzy": "true",
        "sortName": "", "sortOrder": "",
    }
    p.update({k: str(v) for k, v in over.items()})
    req = urllib.request.Request(CNINFO_QUERY_URL,
                                 data=urllib.parse.urlencode(p).encode("utf-8"),
                                 headers=QUERY_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def sig(anns):
    """一组公告的指纹：取 id 列表前 10 个"""
    return [a.get("announcementId") or a.get("adjunctUrl") for a in anns[:10]]


say("=" * 78)
say("### 1. 一条已知业绩预告的原始 JSON 全字段")
j = post(searchkey="业绩预告", seDate="2026-10-10~2026-10-10")
anns = j.get("announcements") or []
say(f"    返回 {len(anns)} 条；顶层字段 keys = {sorted(j.keys())}")
if anns:
    a = anns[0]
    say(f"    第一条 keys = {sorted(a.keys())}")
    say("    ── 全字段 ──")
    for k in sorted(a.keys()):
        v = a[k]
        vs = str(v)
        if len(vs) > 200:
            vs = vs[:200] + "…"
        say(f"      {k:24s} = {vs}")

say()
say("=" * 78)
say("### 2. 候选 category 逐个判别：是「真筛选」还是「被静默忽略」")
say("    判别法：与「完全不传 category」的返回指纹对比，一致 = 被忽略")

base = post(seDate="2026-10-01~2026-10-31")
base_sig = sig(base.get("announcements") or [])
say(f"    基线（不传 category）: {len(base.get('announcements') or [])} 条 "
    f"hasMore={base.get('hasMore')}")
say(f"    基线指纹: {[x[:24] if x else x for x in base_sig[:3]]}")
say()

CANDIDATES = [
    "category_yjyg_szsh", "category_yjkb_szsh", "category_yjyg", "category_yjkb",
    "category_yjyg_sz", "category_yjyg_sh", "category_yjyg_szsh_bj",
    "category_yjyg_szsh_new", "category_cg_yjyg_szsh", "category_yjyg_szshn",
    "category_yjyg_szshb", "category_yjyg_szsh_sz", "category_yjyg_szsh_sh",
    "category_bcgz_szsh", "category_ndbg_szsh",
]
for cat in CANDIDATES:
    try:
        j2 = post(category=cat, seDate="2026-10-01~2026-10-31")
    except Exception as e:  # noqa: BLE001
        say(f"    {cat:32s} !! {type(e).__name__}: {e}")
        continue
    a2 = j2.get("announcements") or []
    s2 = sig(a2)
    if not a2:
        verdict = "✅ VALID（0 条，真筛选）"
    elif s2 == base_sig:
        verdict = "❌ IGNORED（与基线一致 → 代码无效）"
    else:
        verdict = "🔎 不同（需人工看）"
    sample = (a2[0].get("announcementTitle") or "")[:44] if a2 else ""
    say(f"    {cat:32s} {len(a2):>3} 条  {verdict}  样本: {sample}")

say()
say("=" * 78)
say("### 3. 已知有效对照：category_sjdbg_szsh（三季报）在 10 月窗口")
j3 = post(category="category_sjdbg_szsh", seDate="2026-10-01~2026-10-31")
a3 = j3.get("announcements") or []
say(f"    {len(a3)} 条 hasMore={j3.get('hasMore')} "
    f"指纹与基线一致? {sig(a3) == base_sig}")
for a in a3[:3]:
    say(f"      {a.get('secCode')} {a.get('secName')} | "
        f"{(a.get('announcementTitle') or '')[:60]}")

say()
say("=" * 78)
say("### 4. searchkey 覆盖度对比（2026-10-01~2026-10-31）：哪几个词并集最全")
KEYS = ["业绩预告", "业绩预增", "业绩预减", "业绩预亏", "业绩预盈", "业绩快报",
        "业绩预告修正", "前三季度业绩", "第三季度业绩", "业绩"]
union, per = set(), {}
for kw in KEYS:
    all_ids = set()
    for pn in range(1, 12):
        jj = post(pageNum=pn, searchkey=kw, seDate="2026-10-01~2026-10-31")
        aa = jj.get("announcements") or []
        if not aa:
            break
        for a in aa:
            all_ids.add(a.get("announcementId") or a.get("adjunctUrl"))
        if not jj.get("hasMore"):
            break
    per[kw] = len(all_ids)
    union |= all_ids
    say(f"    searchkey={kw:16s} → {len(all_ids):>4} 条")
say(f"    10 个词的并集 → {len(union)} 条")

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(buf) + "\n")
print(f"\n→ {OUT}")
