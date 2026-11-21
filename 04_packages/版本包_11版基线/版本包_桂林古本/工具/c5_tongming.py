#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c5_tongming.py —— 「同名方而组成有别」计数（T2 第二个要报的数）

比什么：本版转录件 ↔ 包内 41 篇电子文本（同一底本系统的两个整理面）。
为什么不是与宋本比：包内没有《伤寒论》方书原文的组成文本（骨架 398 条只到方名，
`pkg_F` 注解本本方组成多省略），逐味比宋本无法取证 —— 该口径缺口已在《争议与疑难清单》写明。

去噪三类（逐条可回原文核）：
  ① 药名归一（防已/防己、黄耆/黄芪、庶虫/䗪虫…）
  ② 切分噪声（一侧把「厚朴一只」切成一味、另一侧切成「厚朴」+残字）
  ③ 见前方（「即前方去人参」之类不含药味者）
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VP = os.path.join(BASE, "派发包_A2_桂林古本二轮", "版本包_桂林古本二轮")
WORK = os.path.join(VP, "_工作")

YAO = {"黄耆": "黄芪", "防已": "防己", "庶虫": "䗪虫", "蟅虫": "䗪虫", "＿虫": "䗪虫",
       "蝱虫": "虻虫", "川芎": "芎䓖", "杏子": "杏仁", "栝楼根": "栝蒌根",
       "栝蒌实者": "栝蒌实", "栝蒌实大者": "栝蒌实", "括蒌根": "栝蒌根"}

JUNK = re.compile(r"(即前|方见|见上|见前|等分|^各$|^一?[只枚两]?$)")


def ny(n):
    n = n.strip()
    return YAO.get(n, n)


def key(f):
    n = re.sub(r"方$", "", f["方名"])
    n = n.replace("黄耆", "黄芪").replace("防已", "防己")
    return n


def main():
    V = json.load(open(os.path.join(WORK, "方剂_V.json"), encoding="utf-8"))
    E = json.load(open(os.path.join(WORK, "方剂_E.json"), encoding="utf-8"))
    vd, ed = {}, {}
    for f in V:
        vd.setdefault(key(f), f)
    for f in E:
        ed.setdefault(key(f), f)

    common = [k for k in vd if k in ed]
    real, noise = [], []
    for k in common:
        a = {ny(y["名"]) for y in vd[k]["药味"] if y["名"] and not JUNK.search(y["名"])}
        b = {ny(y["名"]) for y in ed[k]["药味"] if y["名"] and not JUNK.search(y["名"])}
        if a == b:
            continue
        only_v, only_e = sorted(a - b), sorted(b - a)
        # 去噪：差异项长度异常或含残字 → 切分噪声
        bad = [x for x in only_v + only_e
               if len(x) > 6 or re.search(r"[只枚两升合斤]", x) or x in ("各", "")]
        if bad and not ({x for x in only_v + only_e} - set(bad)):
            noise.append({"方名": k, "本版": only_v, "电子": only_e})
        else:
            real.append({"方名": k, "本版多": only_v, "本版少": only_e,
                         "篇": vd[k]["篇"], "页": vd[k]["页"],
                         "本版原文": vd[k].get("原文行", ""),
                         "本版味数": vd[k]["味数"], "电子味数": ed[k]["味数"]})

    print("同名方 %d 首；组成不同（去噪后）%d 首；判为切分噪声 %d 首"
          % (len(common), len(real), len(noise)))
    for r in real:
        print("  %-20s 本版多%s 少%s" % (r["方名"], r["本版多"] or "-", r["本版少"] or "-"))
    for r in noise:
        print("  [噪声] %-16s 本版%s 电子%s" % (r["方名"], r["本版"], r["电子"]))

    json.dump({"同名方": len(common), "真异组": real, "噪声": noise},
              open(os.path.join(WORK, "同名异组.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
