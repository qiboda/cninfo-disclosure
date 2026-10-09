# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\bulk")
import screen_growth as sg
for f in ("2026-10-08_300964_yjyg.txt","2026-10-10_300505_yjyg.txt","2026-10-10_002107_q3.txt"):
    p = os.path.join(sg.OUT_DEFAULT, "text", f)
    text = open(p, encoding="utf-8").read()
    flat = sg.flatten(text)
    lb, win = sg.find_label_window(flat, sg.PROFIT_LABELS)
    print("="*70); print(f)
    print(" label:", lb)
    print(" win  :", (win or "")[:200])
    print(" pick :", sg.pick_range(win or "", "万元"))
    i = flat.find("净利润")
    print(" first净利润 ctx:", flat[max(0,i-30):i+130])
