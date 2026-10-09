#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速核对 manifest.csv：行数、排序、按类型/年份分布、指向文件的存在性。

用途：镜像/搬迁等维护动作之后，确认既有清单没有被打乱或写出坏路径。

用法：
    python check_manifest.py "C:\\Users\\iq112\\Documents\\cninfo"
"""

import csv
import os
import sys
from collections import Counter


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    path = os.path.join(root, "manifest.csv")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    print(f"文件      : {path}")
    print(f"字段      : {fields}")
    print(f"数据行数  : {len(rows)}")

    key = lambda r: (str(r.get("year") or ""), r.get("kind") or "", r.get("code") or "")
    bad = [i for i in range(len(rows) - 1) if key(rows[i]) > key(rows[i + 1])]
    print(f"排序正确  : {not bad}" + (f"（首个乱序位置 {bad[0]}）" if bad else ""))

    print(f"kind 分布 : {dict(Counter(r['kind'] for r in rows))}")

    def bucket(r):
        fp = (r.get("filepath") or "").replace("\\", "/")
        parts = fp.split("/")
        if "reports" in parts:
            i = parts.index("reports")
            if i + 2 < len(parts):
                return f"{parts[i + 1]}/{parts[i + 2]}"
        return "prospectus" if r["kind"] == "prospectus" else "?"

    dist = Counter(bucket(r) for r in rows)
    for k in sorted(dist):
        print(f"  {k:<12} {dist[k]}")

    missing = [r["filepath"] for r in rows if not os.path.exists(r.get("filepath") or "")]
    print(f"缺失文件  : {len(missing)}")
    for m in missing[:5]:
        print(f"  ! {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
