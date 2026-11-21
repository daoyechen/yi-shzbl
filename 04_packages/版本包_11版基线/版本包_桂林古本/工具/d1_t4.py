#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""d1_t4.py —— 36 条「暂未匹配/体例不同」逐条定位（T4）

对每条宋本条文，在本版转录件里按句找最相似的落点（2-gram 召回 + difflib 精算），
给出候选句、相似度、篇页与行号，供人工定性。
"""
import difflib
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
WORK = os.path.join(VP, "_工作")
TXT = os.path.join(VP, "版本正文", "01_桂林古本伤寒杂病论.md")
DEL = os.path.join(VP, "交付", "版本包.json")


def han(s):
    return "".join(c for c in s if "\u4e00" <= c <= "\u9fff")


def grams(s, n=2):
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def main():
    raw = open(TXT, encoding="utf-8").read()
    lines = raw.split("\n")
    # 句索引：按「。！？；」切，保留行号
    sents = []          # (h, 原文, 行号, 篇)
    heads, pages = [], []
    for k, l in enumerate(lines):
        if l.startswith("## "):
            heads.append((k, l[3:].strip()))
        m = re.match(r"<!-- p(\d+) -->", l.strip())
        if m:
            pages.append((k, int(m.group(1))))
    for k, l in enumerate(lines):
        t = l.strip()
        if not t or t.startswith("#") or t.startswith("<!--"):
            continue
        for s in re.split(r"(?<=[。！？；])", t):
            h = han(s)
            if len(h) >= 6:
                pian = next((x[1] for x in reversed(heads) if x[0] < k), "")
                pg = next((x[1] for x in reversed(pages) if x[0] < k), None)
                sents.append((h, s, k + 1, pian, pg))
    inv = {}
    for i, (h, *_rest) in enumerate(sents):
        for g in grams(h):
            inv.setdefault(g, []).append(i)

    d = json.load(open(DEL, encoding="utf-8"))
    todo = [e for e in d["条目"] if e["状态"] != "有"]
    out = []
    for e in todo:
        body = e["宋本"]
        qs = [han(s) for s in re.split(r"(?<=[。！？；])", body)]
        qs = [q for q in qs if len(q) >= 6]
        best = []
        for q in qs:
            cand = {}
            for g in grams(q):
                for k in inv.get(g, ()):
                    cand[k] = cand.get(k, 0) + 1
            top = sorted(cand.items(), key=lambda x: -x[1])[:10]
            b, br = None, 0.0
            for k, _ in top:
                r = difflib.SequenceMatcher(None, q, sents[k][0], autojunk=False).ratio()
                if r > br:
                    b, br = k, r
            if b is not None:
                best.append((br, b, q))
        best.sort(reverse=True)
        cands = []
        for br, b, q in best[:3]:
            cands.append({"相似": round(br, 3), "宋本句": q,
                          "本版句": sents[b][1], "行": sents[b][2],
                          "篇": sents[b][3], "页": sents[b][4]})
        out.append({"条号": e["条号"], "原原因": e.get("原因"), "宋本": body,
                    "候选": cands, "最高": cands[0]["相似"] if cands else 0})
    json.dump(out, open(os.path.join(WORK, "T4候选.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    for o in out:
        print("\n=== 宋本 %d 条（%s，最高 %.2f）" % (o["条号"], o["原原因"], o["最高"]))
        print("  宋：%s" % o["宋本"][:100])
        for c in o["候选"]:
            print("  %.2f p%s/%s:%d %s" % (c["相似"], c["页"], c["篇"][:8], c["行"],
                                          c["本版句"][:80]))


if __name__ == "__main__":
    main()
