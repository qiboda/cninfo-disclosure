# -*- coding: utf-8 -*-
"""探针：东方财富行情快照接口（push2）能不能一次批量拿到价格/市值/估值。

目的：给成长股筛选补上「当下股价」维度（PE/PB/总市值/涨跌），
以及判断「成长是否已被价格反映」。

结论会写回 README。
"""
import json
import sys
import urllib.parse
import urllib.request

# 沪 1.600000 / 深 0.000001 / 创 0.300750 / 科 1.688981 / 北 0.920157
SECIDS = [
    "1.600176",   # 中国巨石  沪主板
    "0.000601",   # 韶能股份  深主板
    "0.300054",   # 鼎龙股份  创业板
    "1.688099",   # 晶晨股份  科创板
    "0.920157",   # 宇特光电  北交所（待验证前缀）
    "1.920157",   # 北交所另一种前缀写法，看哪个能中
    "116.02245",  # 力勤资源 港股（116 = 港股市场）
]

FIELDS = ("f12,f13,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f15,f16,f17,f18,"
          "f20,f21,f23,f24,f25,f22,f11,f62,f115,f114")

url = "https://push2.eastmoney.com/api/qt/ulist.np/get?" + urllib.parse.urlencode({
    "fltt": "2", "invt": "2", "fields": FIELDS, "secids": ",".join(SECIDS),
    "ut": "fa5fd1943c7b386f172d6893dbfba10b",
    "_": "1",
})
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://quote.eastmoney.com/",
})
sys.stdout.reconfigure(encoding="utf-8")
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
except Exception as e:                                    # noqa: BLE001
    print("请求失败:", type(e).__name__, e)
    sys.exit(1)

print("HTTP OK, %d 字节" % len(raw))
try:
    j = json.loads(raw)
except json.JSONDecodeError:
    print("非 JSON 前 300 字:", raw[:300])
    sys.exit(1)

print("rc =", j.get("rc"), "| data 为 None?", j.get("data") is None)
d = j.get("data")
if not d:
    print(json.dumps(j, ensure_ascii=False)[:600])
    sys.exit(1)

print("total =", d.get("total"))
diff = d.get("diff") or []
if isinstance(diff, dict):
    diff = list(diff.values())
print("返回 %d 条" % len(diff))
for row in diff:
    print(json.dumps(row, ensure_ascii=False))
