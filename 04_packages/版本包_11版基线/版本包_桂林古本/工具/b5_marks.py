#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b5_marks.py —— T1 的记号级统计（b2 只比汉字，标点/体例记号在这里单独数）

产出 _工作/记号统计.json：
  1. 标点差异（以 b2 的锚点分段为单位，比段内标点串）
  2. 「右×味」/「上×味」两侧计数（逐方确认用）
  3. 异体字保留情况（鞕/濇/澁/疠/裩/脇/讝/耆/栝/蘖/核…）
  4. 药名现代化检查（黄蘖↔黄柏、桃核↔桃仁）
  5. 编者按/夹注（转录件里有、电子文本里无的括注）
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
SRC = os.path.join(PKG, "原料", "电子文本", "桂林古本")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
TXT = os.path.join(VP, "版本正文", "01_桂林古本伤寒杂病论.md")
WORK = os.path.join(VP, "_工作")

PUNCT = "，。；：、？！「」『』（）《》…—·"


def han(s):
    return "".join(c for c in s if "\u4e00" <= c <= "\u9fff")


def pun(s):
    return "".join(c for c in s if c in PUNCT)


def load_e():
    out = []
    for fn in sorted(os.listdir(SRC)):
        if fn.endswith(".md"):
            out.append((fn, open(os.path.join(SRC, fn), encoding="utf-8").read()))
    return out


KEY = {
    "鞕": "鞕（硬）", "濇": "濇（涩）", "澁": "澁（涩）", "疠": "疠（疠）",
    "裩": "裩（裈）", "脇": "脇（胁）", "讝": "讝（谵）", "耆": "耆（芪）",
    "栝": "栝（栝蒌）", "蘖": "蘖（柏）", "蚘": "蚘（蛔）", "欬": "欬（咳）",
    "衂": "衂（衄）", "蝱": "蝱（虻）", "庶虫": "庶虫（䗪虫）", "儿儿": "儿儿（几几）",
}


def main():
    raw = open(TXT, encoding="utf-8").read()
    V = han(raw)
    ev = load_e()
    Etxt = "\n".join(t for _, t in ev)
    E = han(Etxt)

    res = {}

    # —— 1. 标点差异：汉字串定位（V 下标 → raw 下标），逐句比标点串
    vmap = [i for i, c in enumerate(raw) if "\u4e00" <= c <= "\u9fff"]
    p_diff, p_pairs = 0, []
    for fn, t in ev:
        for s in re.split(r"[。！？]", t):
            h = han(s)
            if len(h) < 8:
                continue
            pos = V.find(h)
            if pos < 0 or pos + len(h) > len(vmap):
                continue
            seg = raw[vmap[pos]:vmap[pos + len(h) - 1] + 1]
            a, b = pun(s), pun(seg)
            if a and b and a != b:
                p_diff += 1
                if len(p_pairs) < 10:
                    p_pairs.append({"电子": s[:36], "电子标点": a[:20], "转录标点": b[:20]})
    res["标点差异句"] = p_diff
    res["标点样例"] = p_pairs

    # —— 2. 右×味 / 上×味
    for name, txt in (("转录件", raw), ("电子文本", Etxt)):
        res[name + "_右味"] = len(re.findall(r"右[一二三四五六七八九十百]+味", txt))
        res[name + "_上味"] = len(re.findall(r"上[一二三四五六七八九十百]+味", txt))

    # —— 3. 异体字保留
    res["异体字"] = []
    for ch, lab in KEY.items():
        res["异体字"].append({"字": lab, "转录件": V.count(ch), "电子文本": E.count(ch)})

    # —— 4. 药名现代化
    res["药名"] = []
    for a, b in (("黄蘖", "黄柏"), ("桃核", "桃仁"), ("栝蒌", "瓜蒌"), ("黄耆", "黄芪")):
        res["药名"].append({"古名": a, "今名": b,
                            "转录件_古": V.count(a), "转录件_今": V.count(b),
                            "电子文本_古": E.count(a), "电子文本_今": E.count(b)})

    # —— 5. 编者按/夹注：转录件有括注、电子文本无对应字
    notes = []
    for m in re.finditer(r"（[^）]{4,40}）", raw):
        s = m.group(0)
        if any(k in s for k in ("方见", "见前", "见上", "见后", "炙", "炮",
                                "《伤寒杂病论》卷", "汤方")):
            continue
        h = han(s)
        if h and h not in E:
            notes.append(s)
    res["编者按候选"] = notes
    res["编者按数"] = len(notes)

    json.dump(res, open(os.path.join(WORK, "记号统计.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items()
                      if k in ("标点差异句", "转录件_右味", "转录件_上味",
                               "电子文本_右味", "电子文本_上味", "编者按数")},
                     ensure_ascii=False, indent=1))
    print("异体字:", json.dumps(res["异体字"], ensure_ascii=False))
    print("药名:", json.dumps(res["药名"], ensure_ascii=False))
    print("编者按候选:", notes[:8])


if __name__ == "__main__":
    main()
