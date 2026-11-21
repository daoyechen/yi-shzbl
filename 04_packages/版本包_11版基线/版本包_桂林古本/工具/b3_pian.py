#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b3_pian.py —— 41 篇逐篇落点核查（T3 主工具）

为什么要有这一步：锚点分段 diff 只能在「本篇已对齐」的前提下工作；
若整篇在转录件里根本不存在，锚点会错落到邻篇，diff 反而不报缺。

做法：两侧先做「异体/体例归一」（异体字→通行字、上→右统一），
再取 20-gram 唯一探针，统计每篇的命中率与首个命中位置，
命中位置即该篇在转录件中的落点（用于《篇目勘误表》）。
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "工具"))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
SRC = os.path.join(PKG, "原料", "电子文本", "桂林古本")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
TXT = os.path.join(VP, "版本正文", "01_桂林古本伤寒杂病论.md")
WORK = os.path.join(VP, "_工作")

from b2_diff import VARIANT, han  # noqa

# 比对归一表：异体→通行 + 体例差异（上/右）
NORM = dict(VARIANT)
for k, v in list(VARIANT.items()):
    NORM.setdefault(v, v)
NORM["右"] = "上"          # 「右X味」↔「上X味」，体例差异，比对时视为同
NORM["鞕"] = "硬"
NORM["梗"] = "硬"
NORM["濇"] = "涩"
NORM["澁"] = "涩"
NORM["脇"] = "胁"
NORM["讝"] = "谵"
NORM["耆"] = "芪"
NORM["栝"] = "括"
NORM["蝱"] = "虻"
NORM["竜"] = "浮紧"        # 转录件讹字「脉竜」＝「脉浮紧」
NORM["擘"] = "劈"
NORM["倣"] = "仿"
NORM["蚘"] = "尤"
NORM["馨"] = "槃"
NORM["徵"] = "征"
NORM["覆"] = "复"
NORM["晬"] = "啐"
NORM["惵"] = "揲"
NORM["濈"] = "戢"


def norm(s):
    return "".join(NORM.get(c, c) for c in han(s))


def body_of(path):
    out = []
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(">") or s == "---":
            continue
        out.append(s)
    lines = "\n".join(out).strip().split("\n")
    # 去掉开头的篇名行（可能连排 1–2 行，均不含句号且不长）
    while lines and len(lines[0]) <= 22 and "\u3002" not in lines[0] and lines[0]:
        lines = lines[1:]
    return "\n".join(lines).strip()


def main():
    os.makedirs(WORK, exist_ok=True)
    raw = open(TXT, encoding="utf-8").read()
    V = norm(raw)
    # 转录件篇标题在 V 中的坐标
    marks = [(m.start(), int(m.group(1))) for m in re.finditer(r"<!--\s*p(\d+)\s*-->", raw)]
    vheads = []
    for m in re.finditer(r"^##\s+(.+)$", raw, re.M):
        p = len(norm(raw[:m.start()]))
        vheads.append((p, m.group(1).strip()))

    def vpian(p):
        r, pg = "（篇前）", None
        for a, nm in vheads:
            if a <= p:
                r = nm
        oi = 0
        # 由 V 坐标反查原串位置：直接按比例找最近的页锚
        for k, (a, n) in enumerate(marks):
            if a <= _orig(p):
                pg = n
        return r, pg

    # V 坐标 → 原串位置：重建映射
    vmap = []
    for m in re.finditer(r"[^\n]*", raw):
        pass
    vmap = []
    for i, c in enumerate(raw):
        if NORM.get(c, c) == "上" and c == "右":
            pass
    # 简易：逐字符生成 V 并记录原位置
    vpos = []
    buf = []
    for i, c in enumerate(raw):
        h = han(c)
        if not h:
            continue
        for x in NORM.get(h, h):
            buf.append(x)
            vpos.append(i)
    V2 = "".join(buf)
    assert V2 == V, "归一坐标不一致"

    def _orig(p):
        return vpos[min(p, len(vpos) - 1)] if vpos else 0

    rows = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".md"):
            continue
        E = norm(body_of(os.path.join(SRC, fn)))
        probes, hit, first = [], 0, None
        for i in range(0, max(1, len(E) - 20), 12):
            p = E[i:i + 20]
            if len(p) < 20:
                continue
            probes.append(p)
            k = V.find(p)
            if k >= 0:
                hit += 1
                if first is None:
                    first = k
        rate = hit / len(probes) if probes else 0.0
        pian, pg = vpian(first) if first is not None else ("—", None)
        rows.append({"篇": fn, "字数": len(E), "探针": len(probes),
                     "命中": hit, "命中率": round(rate, 3),
                     "落点篇": pian, "落点页": pg,
                     "位置": first})

    json.dump(rows, open(os.path.join(WORK, "篇级落点.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=1)
    L = ["%s %-50s %5d %6.1f%%  → %s p%s" % (
        "OK " if r["命中率"] >= 0.85 else ("?? " if r["命中率"] >= 0.3 else "XX "),
        r["篇"][:48], r["字数"], r["命中率"] * 100, r["落点篇"], r["落点页"])
        for r in rows]
    print("\n".join(L))
    print("\n<85%%: %d 篇 / <30%%: %d 篇" % (
        sum(1 for r in rows if r["命中率"] < 0.85),
        sum(1 for r in rows if r["命中率"] < 0.30)))


if __name__ == "__main__":
    main()
