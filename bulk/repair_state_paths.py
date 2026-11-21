#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 done.jsonl 里的绝对路径从旧根目录改写到新根目录。

为什么必须做：`write_manifest` 的「保留既有行」是按路径做集合比较的 ——
它用 done.jsonl 里 ok 记录的 path 组成 managed 集合，去和 manifest.csv 的
filepath 对撞。数据集从 C:\\Users\\iq112\\Documents\\cninfo 搬到 E:\\cninfo 后，
done.jsonl 里 95,321 条 report 记录的 path 仍是 C: 前缀：

  * 这些路径不在磁盘上，写进 manifest 就是死链；
  * managed 里是 C:\\… ，manifest 里是 E:\\… ，谁也匹配不上对方的行，
    结果「既有行全部保留」+「state 行全部重写一遍」，manifest 直接翻倍。

用法：
    python repair_state_paths.py <root> [<旧根> <新根>]
默认把 C:\\Users\\iq112\\Documents\\cninfo 改写为 <root>。
"""
import json
import os
import sys

OLD_DEFAULT = r"C:\Users\iq112\Documents\cninfo"


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else r"E:\cninfo")
    old = sys.argv[2] if len(sys.argv) > 2 else OLD_DEFAULT
    new = sys.argv[3] if len(sys.argv) > 3 else root
    path = os.path.join(root, "_state", "done.jsonl")
    if not os.path.exists(path):
        print(f"找不到 {path}", file=sys.stderr)
        return 1

    tmp = path + ".tmp"
    total = changed = dropped = broken = 0
    with open(path, encoding="utf-8") as f, open(tmp, "w", encoding="utf-8") as out:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # 多线程并发 append 可能写出半行，直接丢弃（该任务会重跑）
                broken += 1
                continue
            p = rec.get("path") or ""
            if p.lower().startswith(old.lower()):
                rec["path"] = new + p[len(old):]
                changed += 1
            # status=ok 但文件已不在磁盘上（被隔离/被删）的记录一并降级，
            # 免得它写进 manifest 变成死链。
            if rec.get("status") == "ok" and rec.get("path") and not os.path.exists(rec["path"]):
                rec["status"] = "missing"
                rec["reason"] = "文件已不在磁盘上"
                dropped += 1
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    print(f"done.jsonl {total} 条：改写路径 {changed} 条，"
          f"降级为 missing {dropped} 条，丢弃断行 {broken} 条 → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
