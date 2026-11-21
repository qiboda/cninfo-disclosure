#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""招股书全量补抓启动器（抗封禁）

为什么需要它：巨潮 `/new/hisAnnouncement/query` 是 IP 级限流，8 并发跑几百次
就会吃到 HTTP 403，且 403 期间连串行单请求也照样被拒。所以：

  1. 每一轮开跑前先做一次轻量探针，未解封就每分钟探一次（最多 40 分钟）；
  2. 跑完看「成功+空」是否明显多于「失败」——不多就判定为仍被封，
     冷却 15 分钟后重跑（失败记录不入 state，重跑天然幂等）；
  3. 成功/空占多数则收工（剩下的失败多为 1990 年代的 HTML 存档与 404 死链）。

用法：python run_prospectus_safe.py [root] [workers]
"""
import os
import re
import subprocess
import sys
import time

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"E:\cninfo"
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 1
# 查询间隔：巨潮是 IP 级限流，实测 8 并发（约 5 次/秒）跑几百次就吃 403。
# 1 worker + 1.5s 间隔 ≈ 0.67 次/秒，5,000 只约 2~3 小时，但不会被封。
QUERY_GAP = os.environ.get("CNINFO_QUERY_GAP", "1.5")

HERE = os.path.dirname(os.path.abspath(__file__))
BULK = os.path.join(HERE, "bulk_cninfo.py")
LOG = os.path.join(ROOT, "_state", "prospectus-safe.log")

MAX_ROUNDS = 10
COOLDOWN = 900
PROBE_TRIES = 40
PROBE_GAP = 180

sys.stdout.reconfigure(encoding="utf-8")

PROBE = r"""
import sys
sys.path.insert(0, r'C:\Users\iq112\codes\cninfo-disclosure\scripts')
from cninfo_client import query_by_stock
try:
    a = query_by_stock('600519,gssh0600519','sse','1990-01-01','2099-12-31',
                       category='', searchkey='招股说明书', page_size=30, max_pages=1)
    print('OK', len(a))
except Exception as e:
    print('BLOCKED', type(e).__name__, str(e)[:60])
"""


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def probe():
    r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    return out.startswith("OK"), out


def coverage():
    """当前招股书覆盖：磁盘上多少个股票代码有文件。"""
    try:
        import json
        sys.path.insert(0, HERE)
        import bulk_cninfo as bc

        prog = os.path.join(ROOT, "prospectus")
        have = {f[:6] for f in os.listdir(prog)
                if len(f) > 7 and f[:6].isdigit() and f[6] == "_"} if os.path.isdir(prog) else set()
        uni = json.load(open(os.path.join(ROOT, "_state", "universe.json"), encoding="utf-8"))
        kept, _dropped = bc._dedup_legacy(uni)   # 与抓取口径一致（去旧码后 5,945 只）
        codes = {s["code"] for s in kept}
        return len(have & codes), len(codes)
    except Exception as exc:  # 统计失败不该阻断抓取
        log(f"覆盖统计失败：{type(exc).__name__}: {exc}")
        return -1, -1


def main():
    log(f"启动器开始：root={ROOT} workers={WORKERS} 间隔={QUERY_GAP}s")
    have, total = coverage()
    if total > 0:
        log(f"当前覆盖 {have}/{total}（{have * 100 / total:.1f}%），缺 {total - have}")
    for rnd in range(1, MAX_ROUNDS + 1):
        for i in range(PROBE_TRIES):
            ok, out = probe()
            if ok:
                log(f"接口可用（{out}）")
                break
            log(f"接口受限（{out}），{PROBE_GAP}s 后重试 [{i + 1}/{PROBE_TRIES}]")
            time.sleep(PROBE_GAP)
        else:
            log("连续 40 分钟未解封，退出（稍后手工重跑本脚本即可续传）")
            return 1

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["CNINFO_LOG"] = os.path.join(ROOT, "_state", f"prospectus-safe-r{rnd}.log")
        env["CNINFO_QUERY_GAP"] = QUERY_GAP
        log(f"第 {rnd} 轮启动 → {env['CNINFO_LOG']}（workers={WORKERS}, 间隔={QUERY_GAP}s）")
        subprocess.run([sys.executable, BULK, "run", "--root", ROOT,
                        "--prospectus-only", "--workers", str(WORKERS),
                        "--progress", "100", "--timeout", "120"],
                       env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")

        tail = ""
        try:
            with open(env["CNINFO_LOG"], encoding="utf-8") as f:
                tail = f.read()[-800:]
        except OSError:
            pass
        m = re.findall(r"完成：成功 (\d+) / 空 (\d+) / 失败 (\d+)", tail)
        if not m:
            log("本轮没读到完成统计，冷却后重跑")
            time.sleep(COOLDOWN)
            continue
        ok_n, empty_n, fail_n = (int(x) for x in m[-1])
        have, total = coverage()
        log(f"第 {rnd} 轮结束：ok={ok_n} empty={empty_n} fail={fail_n}"
            f" | 覆盖 {have}/{total}（缺 {total - have}）")

        if ok_n + empty_n >= fail_n:
            log("成功+空已不少于失败，判定为正常收工（余下为 HTML 存档/死链）")
            return 0
        log(f"成功+空少于失败，疑似仍在限流，冷却 {COOLDOWN // 60} 分钟")
        time.sleep(COOLDOWN)
    log("达到最大轮次，退出")
    return 1


if __name__ == "__main__":
    sys.exit(main())
