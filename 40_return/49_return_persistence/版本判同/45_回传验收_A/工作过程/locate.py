#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把读到的句子在宋本398条全文里做模糊匹配，给出候选条号。
用法： python3 locate.py "太陽之為病脉浮頭項強痛而惡寒"
      python3 locate.py --file work.txt   # 每行: 页号<TAB>句子
"""
import csv, sys, unicodedata, os

BASE = "/private/tmp/yi/1/unpacked45/45_派发包_A_田边宪本条目比对/数据/宋本398条.csv"

_T2S_SRC = "陽陰為脉傷熱證發頭項強湯藥虛實滿煩數傳變結嘔穀裏濕胷脇瀉噦瘧癉癰腫脹膽臟經絡衞榮氣風溫涼鹹參蟲麥黃齊劑兩錢箇個漬絞濾減擣搗篩剉"
_T2S_DST = "阳阴为脉伤热证发头项强汤药虚实满烦数传变结呕谷里湿胸胁泻哕疟疸痈肿胀胆脏经络卫荣气风温凉咸参虫麦黄齐剂两钱个个渍绞滤减捣捣筛锉"
T2S = str.maketrans(_T2S_SRC, _T2S_DST)

def norm(s):
    s = unicodedata.normalize("NFKC", str(s))
    s = s.translate(T2S)
    return "".join(ch for ch in s if "\u4e00" <= ch <= "\u9fff")

def load():
    out = []
    with open(BASE, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out.append((int(r["条号"]), r["篇"], norm(r["全文"])))
    return out

def bigrams(s):
    return {s[i:i+2] for i in range(len(s)-1)} or ({s} if s else set())

def match(q, base, top=4):
    nq = norm(q)
    if not nq:
        return []
    gq = bigrams(nq)
    scored = []
    for no, pian, body in base:
        gb = bigrams(body)
        cov = len(gq & gb) / len(gq)
        scored.append((cov, no, pian))
    scored.sort(reverse=True)
    return scored[:top]

def main():
    base = load()
    args = sys.argv[1:]
    if args and args[0] == "--file":
        for line in open(args[1], encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or "\t" not in line:
                continue
            pg, q = line.split("\t", 1)
            hits = match(q, base)
            s = "  ".join(f"{no}({pian})={cov:.2f}" for cov, no, pian in hits)
            print(f"{pg}\t{q[:16]}\t{s}")
    else:
        q = " ".join(args)
        hits = match(q, base)
        for cov, no, pian in hits:
            print(f"{no}\t{pian}\t覆盖率={cov:.2f}")

if __name__ == "__main__":
    main()
