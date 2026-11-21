#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b0_cover.py —— 41 篇电子文本 × 转录件 覆盖扫描

用途：
  1. T3：判定每篇在转录件里「有无落点」「是否整篇缺」
  2. T1：为逐字比对圈定范围（先看哪几篇整体在外，再做字符级 diff）

做法：两侧都压成只含汉字的长串（丢标点空白，容标点差异），
      每篇按 20 字窗、步长 8 取样探针，统计在转录件中的命中率。
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
SRC = os.path.join(PKG, "原料", "电子文本", "桂林古本")
TXT = os.path.join(PKG, "版本包_桂林古本二轮", "版本正文", "01_桂林古本伤寒杂病论.md")


def han(s):
    return "".join(c for c in s if "\u4e00" <= c <= "\u9fff")


def body_of(path):
    """去掉标题、引用块、分隔线、首行篇名，取正文。"""
    out = []
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(">") or s == "---":
            continue
        out.append(s)
    t = "\n".join(out).strip()
    # 首行是篇名（与文件名末段同名），去掉
    lines = t.split("\n")
    if lines and len(lines[0]) <= 20 and "\u3002" not in lines[0]:
        lines = lines[1:]
    return "\n".join(lines).strip()


def main():
    flat = han(open(TXT, encoding="utf-8").read())
    rows = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".md"):
            continue
        b = han(body_of(os.path.join(SRC, fn)))
        if not b:
            rows.append((fn, 0, 0, 0.0, []))
            continue
        probes, hit, miss = [], 0, []
        for i in range(0, max(1, len(b) - 20), 8):
            p = b[i:i + 20]
            if len(p) < 20:
                continue
            probes.append(p)
            if flat.find(p) >= 0:
                hit += 1
            elif len(miss) < 3:
                miss.append(p)
        rate = hit / len(probes) if probes else 0.0
        rows.append((fn, len(b), len(probes), rate, miss))

    print("%-52s %6s %5s %7s" % ("篇", "字", "探针", "命中率"))
    for fn, n, np_, r, miss in rows:
        flag = "  " if r >= 0.85 else ("?? " if r >= 0.3 else "XX ")
        print("%s%-50s %6d %5d %6.1f%%" % (flag, fn[:50], n, np_, r * 100))
        if r < 0.85 and miss:
            for m in miss:
                print("        未命中: %s" % m[:24])
    low = [r for r in rows if r[3] < 0.85]
    print("\n合计 %d 篇；命中率 <85%% 的 %d 篇" % (len(rows), len(low)))


if __name__ == "__main__":
    main()
