import json, os, re
import screen_growth as sg
rs = json.load(open(os.path.join(sg.OUT_DEFAULT,"extract.json"), encoding="utf-8"))
for code in ("301686","920202"):
    r = [x for x in rs if x["code"]==code][0]
    p = os.path.join(sg.OUT_DEFAULT, "text", "%s_%s_%s.txt" % (r["date"], r["code"], r["kind"]))
    flat = sg.flatten(open(p, encoding="utf-8").read())
    fin = sg._ipo_financials(flat)
    print("="*90); print(code, r["name"])
    for k in ("revenue_3y","profit_3y"):
        c = fin[k]
        print("  %s yi=%s label=%s" % (k, c["yi"], c.get("label")))
        print("     ...%s ||| %s" % (flat[max(0,c["pos"]-140):c["pos"]].replace(" ",""), c["text"][:90].replace(" ","")))
