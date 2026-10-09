# -*- coding: utf-8 -*-
import xcheck_growth as xc, json, os
codes = ["920202","301686","920157","920162","301716","920196","301660","920296","301569"]
mine = {r["code"]: r for r in json.load(open(os.path.join("_growth","extract.json"), encoding="utf-8"))}
for c in codes:
    try:
        j = xc.api("RPT_LICO_FN_CPD", '(SECURITY_CODE="%s")' % c, size=100)
        data = (j.get("result") or {}).get("data") or []
    except Exception as e:
        print("%s ERR %s" % (c, e)); continue
    ann = sorted([d for d in data if str(d.get("REPORTDATE","")).endswith("12-31")], key=lambda d: d["REPORTDATE"])
    got = {d["REPORTDATE"][:10]: d for d in ann}
    m = mine[c]
    rev = [round(float(d["TOTAL_OPERATE_INCOME"])*1e-8,4) if d.get("TOTAL_OPERATE_INCOME") else None for d in ann]
    prof = [round(float(d["PARENT_NETPROFIT"])*1e-8,4) if d.get("PARENT_NETPROFIT") else None for d in ann]
    print("%s %-8s 东财年报%s 营收%s 归母%s" % (c, m["name"], [k[:4] for k in got], rev, prof))
    print("             PDF    营收%s 归母%s" % (
        (m.get("revenue_3y") or {}).get("yi"), (m.get("profit_3y") or {}).get("yi")))
