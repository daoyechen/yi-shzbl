#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""d2_probe.py —— 36 条逐字片段probe（T4 定案依据）

句相似度会被「分句位置不同」误导。此处改用最硬的判据：
把宋本条去编者附注后切成 10 字片段（步长 5），逐段在本版全文检索，
输出未命中片段 —— 命中的部分即「本版有此文」，未命中的即「此处有异/无」。
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
WORK = os.path.join(VP, "_工作")
TXT = os.path.join(VP, "版本正文", "01_桂林古本伤寒杂病论.md")


def han(s):
    return "".join(c for c in s if "\u4e00" <= c <= "\u9fff")


def core(s):
    """去宋本编者附注（方号、一云、臣亿等按语、方后注）。"""
    s = re.sub(r"\[方[^\]]*\]|〔方[^〕]*〕|\[[一二三四五六七八九十百]+\]", "", s)
    s = re.sub(r"用前第[^\s。，]*方[。，]?", "", s)
    s = re.sub(r"一云[:：][^。]*", "", s)
    s = re.sub(r"臣亿等.*$", "", s, flags=re.S)
    s = re.sub(r"（[^）]*）|\([^)]*\)", "", s)
    return s


def main():
    V = han(open(TXT, encoding="utf-8").read())
    d = json.load(open(os.path.join(VP, "交付", "版本包.json"), encoding="utf-8"))
    todo = [e for e in d["条目"] if e["状态"] != "有"]
    out = []
    for e in todo:
        body = han(core(e["宋本"]))
        if len(body) < 6:
            out.append({"条号": e["条号"], "片段": [], "缺": [], "命中率": 1.0})
            continue
        frags, miss = [], []
        step = 5 if len(body) > 40 else max(1, len(body) // 4)
        for i in range(0, max(1, len(body) - 10 + 1), step):
            f = body[i:i + 10]
            if len(f) < 10:
                continue
            frags.append(f)
            if V.find(f) < 0:
                miss.append(f)
        out.append({"条号": e["条号"], "宋本": e["宋本"], "片段": frags,
                    "缺": miss, "命中率": round(1 - len(miss) / max(1, len(frags)), 3)})
    json.dump(out, open(os.path.join(WORK, "T4probe.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for o in out:
        flag = "有" if not o["缺"] else ("大部分有" if o["命中率"] >= 0.6 else "存疑")
        print("%3d  %-6s 命中%.2f  缺:%s" % (o["条号"], flag, o["命中率"],
                                          "／".join(o["缺"]) or "—"))


if __name__ == "__main__":
    main()
