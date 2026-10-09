import json, os
import screen_growth as sg
rs = json.load(open(os.path.join(sg.OUT_DEFAULT,"extract.json"), encoding="utf-8"))
for r in rs:
    if r["kind"]!="ipo": continue
    if r["code"] not in ("920157","920162","001246","301660","301569","920202"): continue
    pf = r.get("profit_3y")
    print("="*72); print(r["code"], r["name"])
    print("  profit:", json.dumps(pf, ensure_ascii=False)[:500])
