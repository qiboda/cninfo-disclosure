#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""维护脚本：从断点状态中剔除指定类型记录，使其重新执行。

用法：
  python reset_type.py D:\\cninfo prospectus      # 重置招股书记录
  python reset_type.py D:\\cninfo q3              # 重置三季报记录
"""
import json
import os
import sys

root = sys.argv[1]
kinds = set(sys.argv[2].split(","))
path = os.path.join(root, "_state", "done.jsonl")

kept, dropped = [], 0
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = "prospectus" if r.get("kind") == "prospectus" else str(r.get("kind"))
        tag = str(r.get("year")) if r.get("kind") != "prospectus" else "prospectus"
        if r.get("kind") == "prospectus" and "prospectus" in kinds:
            dropped += 1
            continue
        if tag in kinds:
            dropped += 1
            continue
        kept.append(line)

with open(path, "w", encoding="utf-8") as f:
    for line in kept:
        f.write(line + "\n")
print(f"已剔除 {dropped} 条记录，保留 {len(kept)} 条 → {path}")
