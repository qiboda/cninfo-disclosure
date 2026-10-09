import json, os, re
import screen_growth as sg
rs = json.load(open(os.path.join(sg.OUT_DEFAULT,"extract.json"), encoding="utf-8"))
for r in rs:
    if r["kind"] != "ipo": continue
    p = os.path.join(sg.OUT_DEFAULT, "text", "%s_%s_%s.txt" % (r["date"], r["code"], r["kind"]))
    flat = sg.flatten(open(p, encoding="utf-8").read())
    fin = sg._ipo_financials(flat)
    print("="*90); print(r["code"], r["name"], " pair_dist", fin.get("pair_dist"), " pair_n", fin.get("pair_n"))
    for k in ("revenue_3y","profit_3y"):
        c = fin.get(k)
        if not c: print("   %-11s None" % k); continue
        print("   %-11s yi=%s  pos=%s" % (k, c["yi"], c.get("pos")))
        print("        ctx: ...%s" % flat[max(0,c["pos"]-90):c["pos"]].replace(" ",""))
        print("        txt: %s" % c["text"][:150].replace(" ",""))
