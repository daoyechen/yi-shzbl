#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""d4_gap.py —— 指定篇的句级缺口（T3 用）

把电子文本某篇按句切，每句取 8 字探针在转录件中检索：
一句里所有探针都不中 → 该句本版无；部分中 → 有异文。
输出缺句清单（含前后文与字数），作为补录依据。
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
SRC = os.path.join(PKG, "原料", "电子文本", "桂林古本")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
TXT = os.path.join(VP, "版本正文", "01_桂林古本伤寒杂病论.md")
WORK = os.path.join(VP, "_工作")


def han(s):
    return "".join(c for c in s if "\u4e00" <= c <= "\u9fff")


def body_of(path):
    out = []
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(">") or s == "---":
            continue
        out.append(s)
    lines = "\n".join(out).strip().split("\n")
    while lines and len(lines[0]) <= 22 and "\u3002" not in lines[0] and lines[0]:
        lines = lines[1:]
    return "\n".join(lines).strip()


def main(fn):
    V = han(open(TXT, encoding="utf-8").read())
    txt = body_of(os.path.join(SRC, fn))
    sents = [s.strip() for s in re.split(r"(?<=[。！？])", txt) if han(s).strip()]
    rows = []
    for s in sents:
        h = han(s)
        if len(h) < 6:
            continue
        hit = 0
        tot = 0
        for i in range(0, max(1, len(h) - 8 + 1), 3):
            p = h[i:i + 8]
            if len(p) < 8:
                continue
            tot += 1
            if V.find(p) >= 0:
                hit += 1
        rate = hit / max(1, tot)
        rows.append({"句": s, "字": len(h), "命中": round(rate, 2)})
    miss = [r for r in rows if r["命中"] < 0.5]
    print("=== %s：%d 句，缺 %d 句（%d 字）" % (fn, len(rows), len(miss),
                                          sum(r["字"] for r in miss)))
    for r in rows:
        mark = "  " if r["命中"] >= 0.5 else "XX"
        print("%s %.2f %s" % (mark, r["命中"], r["句"][:80]))
    json.dump(rows, open(os.path.join(WORK, "缺口_%s.json" % fn[:2]), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    for fn in sys.argv[1:]:
        main(fn)
