import json, os, re
import screen_growth as sg
rs = json.load(open(os.path.join(sg.OUT_DEFAULT,"extract.json"), encoding="utf-8"))
for r in rs:
    if r["kind"] != "ipo": continue
    print("%-8s %-6s  %s" % (r["code"], r["name"], r.get("report_period","")[:40]))
    for k in ("revenue_3y","profit_3y"):
        c = r.get(k)
        if not c: print("    %-11s MISSING" % k); continue
        print("    %-11s %-10s %-6s %s" % (k, c["src"], c.get("label","")[:8], c["yi"]))
        print("        %s" % c["text"][:110].replace(" ",""))
