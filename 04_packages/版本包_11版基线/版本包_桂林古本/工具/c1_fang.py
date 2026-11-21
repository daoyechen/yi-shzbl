#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c1_fang.py —— 方剂结构化抽取（T2 基础，同时供 T1 方剂层比对）

上一轮方剂表由「方名行之后的邻近行即为其组成」的启发式抽取，导致：
  · 方名与组成错配（三物小陷胸汤下列文蛤散）
  · 组成截断（乌头桂枝汤只到「乌头五枚」）
  · 方名粘连（五苓散小陷胸汤）

本脚本按抄本的实际版式抽取：
  方名行（整行以「方」结尾） → 药味区（方名行与「右/上X味」之间的行）
  → 煎服法（「右/上X味…」行）
并且用「右X味」声明的味数校验实际解析出的药味数 —— 不等即报错配/截断。

输出：_工作/方剂_V.json（转录件）、_工作/方剂_E.json（41 篇电子文本）
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

CN = "一二三四五六七八九十百零〇两半"
CN_NUM = "一二三四五六七八九十百半两"   # 剂量数字（含「两」，如「两把」「两枚」）
UNIT = "两升合铢斤分枚个片条茎把尺斗撮粒具颗钱字文壮寸些许匕"
# 剂量后的单字注（不是独立药味），并入前一条的炮制
POST = {"碎", "大者", "小者", "匙", "匕", "余", "各", "等分", "汗", "炮", "炙",
        "切", "劈", "擘", "洗", "熬", "烧", "研", "打碎", "绵裹", "酒洗", "另研",
        "去皮", "去节", "去心", "去足", "去皮尖", "去目", "炒", "蒸", "焙",
        "去目汗", "去汗", "去毛", "去芦", "去核", "去翅足", "去皮脐", "生用"}

RE_NAME = re.compile(r"^([^\s，。；：:、（）()]{2,30})方[：:]?$")
RE_TAIL = re.compile(r"^(?:右|上)([%s]+)味" % CN)
RE_DOSE = re.compile(r"[%s\d]" % CN)
RE_TAILNUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
              "八": 8, "九": 9, "十": 10, "半": 0, "两": 0}
RE_JIAN = re.compile(r"^方?见(前|上|下|后)|俱见前|方见[前后上下]")


def cn2int(s):
    """右X味 的中文数字 → int（只处理 1–30）。"""
    if not s:
        return 0
    if s == "十":
        return 10
    if "十" in s:
        a, _, b = s.partition("十")
        return (RE_TAILNUM.get(a, 1) if a else 1) * 10 + (RE_TAILNUM.get(b, 0) if b else 0)
    return RE_TAILNUM.get(s, 0)


PH = []


def _ph(txt):
    PH.append(txt.strip())
    return len(PH) - 1


def split_yao(line):
    """把药味行切成 [(药名, 剂量, 炮制)]。

    药名与剂量之间没有分隔符（底本有的用全角空格，有的直接相连），所以：
      1. 括号炮制注先换成占位符（「破八片」的「八片」不是剂量）
      2. 先按空白切成「味组」（一个味组通常 = 药名+剂量，或只有药名）
      3. 味组内再按「数字+量词」切，得 名/量 交替
      4. 整组只是剂量（「六两」）→ 并回上一味；量后注（碎/大者/半/余）并入量
      5. 「各等分」「各一两」「如鸡子大」单列
    """
    PH.clear()
    s = re.sub(r"[（(]([^）)]*)[）)]",
               lambda m: "%s" % chr(0xE000 + _ph(m.group(1))), line.strip())
    if not s:
        return []
    pat = re.compile(r"[一二三四五六七八九十百半两]{1,2}[升合铢斤分枚个片条茎把尺斗撮粒具颗钱丈寸匕两]")
    pairs = []
    for tok in re.split(r"[\s\u3000]+", s):
        tok = tok.strip("，。,．.；;")
        if not tok:
            continue
        if pat.fullmatch(tok) and pairs:          # 纯剂量组 → 并前
            pairs[-1][1] += tok
            continue
        if tok.startswith("各") and pat.fullmatch(tok[1:]) and pairs:
            pairs[-1][1] += tok              # 「各十八铢」
            continue
        segs, prev = [], 0
        for m in pat.finditer(tok):
            if m.start() == 0:
                continue
            segs.append(tok[prev:m.start()])
            prev = m.start()
        segs.append(tok[prev:])
        nm, li = None, ""
        for sg in segs:
            if not sg:
                continue
            if nm is not None and pat.match(sg):
                li += sg
            elif nm is not None and (sg in POST or sg in ("半", "余")):
                li += sg
            else:
                if nm is not None:
                    pairs.append([nm, li])
                nm, li = sg, ""
        if nm is not None:
            pairs.append([nm, li])

    pset = {chr(0xE000 + i) for i in range(len(PH))}
    out = []
    for nm, li in pairs:
        proc = "，".join(PH[ord(c) - 0xE000] for c in nm + li if c in pset)
        nm = "".join(c for c in nm if c not in pset)
        li = "".join(c for c in li if c not in pset)
        if not nm and li and out:
            out[-1]["量"] += li
            continue
        if not nm:
            continue
        for suf in ("各等分", "等分", "各"):
            if nm.endswith(suf):
                nm, li = nm[:-len(suf)], li + suf
                break
        if not nm and li and out:                 # 「各等分」单独成组 → 并前
            out[-1]["量"] += li
            continue
        if "如" in nm and not li:                 # 「石膏如鸡子大」
            nm, li = nm.split("如", 1)
            li = "如" + li
        if nm in ("各", "等分") or (nm.startswith("各") and not li):
            if out:
                out[-1]["量"] += nm + li
            continue
        if not li and nm in POST and out:
            out[-1]["制"] = (out[-1]["制"] + nm).strip("，")
            continue
        if nm in ("半", "余") and not li and out:
            out[-1]["量"] += nm
            continue
        out.append({"名": nm, "量": li, "制": proc})
    return out


def extract(lines, src):
    """从行序列抽方。返回 [dict]。"""
    fangs, i = [], 0
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        m = RE_NAME.match(s)
        if not m or s.startswith("#"):
            i += 1
            continue
        name = m.group(1) + "方"
        j = i + 1
        body, tail, jian = [], "", ""
        while j < n:
            t = lines[j].strip()
            if not t:
                j += 1
                continue
            if RE_NAME.match(t) or t.startswith("#"):
                break
            if RE_TAIL.match(t) or t.startswith("右") or t.startswith("上"):
                # 煎服法：可能连续多行
                # 煎服法只取当前行：向后无限收集会在「篇末无方名行」时吞掉整篇
                tail = t
                j += 1
                while j < n and lines[j].strip() and not RE_NAME.match(lines[j].strip()) \
                        and not lines[j].strip().startswith("#") \
                        and not re.search(r"[。；]$", lines[j].strip()):
                    tail += lines[j].strip()
                    j += 1
                break
            if RE_JIAN.search(t):
                jian = t
                j += 1
                continue
            body.append(t)
            j += 1
        yao = []
        for b in body:
            yao += split_yao(b)
        mt = RE_TAIL.match(tail)
        out = {
            "方名": name, "药味": yao, "味数": len(yao),
            "声明味数": cn2int(mt.group(1)) if mt else 0,
            "煎服": tail, "见前": jian, "原文行": s,
            "位置": i + 1, "源": src,
        }
        fangs.append(out)
        i = j
    return fangs


def main():
    os.makedirs(WORK, exist_ok=True)
    # 转录件
    raw = open(TXT, encoding="utf-8").read()
    lines = raw.split("\n")
    # 篇标注：向前找最近的 ## 标题
    heads = [(k, l[3:].strip()) for k, l in enumerate(lines) if l.startswith("## ")]
    pages = [(k, int(re.search(r"p(\d+)", l).group(1)))
             for k, l in enumerate(lines) if (mm := re.match(r"<!-- p(\d+) -->", l.strip()))]
    V = extract(lines, "转录件")
    for f in V:
        f["篇"] = next((h[1] for h in reversed(heads) if h[0] < f["位置"] - 1), "")
        f["页"] = next((p[1] for p in reversed(pages) if p[0] < f["位置"] - 1), None)
    json.dump(V, open(os.path.join(WORK, "方剂_V.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 电子文本：逐篇拼接（保留篇名）
    E = []
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".md"):
            continue
        ls = [l.rstrip("\n") for l in open(os.path.join(SRC, fn), encoding="utf-8")]
        fs = extract(ls, fn)
        for f in fs:
            f["篇"] = fn
            f["页"] = None
        E += fs
    json.dump(E, open(os.path.join(WORK, "方剂_E.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("转录件方 %d（唯一 %d）｜电子文本方 %d（唯一 %d）" % (
        len(V), len({f["方名"] for f in V}), len(E), len({f["方名"] for f in E})))
    # 自校验：声明味数 vs 实际味数
    for tag, arr in (("转录件", V), ("电子", E)):
        bad = [f for f in arr if f["声明味数"] and f["声明味数"] != f["味数"]]
        zero = [f for f in arr if not f["药味"] and not f["见前"] and not f["煎服"]]
        print("\n[%s] 声明味数≠实际味数 %d 首；无组成且无见前 %d 首" % (tag, len(bad), len(zero)))
        for f in (bad + zero)[:24]:
            print("  %-24s 声明%2d 实%2d 字=%d 见前=%s | %s" % (
                f["方名"], f["声明味数"], f["味数"], len(f["煎服"]), f["见前"] or "-",
                "／".join("%s%s" % (x["名"], x["量"]) for x in f["药味"])[:60]))


if __name__ == "__main__":
    main()
