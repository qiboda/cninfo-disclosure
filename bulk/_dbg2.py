import json, os
import screen_growth as sg
rs = json.load(open(os.path.join(sg.OUT_DEFAULT,"extract.json"), encoding="utf-8"))
for r in rs:
    if r["kind"] != "ipo": continue
    print("="*70)
    print(r["code"], r["name"], r["date"], "pages=", r.get("pages"))
    print("  main_biz:", (r.get("main_biz") or "(NONE)")[:180].replace("\n"," "))
    ft = r.get("fin_table")
    print("  fin_table:", json.dumps(ft, ensure_ascii=False)[:400] if ft else "(NONE)")
    print("  use_of_proceeds:", (r.get("use_of_proceeds") or "(NONE)")[:120].replace("\n"," "))
