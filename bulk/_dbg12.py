# -*- coding: utf-8 -*-
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "_growth")
rows = json.load(open(os.path.join(G, "rank_growth.json"), encoding="utf-8"))
recs = {r["code"]: r for r in json.load(open(os.path.join(G, "extract.json"), encoding="utf-8"))}
em = json.load(open(os.path.join(G, "em_yjyg.json"), encoding="utf-8"))
def clean(t):
    t = re.sub(r"\s*\n\s*", " ", t or "")
    t = re.split(r"[三四五六七八九]、\s*(?:风险提示|其他说明|其他相关说明)", t)[0]
    t = re.sub(r"^[一二三]、\s*", "", t)
    return t.strip()
for x in rows:
    if x["tier"] not in ("A 超级成长", "B 高规模+高增速", "C 高增速"):
        continue
    r = recs.get(x["code"], {})
    e = em.get(x["code"], {})
    print("### %s %s %s  [%s]" % (x["code"], x["name"], x["tier"], x["kind"]))
    print("  规模: %s | 增速: %s | 对账: %s %s" % (x.get("scale_why"), x.get("growth_why"),
          x.get("xcheck") or "-", x.get("em_type") or ""))
    if x["kind"] == "ipo":
        print("  主营: %s" % clean(r.get("main_biz") or "-")[:300])
        print("  摘要: %s" % clean(r.get("summary") or r.get("abstract") or "")[:260])
    else:
        print("  原因: %s" % clean(r.get("reason") or e.get("em_reason") or "-")[:420])
    print()
