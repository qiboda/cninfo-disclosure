import json, xcheck_growth as xc
j = xc.api("RPT_PUBLIC_OP_NEWPREDICT", "(REPORT_DATE='2026-09-30')")
rows = (j.get("result") or {}).get("data") or []
want = {"688099","688469","300505","300497","300054"}
for r in rows:
    if r["SECURITY_CODE"] in want:
        print("=== %s %s" % (r["SECURITY_CODE"], r.get("SECURITY_NAME_ABBR")))
        for k in ("REPORT_DATE","NOTICE_DATE","PREDICT_FINANCE","PREDICT_AMT_LOWER","PREDICT_AMT_UPPER",
                  "ADD_AMP_LOWER","ADD_AMP_UPPER","PREDICT_TYPE","PREDICT_CONTENT","CHANGE_REASON_EXPLAIN","INDUSTRY"):
            v = r.get(k)
            if v not in (None,""): print("   %-22s %s" % (k, str(v)[:190]))
