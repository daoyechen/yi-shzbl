#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c2_duibi.py —— 方名集合比对 + 归属初判（T2 第二步）

1. 从宋本 398 条骨架正文抽方名（「XX汤主之」「宜XX汤」等）→ 宋本方名集（带条号）
2. 与本版 328 首方名比对：宋本有 / 宋本无
3. 同名方逐首比药味集合（顺序无关）：组成同 / 药味有出入 / 剂量有出入
4. 输出比对表，供人工核对与归属判定
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
WORK = os.path.join(VP, "_工作")
SK = os.path.join(PKG, "公共地基", "骨架", "宋本398条.json")

# 方名后缀
SUF = "汤|散|丸|饮|煎|膏|丹|酒|粥|方"

# 方名用字归一：异体、通假、讹字（两侧写法不同但同方）
FANG_NORM = [
    ("黄耆", "黄芪"), ("黄茋", "黄芪"), ("庶虫", "䗪虫"), ("蟅虫", "䗪虫"),
    ("＿虫", "䗪虫"), ("地鳖虫", "䗪虫"), ("括蒌", "栝蒌"), ("括楼", "栝蒌"),
    ("栝楼", "栝蒌"), ("防已", "防己"), ("烧昆散", "烧裩散"), ("烧裩散", "烧裩散"),
    ("蝱虫", "虻虫"), ("芎䓖", "芎䓖"), ("川芎", "芎䓖"), ("牡丹皮", "牡丹"),
    ("麦门冬", "麦门冬"), ("麦冬", "麦门冬"), ("抵挡", "抵当"), ("小陷胸胁", "小陷胸"),
    ("芜花", "芫花"), ("蒴藋", "蒴翟"), ("薯蓣", "薯蓣"), ("薯芋", "薯蓣"),
    ("胶汤姜", "胶姜汤"), ("白汤", "白术汤"), ("大承气方", "大承气汤"),
    ("桂枝芍药汤", "桂枝加芍药汤"), ("代赭石", "代赭"), ("前胡", "前胡"),
]


def norm_fang(s):
    """方名归一：去「方」尾 + 异体/通假/讹字替换。"""
    t = s[:-1] if s.endswith("方") else s
    for a, b in FANG_NORM:
        t = t.replace(a, b)
    return t
RE_FANG = re.compile(r"([\u4e00-\u9fff]{1,12}(?:%s))" % SUF)


def load():
    V = json.load(open(os.path.join(WORK, "方剂_V.json"), encoding="utf-8"))
    E = json.load(open(os.path.join(WORK, "方剂_E.json"), encoding="utf-8"))
    sk = json.load(open(SK, encoding="utf-8"))["条目"]
    return V, E, sk


def song_fangs(sk):
    """宋本 398 条正文里的方名 → {方名: [条号]}"""
    d = defaultdict(list)
    for e in sk:
        for m in RE_FANG.finditer(e["body"]):
            nm = m.group(1)
            # 去掉前面的动词/连词
            nm = re.sub(r"^(?:宜|与|属|主之|服|用|作|及|若|凡|以|其)+", "", nm)
            if len(nm) < 3:
                continue
            d[nm].append(e["no"])
    return d


def key_yao(yao):
    """药味集合（忽略剂量/炮制），并做异体字归一，剔除切分残段。"""
    fix = {"黄耆": "黄芪", "黄茋": "黄芪", "栝蒌": "栝蒌", "括蒌": "栝蒌",
           "栝楼": "栝蒌", "庶虫": "䗪虫", "蟅虫": "䗪虫", "＿虫": "䗪虫",
           "地鳖虫": "䗪虫", "川芎": "芎䓖", "牡丹": "牡丹皮", "蝱虫": "虻虫",
           "木防已": "木防己", "蒴翟": "蒴藋", "芜花": "芫花", "薯芋": "薯蓣",
           "麦冬": "麦门冬", "代赭石": "代赭", "枣": "大枣"}
    junky = re.compile(r"^[一二三四五六七八九十百半两\d].*$|^各.*|^等分$|^右.*|^上.*|^[枚个片条茎把尺斗撮粒具颗]+$")
    subst = [("括蒌", "栝蒌"), ("黄耆", "黄芪"), ("黄茋", "黄芪"), ("庶虫", "䗪虫"),
             ("蟅虫", "䗪虫"), ("＿虫", "䗪虫"), ("川芎", "芎䓖"), ("牡丹皮", "牡丹皮"),
             ("蝱虫", "虻虫"), ("木防已", "木防己"), ("蒴翟", "蒴藋"), ("芜花", "芫花"),
             ("薯芋", "薯蓣"), ("麦冬", "麦门冬"), ("代赭石", "代赭")]
    out = set()
    for y in yao:
        n = y["名"].strip().strip("，。")
        n = fix.get(n, n)
        for a, b in subst:
            n = n.replace(a, b)
        n = re.sub(r"(各等分|等分|各)$", "", n)
        if not n or junky.match(n):
            continue
        if len(n) > 8:
            continue
        out.add(n)
    return out


def main():
    V, E, sk = load()
    song = song_fangs(sk)
    # 本版唯一方名（取首次出现，记录全部出现位置）
    vm = defaultdict(list)
    for f in V:
        vm[f["方名"]].append(f)
    em = defaultdict(list)
    for f in E:
        em[f["方名"]].append(f)

    # 归一：去掉「方」字尾再比
    bare = norm_fang

    song_bare = defaultdict(list)
    for k, v in song.items():
        song_bare[bare(k)] += v

    # 归一后聚合（同一方在本版可能有「炙甘草汤方／炙甘草汤」等写法）
    vg = defaultdict(list)
    for nm, fs in vm.items():
        vg[norm_fang(nm)] += fs
    eg = defaultdict(list)
    for nm, fs in em.items():
        eg[norm_fang(nm)] += fs
    print("归一后本版方 %d 首（原写法 %d 种）" % (len(vg), len(vm)))

    rows = []
    for nm, fs in sorted(vm.items()):
        b = bare(nm)
        hit = song_bare.get(b) or song_bare.get(b + "汤") or song_bare.get(b + "散")
        yao = key_yao([y for f in fs for y in f["药味"]])
        rows.append({
            "方名": nm, "出现": len(fs), "页": sorted({f["页"] for f in fs if f["页"]}),
            "篇": sorted({f["篇"] for f in fs}),
            "味数": fs[0]["味数"], "药味": sorted(yao),
            "宋本条号": sorted(set(hit)) if hit else [],
            "电子本有": nm in em,
        })

    # 统计
    n_song = sum(1 for r in rows if r["宋本条号"])
    print("本版唯一方 %d 首；方名见于宋本 398 条者 %d 首" % (len(rows), n_song))
    print("宋本骨架抽出方名 %d 个" % len(song_bare))

    # 只在一边有的方名
    vset = {norm_fang(x) for x in vm}
    eset = {norm_fang(x) for x in em}
    only_v = sorted(vset - eset)
    only_e = sorted(eset - vset)
    print("\n仅转录件有 %d 首：%s" % (len(only_v), "、".join(only_v)))
    print("仅电子文本有 %d 首：%s" % (len(only_e), "、".join(only_e)))

    # 同名方药味比对
    diff = []
    for nm in sorted(vset & eset):
        a = key_yao([y for f in vg[nm] for y in f["药味"]])
        b2 = key_yao([y for f in eg[nm] for y in f["药味"]])
        if a != b2:
            diff.append({"方名": nm, "转录": sorted(a), "电子": sorted(b2),
                         "仅转录": sorted(a - b2), "仅电子": sorted(b2 - a)})
    print("\n同名方药味集合不同 %d 首" % len(diff))
    for d in diff[:30]:
        print("  %-22s 仅转:%s 仅电:%s" % (d["方名"], "、".join(d["仅转录"]) or "-",
                                        "、".join(d["仅电子"]) or "-"))

    json.dump({"方": rows, "同名异组": diff, "仅转录": only_v, "仅电子": only_e,
               "宋本方名": {k: sorted(set(v)) for k, v in song_bare.items()}},
              open(os.path.join(WORK, "方剂比对.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
