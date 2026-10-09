# -*- coding: utf-8 -*-
import sys, xcheck_growth as xc
codes = ["920202","301686","920157","920162","301716","920196","001246","301660","920296","301569"]
for d in ("2025-12-31","2024-12-31","2023-12-31"):
    j = xc.api("RPT_LICO_FN_CPD", "(REPORTDATE='%s')" % d, size=500)
    data = (j.get("result") or {}).get("data") or []
    hit = {r["SECURITY_CODE"]: r for r in data if r["SECURITY_CODE"] in codes}
    print("%s 东财全部%d条, 命中我们的 %d 只: %s" % (d, len(data), len(hit), ",".join(hit)))
    for c in codes:
        r = hit.get(c)
        if r: print("   %s %s 营收=%s 归母=%s" % (c, r.get("SECURITY_NAME_ABBR"), r.get("TOTAL_OPERATE_INCOME"), r.get("PARENT_NETPROFIT")))
