#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量下载完成后校验：文件数 / 体积 / 覆盖率 / 失败清单 / PDF 完整性抽检。

用法：
  python verify.py C:\\Users\\iq112\\Documents\\cninfo
产出：
  控制台摘要 + {root}/_state/verify_report.md
"""
import collections
import csv
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from bulk_cninfo import DEFAULT_YEARS, REPORT_TYPES, _dedup_legacy  # noqa: E402

root = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\iq112\Documents\cninfo"
state_dir = os.path.join(root, "_state")
out_lines = []


def emit(s=""):
    print(s)
    out_lines.append(s)


# ─── 1. 股票池 ───────────────────────────────────────────────
raw = json.load(open(os.path.join(state_dir, "universe.json"), encoding="utf-8"))
universe, dropped = _dedup_legacy(raw)
N = len(universe)
emit(f"# 下载完整性校验报告")
emit()
emit(f"- 落盘根目录：`{root}`")
emit(f"- 股票池：原始 {len(raw)} 只 → 去北交所旧码重复 {len(dropped)} 只 → **有效 {N} 只**")
emit()

# ─── 2. 任务状态 ─────────────────────────────────────────────
recs = []
with open(os.path.join(state_dir, "done.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass

latest = {}
for r in recs:                      # 后写覆盖前写（重试会追加新记录）
    latest[r["key"]] = r

status = collections.Counter(r["status"] for r in latest.values())
expected_tasks = N * (sum(len(v) for v in DEFAULT_YEARS.values()) + 1)
emit(f"## 1. 任务执行")
emit()
emit(f"- 预期任务 {expected_tasks:,} 个；状态文件记录 {len(latest):,} 个唯一任务")
emit(f"- 成功 **{status['ok']:,}** / 空 {status['empty']:,} / 失败 {status['fail']:,}")
emit()

fails = [r for r in latest.values() if r["status"] == "fail"]
if fails:
    emit(f"## 2. 失败明细（{len(fails)} 条，需重跑）")
    emit()
    for r in fails[:60]:
        emit(f"- `{r['key']}` {r.get('reason', '')[:110]}")
    if len(fails) > 60:
        emit(f"- …… 其余 {len(fails) - 60} 条见 `_state/verify_report.md`")
    emit()
else:
    emit("## 2. 失败明细")
    emit()
    emit("无失败任务。")
    emit()

# 空结果归因（判断是否为系统性漏档）
emit(f"## 3. 空结果归因（{status['empty']:,} 条）")
emit()
reasons = collections.Counter(r.get("reason", "-") for r in latest.values()
                              if r["status"] == "empty")
for reason, cnt in reasons.most_common():
    emit(f"- {reason}: {cnt:,}")
emit()

# ─── 3. 落盘实况 ─────────────────────────────────────────────
disk = collections.defaultdict(lambda: {"n": 0, "bytes": 0, "tiny": 0})
total_bytes = 0
orphan_missing = []
for r in latest.values():
    if r["status"] != "ok":
        continue
    p = r.get("path", "")
    if not p or not os.path.exists(p):
        orphan_missing.append(r["key"])
        continue
    size = os.path.getsize(p)
    total_bytes += size
    # 状态记录的 kind 只有 report/prospectus，真实报告类型在 key 里（形如 "600519|annual|2022"）
    if r["kind"] == "prospectus":
        bucket = ("prospectus", None)
    else:
        bucket = (r["key"].split("|")[1], r.get("year"))
    buf = disk[bucket]
    buf["n"] += 1
    buf["bytes"] += size
    if size < 10 * 1024:
        buf["tiny"] += 1

emit(f"## 4. 落盘实况")
emit()
emit(f"- 状态标记成功但文件缺失：**{len(orphan_missing)}** 个")
if orphan_missing:
    for k in orphan_missing[:30]:
        emit(f"  - `{k}`")
emit()
emit(f"- 磁盘占用合计：**{total_bytes / 1e9:,.2f} GB**")
emit()

emit("## 5. 分类型 / 年份覆盖率（分母 = 全市场 %d 只）" % N)
emit()
emit("| 类型 | 财报年 | 成功数 | 覆盖率 | 平均体积 | 小计 |")
emit("|---|---|---|---|---|---|")
for kind in ["annual", "semi", "q1", "q3"]:
    for year in DEFAULT_YEARS[kind]:
        st = disk.get((kind, year), {"n": 0, "bytes": 0, "tiny": 0})
        avg = st["bytes"] / st["n"] / 1e6 if st["n"] else 0
        emit(f"| {REPORT_TYPES[kind]['label']} | {year} | {st['n']:,} | "
             f"{st['n'] / N * 100:.1f}% | {avg:.2f} MB | {st['bytes'] / 1e9:.2f} GB |")
pst = disk.get(("prospectus", None), {"n": 0, "bytes": 0, "tiny": 0})
emit(f"| 招股说明书 | 2022+ | {pst['n']:,} | {pst['n'] / N * 100:.1f}% | "
     f"{pst['bytes'] / pst['n'] / 1e6 if pst['n'] else 0:.2f} MB | {pst['bytes'] / 1e9:.2f} GB |")
emit()

tiny_total = sum(v["tiny"] for v in disk.values())
emit(f"- 体积极小（<10KB，疑似损坏）文件：**{tiny_total}** 个")
emit()

# ─── 4. PDF 完整性抽检 ───────────────────────────────────────
ok_files = [r["path"] for r in latest.values()
            if r["status"] == "ok" and r.get("path") and os.path.exists(r["path"])]
random.seed(1)
sample = random.sample(ok_files, min(300, len(ok_files)))
bad = []
for p in sample:
    try:
        with open(p, "rb") as f:
            if f.read(5) != b"%PDF-":
                bad.append(p)
    except OSError:
        bad.append(p)
emit(f"## 6. PDF 完整性抽检")
emit()
emit(f"- 抽检 {len(sample)} 个文件，文件头非 `%PDF-` 的：**{len(bad)}** 个")
for p in bad[:20]:
    emit(f"  - `{p}`")
emit()

# ─── 5. 与 manifest 对账 ─────────────────────────────────────
mf = os.path.join(root, "manifest.csv")
if os.path.exists(mf):
    with open(mf, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    emit(f"## 7. manifest 对账")
    emit()
    emit(f"- manifest 行数：{len(rows):,}（应为成功任务数 {status['ok']:,}）")
    emit()

emit(f"## 8. 结论")
emit()
if status["fail"] == 0 and not orphan_missing and not bad:
    emit(f"下载完整：{status['ok']:,} 个文件 / {total_bytes / 1e9:.2f} GB，无失败、无缺失、抽检无损坏。")
else:
    emit(f"存在待处理项：失败 {status['fail']}、缺失 {len(orphan_missing)}、损坏 {len(bad)}。")

report_path = os.path.join(state_dir, "verify_report.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")
print(f"\n报告已写入：{report_path}")
