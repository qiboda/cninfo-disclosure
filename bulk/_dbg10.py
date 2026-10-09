import json, os
import screen_growth as sg
rs = json.load(open(os.path.join(sg.OUT_DEFAULT,"extract.json"), encoding="utf-8"))
r = [x for x in rs if x["kind"]=="yjyg"][0]
print("KEYS:", sorted(r.keys()))
print(json.dumps({k:v for k,v in r.items() if k!="text"}, ensure_ascii=False, indent=1)[:1800])
