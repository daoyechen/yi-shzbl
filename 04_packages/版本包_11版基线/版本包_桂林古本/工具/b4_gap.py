#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b4_gap.py —— 篇内缺口检测：电子文本有、转录件无的段落

做法：篇已大致对齐（b3 已给出落点），用单调游标在转录件中向后扫描：
  每个 16-gram 探针在 V[cur-40, cur+2000] 内找；连续 3 个探针都找不到 → 缺口起点；
  再连续 3 个探针恢复命中 → 缺口终点。返回缺口原文（供人工判读是否真缺）。

输出：_工作/篇内缺口.json、打印清单
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "工具"))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
SRC = os.path.join(PKG, "原料", "电子文本", "桂林古本")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
TXT = os.path.join(VP, "版本正文", "01_桂林古本伤寒杂病论.md")
WORK = os.path.join(VP, "_工作")

from b3_pian import body_of, norm  # noqa

W, STEP = 16, 4


def main():
    V = norm(open(TXT, encoding="utf-8").read())
    out = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".md"):
            continue
        E = norm(body_of(os.path.join(SRC, fn)))
        if len(E) < W * 3:
            continue
        cur = -1
        hits, miss = [], []          # (pos, found?)
        for i in range(0, len(E) - W, STEP):
            p = E[i:i + W]
            if cur < 0:
                k = V.find(p)
            else:
                k = V.find(p, max(0, cur - 80), min(len(V), cur + 4000))
            if k >= 0:
                cur = k + W
                hits.append(i)
                miss.append((i, True))
            else:
                miss.append((i, False))
        # 找连续 3 个以上未命中的区间
        gaps, run = [], None
        for i, ok in miss:
            if not ok:
                if run is None:
                    run = i
            else:
                if run is not None and i - run >= W + STEP * 2:
                    gaps.append((run, i + W))
                run = None
        if run is not None and len(E) - run >= W + STEP * 2:
            gaps.append((run, len(E)))
        for a, b in gaps:
            out.append({"篇": fn, "起": a, "止": b, "长度": b - a,
                        "文本": E[a:b]})
    json.dump(out, open(os.path.join(WORK, "篇内缺口.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    tot = sum(o["长度"] for o in out)
    print("缺口 %d 段，合计 %d 字\n" % (len(out), tot))
    for o in out:
        print("%-46s %4d字  %s" % (o["篇"][:44], o["长度"], o["文本"][:70]))


if __name__ == "__main__":
    main()
