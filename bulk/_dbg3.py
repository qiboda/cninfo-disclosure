import sys, os, glob, re
sys.path.insert(0, r"C:\Users\iq112\codes\cninfo-disclosure\bulk")
import screen_growth as sg
want = {"300497":"富祥","300209":"行云","688099":"晶晨","603228":"景旺","605020":"永和","688103":"国力"}
for code, tag in want.items():
    p = glob.glob(os.path.join(sg.OUT_DEFAULT,"text","*_%s_yjyg.txt" % code))[0]
    text = open(p, encoding="utf-8").read()
    flat = sg.flatten(text)
    uh = sg.RE_UNIT_HINT.search(flat)
    hit = sg.best_amount(flat, [l for l in sg.PROFIT_LABELS if not l.startswith("归属于上市公司股东的扣除非")], uh.group(1) if uh else None, 70)
    print("="*72); print(tag, code)
    if hit:
        lb, raw, win, pr = hit
        print("  label:", lb, " raw:", repr(raw))
        print("  win  :", win[:110])
        print("  pick :", pr)
    else:
        print("  (no hit)")
    for m in re.finditer(r"(亏损|为负值|为正值)", flat):
        print("   sign-ctx[%s]:" % m.group(1), flat[max(0,m.start()-45):m.start()+45])
