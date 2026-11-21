#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c4_song.py —— 「与宋本同名而组成有别者」实证比对

参照本：`pkg_F/…/08_注解伤寒论_十卷全本.md`（宋本系统，成无己注本，含 113 方组成）
对象  ：本版《方剂归属表》判为「宋本方」的各方

做法：两侧都按「方名 → 药味名集合」抽取，药名归一去炮制/剂量，比对称差。
输出：_工作/宋本组成比对.json + 控制台清单
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
WORK = os.path.join(VP, "_工作")
REF = os.path.join(BASE, "..", "pkg_F", "派发包_F_注解伤寒论注文对照专项",
                   "版本包_注解伤寒论注文对照", "版本正文", "08_注解伤寒论_十卷全本.md")

# 药名归一（只收确为同物的古今/异写，不做「同类归并」）
YAO = {
    "黄耆": "黄芪", "黄茋": "黄芪", "栝蒌根": "栝蒌根", "栝楼根": "栝蒌根",
    "栝蒌实": "栝蒌实", "栝楼实": "栝蒌实", "括蒌根": "栝蒌根",
    "葶苈子": "葶苈", "葶苈": "葶苈", "术": "白术", "胶饴": "饴糖",
    "香豉": "香豉", "豉": "香豉", "庶虫": "䗪虫", "蟅虫": "䗪虫", "＿虫": "䗪虫",
    "蝱虫": "虻虫", "蚘虫": "蛔虫", "蜀椒": "蜀椒", "川椒": "蜀椒",
    "防已": "防己", "杏子": "杏仁", "杏人": "杏仁", "桃核": "桃仁",
    "黄蘖": "黄柏", "川芎": "芎䓖", "芎藭": "芎䓖", "麦门冬": "麦冬",
    "天门冬": "天冬", "生地黄": "地黄", "干地黄": "地黄", "生地黄汁": "地黄",
    "乌梅": "乌梅", "梔子": "栀子", "栀子": "栀子", "瓜蒂": "瓜蒂",
    "赤小豆": "赤小豆", "吴茱萸": "吴茱萸", "五味子": "五味子",
    "麻子仁": "麻子仁", "麻仁": "麻子仁", "酸枣仁": "酸枣仁",
    "生梓白皮": "梓白皮", "梓白皮": "梓白皮", "连轺": "连翘", "连翘": "连翘",
    "猪肤": "猪肤", "猪胆汁": "猪胆汁", "人尿": "人尿", "烧裩散": "烧裩散",
    "白蜜": "白蜜", "蜜": "白蜜", "清酒": "清酒", "苦酒": "苦酒",
    "鸡子黄": "鸡子黄", "鸡子白": "鸡子白", "白粉": "白粉",
}


def ny(n):
    n = n.strip("　 ，,。；;：:（）()")
    n = re.sub(r"^(?:生|炮|炙|炒|煨|去.*)$", "", n)
    return YAO.get(n, n)


RE_FN = re.compile(r"^([\u4e00-\u9fff]{2,14})方$")


def parse_ref():
    lines = [l.rstrip("\n") for l in open(REF, encoding="utf-8")]
    out = {}
    for i, l in enumerate(lines):
        m = RE_FN.match(l.strip())
        if not m:
            continue
        name = m.group(1)
        # 组成行：紧随其后的非空行
        j = next((k for k in range(i + 1, min(i + 4, len(lines))) if lines[k].strip()), None)
        if j is None:
            continue
        body = lines[j]
        if not re.search(r"[两枚升合铢斤]", body):
            continue
        toks = [t for t in re.split(r"[\s\u3000]+", body.strip()) if t]
        yao = []
        for t in toks:
            nm = re.split(r"[（(]", t)[0]
            nm = ny(nm)
            if 1 <= len(nm) <= 6 and re.fullmatch(r"[\u4e00-\u9fff]+", nm):
                yao.append(nm)
        if len(yao) >= 2:
            out.setdefault(name, set(yao))
    return out


def main():
    ref = parse_ref()
    print("注解本抽出带组成的方：%d 首" % len(ref))

    rows = json.load(open(os.path.join(WORK, "方剂归属.json"), encoding="utf-8"))
    mine = [r for r in rows if r["归属"] == "宋本方"]

    same, diff, miss = [], [], []
    for r in mine:
        k = r["归一名"]
        cand = [n for n in ref if n == k] or [n for n in ref if n in k or k in n]
        if not cand:
            miss.append(r)
            continue
        a = {ny(y["名"]) for y in r["药味"]}
        b = ref[cand[0]]
        if a == b:
            same.append((k, len(a)))
        else:
            diff.append({"方名": k, "本版": sorted(a), "宋本": sorted(b),
                         "本版多": sorted(a - b), "本版少": sorted(b - a),
                         "参照": cand[0], "篇": r["篇"], "页": r["页"]})

    print("可比 %d 首：组成全同 %d 首，不同 %d 首，参照本无此方 %d 首"
          % (len(same) + len(diff), len(same), len(diff), len(miss)))
    for d in diff:
        print("  %-22s 本版多%s 少%s" % (d["方名"], d["本版多"] or "-", d["本版少"] or "-"))

    json.dump({"全同": len(same), "不同": diff,
               "参照本无": [r["方名"] for r in miss],
               "参照本方数": len(ref)},
              open(os.path.join(WORK, "宋本组成比对.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
