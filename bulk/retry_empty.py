#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从断点状态中剔除「空结果」记录，使这些任务重跑（修正筛选规则后需要）。

用法：python retry_empty.py <root>
保留 status=ok（已下载，别浪费）与 status=fail（State 本就会重跑）。
"""
import json
import os
import sys

root = sys.argv[1]
path = os.path.join(root, "_state", "done.jsonl")

latest = {}
order = []
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = r.get("key")
        if key not in latest:
            order.append(key)
        latest[key] = r          # 后写覆盖前写

kept = [latest[k] for k in order if latest[k].get("status") != "empty"]
dropped = len(order) - len(kept)

with open(path, "w", encoding="utf-8") as f:
    for r in kept:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"剔除空结果 {dropped} 条，保留 {len(kept)} 条（ok + fail）")
