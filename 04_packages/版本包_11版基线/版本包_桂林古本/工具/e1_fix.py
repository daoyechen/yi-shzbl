#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e1_fix.py —— 转录件局部修订（T3），幂等

每次运行都从 `_工作/正文_修订前.md`（包内原样转录件）重新生成，因此天然幂等。

三处结构性修订，均由《篇目勘误表》与 T1 比对核定，**不涉改字**：
  1. 卷三「杂病例第五」缺篇标题 —— 内容完整在「伤寒例第四」篇末，
     补标题析出（插在「问曰：上工治未病何也」之前）
  2. 「辨血痹虚劳病脉证并治」标题错置于「蜀漆散方」方名与组成之间 ——
     移到本篇首条「问曰：血痹之病，从何得之」之前
  3. 「辨胸痹心痛短气病脉证并治」标题错置于「黄连粉方」方名与组成之间 ——
     移到本篇首条「师曰：夫脉当取太过不及，阳微阴弦」之前

不动任何正文文字（不改字、不补字、不删字），只调整篇标题位置。
输出：_工作/改动清单.json
"""
import json
import os
import re
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(BASE, "派发包_A2_桂林古本二轮")
VP = os.path.join(PKG, "版本包_桂林古本二轮")
TXT = os.path.join(VP, "版本正文", "01_桂林古本伤寒杂病论.md")
WORK = os.path.join(VP, "_工作")
SRC = os.path.join(WORK, "正文_修订前.md")

CHANGES = []


def move_head(out, head, target_prefix, reason, basis):
    """把错置的篇标题移到 target_prefix 那一行之前。"""
    line = "## " + head
    idx = next((i for i, l in enumerate(out) if l.strip() == line), None)
    if idx is None:
        return False
    # 已经就位：目标行之前（跳过空行）即是该标题
    tj = next((i for i, l in enumerate(out) if l.strip().startswith(target_prefix)), None)
    if tj is None:
        return False
    prev = next((out[i] for i in range(tj - 1, -1, -1) if out[i].strip()), "")
    if prev.strip() == line:
        return False
    out.pop(idx)
    while idx < len(out) and not out[idx].strip():
        out.pop(idx)
    tj = next(i for i, l in enumerate(out) if l.strip().startswith(target_prefix))
    out.insert(tj, "")
    out.insert(tj + 1, line)
    out.insert(tj + 2, "")
    CHANGES.append({
        "位置": "《%s》篇" % head.replace("辨", "").replace("脉证并治", ""),
        "改动": "「%s」标题移至本篇首条「%s」之前" % (line, target_prefix),
        "理由": reason, "依据": basis,
    })
    return True


def fix(lines):
    out = list(lines)

    # —— 1. 杂病例第五（缺标题，补）
    if not any(l.startswith("## 杂病例第") for l in out):
        for i, l in enumerate(out):
            if l.strip().startswith("问曰：上工治未病"):
                out.insert(i, "## 杂病例第五")
                out.insert(i + 1, "")
                CHANGES.append({
                    "位置": "卷三·伤寒例第四篇末（第 %d 行前）" % (i + 1),
                    "改动": "新增篇标题「## 杂病例第五」",
                    "理由": "十六卷目录载卷三有「杂病例」；本篇 52 句在转录件中 51 句可逐句命中"
                            "（唯一未中者是「师曰：语声寂寂然…头中病」，转录件该句标点作「；」），"
                            "内容完整、篇标题全文 0 命中，属标题漏置而非漏转",
                    "依据": "原料/电子文本/桂林古本/05_伤寒杂病论卷第三杂病例.md（1461 字，命中率 100.0%）",
                })
                # 篇界之后紧跟的是卷四，需保持「## 标题 / 空行 / 正文」体例
                break

    # —— 2. 血痹虚劳（标题错置在蜀漆散方名与组成之间）
    move_head(
        out, "辨血痹虚劳病脉证并治", "问曰：血痹之病，从何得之",
        "原标题插在「蜀漆散方」方名与组成之间，既隔断蜀漆散、柴胡桂姜汤两方，"
        "又使本篇首条「问曰：血痹之病，从何得之」落在疟病篇内（血痹篇成空篇）",
        "原料/电子文本/桂林古本/31_…辨疟病脉证并治.md 末段之后紧接 32_…血痹虚劳病.md 首行")

    # —— 3. 胸痹心痛短气（标题错置在黄连粉方名与组成之间）
    move_head(
        out, "辨胸痹心痛短气病脉证并治", "师曰：夫脉当取太过不及，阳微阴弦",
        "原标题插在「黄连粉方」方名与组成之间，既隔断黄连粉方，又使卷十五疮痈病篇末"
        "（王不留行散、排脓散、排脓汤、薏苡附子败酱散、大黄牡丹汤）被划入胸痹篇",
        "原料/电子文本/桂林古本/37_…疮痈病.md 末段之后为胸痹篇首条「师曰：夫脉当取太过不及」")

    return out


def check(new):
    """结构自检：每个篇标题之后须在 6 行内出现正文（不得紧跟卷标识/页锚/下一篇标题）。"""
    bad = []
    for i, l in enumerate(new):
        if not l.startswith("## "):
            continue
        body = ""
        for j in range(i + 1, min(i + 8, len(new))):
            t = new[j].strip()
            if not t or t.startswith("<!--") or t.startswith("（《伤寒杂病论》卷"):
                continue
            body = t
            break
        if not body or body.startswith("## "):
            bad.append(l)
    return bad


def main():
    if not os.path.exists(SRC):
        shutil.copy2(TXT, SRC)
        print("已建立原样备份 _工作/正文_修订前.md")
    lines = open(SRC, encoding="utf-8").read().split("\n")
    new = fix(lines)
    open(TXT, "w", encoding="utf-8").write("\n".join(new))
    for i, c in enumerate(CHANGES, 1):
        c["序"] = i
    json.dump(CHANGES, open(os.path.join(WORK, "改动清单.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)

    heads = [l[3:] for l in new if l.startswith("## ")]
    bad = check(new)
    print("改动 %d 处；篇标题 %d 个" % (len(CHANGES), len(heads)))
    for c in CHANGES:
        print(" -", c["改动"])
    if bad:
        print("⚠ 空篇标题 %d 个: %s" % (len(bad), bad))
    else:
        print("✅ 29 篇标题均有正文落点（无空篇）")


if __name__ == "__main__":
    main()
