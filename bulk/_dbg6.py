import json, os, re
import screen_growth as sg
rs = json.load(open(os.path.join(sg.OUT_DEFAULT,"extract.json"), encoding="utf-8"))
for r in rs:
    if r["code"] != "301660": continue
    p = os.path.join(sg.OUT_DEFAULT, "text", "%s_%s_%s.txt" % (r["date"], r["code"], r["kind"]))
    flat = sg.flatten(open(p, encoding="utf-8").read())
    for m in re.finditer(r"净利润", flat):
        seg = flat[max(0,m.start()-40):m.start()+110].replace(" ","")
        print("%7d  %s" % (m.start(), seg))
