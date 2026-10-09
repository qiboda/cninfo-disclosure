import json, os, re
import screen_growth as sg
rs = json.load(open(os.path.join(sg.OUT_DEFAULT,"extract.json"), encoding="utf-8"))
want = ("001246","301660","920202","920162")
for r in rs:
    if r["code"] not in want: continue
    p = os.path.join(sg.OUT_DEFAULT, "text", "%s_%s_%s.txt" % (r["date"], r["code"], r["kind"]))
    flat = sg.flatten(open(p, encoding="utf-8").read())
    print("="*80); print(r["code"], r["name"], "len", len(flat))
    for lb in sg.IPO_PROFIT_LABELS:
        for m in re.finditer(sg.flex(lb) + r"[^。；\n]{0,14}?(?:分别)?为\s*" + sg.RE_IPO_NARR.pattern, flat):
            pre = flat[max(0,m.start()-12):m.start()]
            print("  [%s] pre=%r" % (lb, pre))
            print("      %s" % flat[m.start():m.start()+120].replace(" ",""))
