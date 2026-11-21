#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b2_diff.py —— 电子文本 × 转录件 锚点分段 + 段内字符级 diff（T1 主工具）

为什么不按句对齐：两侧分句粒度不同（电子文本按「；」断，转录件连成一句），
句子级最近邻匹配必然错位，把「串行」误报成「异文」。

做法：
  1. 两侧都压成只含汉字的长串（丢标点空白 —— 标点差异单独统计）
  2. 取电子文本中「双向唯一」的 20-gram 作锚点（E 中唯一且 V 中唯一）
  3. 锚点按 V 位置做最长递增子序列，剔除错位锚
  4. 相邻锚点之间做 SequenceMatcher 局部对齐，收 opcodes
  5. 按 E 的篇边界把差异归篇，按 V 的页锚给出页码

输出：_工作/差异明细.json、_工作/差异汇总.txt
"""
import bisect
import difflib
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

VARIANT = {
    "鞕": "硬", "濇": "涩", "澁": "涩", "欬": "咳", "讝": "谵",
    "蘖": "柏", "栢": "柏", "蚘": "蛔", "癎": "痫", "痺": "痹",
    "胷": "胸", "脇": "胁", "脣": "唇", "溼": "湿", "徧": "遍",
    "迺": "乃", "廼": "乃", "葢": "盖", "疎": "疏", "叚": "假",
    "効": "效", "啓": "启", "嗁": "啼", "嘑": "呼", "噉": "啖",
    "囘": "回", "塜": "冢", "壻": "婿", "妬": "妒", "寃": "冤",
    "尅": "克", "屛": "屏", "歲": "岁", "幷": "并", "彊": "强",
    "悮": "误", "慙": "惭", "戱": "戏", "挿": "插", "採": "采",
    "摠": "总", "敎": "教", "旣": "既", "昬": "昏", "朞": "期",
    "椀": "碗", "楡": "榆", "槩": "概", "氷": "冰", "汚": "污",
    "浄": "净", "淸": "清", "渇": "渴", "煑": "煮", "煖": "暖",
    "牀": "床", "甞": "尝", "畧": "略", "癡": "痴", "皁": "皂",
    "盃": "杯", "眞": "真", "砲": "炮", "竒": "奇", "箇": "个",
    "絃": "弦", "綉": "绣", "羗": "羌", "肎": "肯", "膓": "肠",
    "艸": "草", "荅": "答", "莭": "节", "蓡": "参", "薓": "参",
    "虵": "蛇", "蝱": "虻", "衂": "衄", "衞": "卫", "裠": "裙",
    "覩": "睹", "觔": "斤", "觧": "解", "訶": "诃", "諠": "喧",
    "貍": "狸", "賸": "剩", "踈": "疏", "蹔": "暂", "躭": "耽",
    "軆": "体", "輭": "软", "逈": "迥", "遯": "遁", "郞": "郎",
    "醖": "酝", "鈎": "钩", "鍼": "针", "闗": "关", "陞": "升",
    "隣": "邻", "霑": "沾", "靣": "面", "飮": "饮", "飡": "餐",
    "餠": "饼", "饑": "饥", "騐": "验", "髗": "颅", "麫": "面",
    "麪": "面", "黙": "默", "鼈": "鳖", "鼡": "鼠", "龎": "庞",
}


def han(s):
    return "".join(c for c in s if "\u4e00" <= c <= "\u9fff")


def body_of(path):
    out = []
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(">") or s == "---":
            continue
        out.append(s)
    lines = "\n".join(out).strip().split("\n")
    if lines and len(lines[0]) <= 20 and "\u3002" not in lines[0]:
        lines = lines[1:]
    return "\n".join(lines).strip()


def lis(pairs):
    """按 V 位置取最长递增子序列，保留 (e_pos, v_pos)。"""
    if not pairs:
        return []
    vs = [b for _, b in pairs]
    tails, idx = [], []
    prev = [-1] * len(pairs)
    for i, x in enumerate(vs):
        j = bisect.bisect_left(tails, x)
        if j == len(tails):
            tails.append(x)
            idx.append(i)
        else:
            tails[j] = x
            idx[j] = i
        prev[i] = idx[j - 1] if j > 0 else -1
    out, k = [], idx[-1]
    while k >= 0:
        out.append(pairs[k])
        k = prev[k]
    return out[::-1]


def anchors_of(E, V, n=20, step=60):
    out, i = [], 0
    while i <= len(E) - n:
        g = E[i:i + n]
        if E.count(g) == 1:
            p = V.find(g)
            if p >= 0 and V.count(g) == 1:
                out.append((i, p))
                i += step
                continue
        i += 10
    return lis(out)


def main():
    os.makedirs(WORK, exist_ok=True)
    # 电子文本拼接（按卷序 = 文件名序），记录篇边界
    parts, bounds, pos = [], [], 0
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".md"):
            continue
        h = han(body_of(os.path.join(SRC, fn)))
        parts.append(h)
        bounds.append((pos, pos + len(h), fn))
        pos += len(h)
    E = "".join(parts)

    # 转录件：压平 + 记录页锚位置
    raw = open(TXT, encoding="utf-8").read()
    marks = [(m.start(), int(m.group(1))) for m in re.finditer(r"<!--\s*p(\d+)\s*-->", raw)]
    # 结构行（篇标题 / 卷标识 / 一级标题）不是正文，压平时整行跳过，
    # 否则会被当成「转录件多出的文字」报成假差异
    skip = [False] * len(raw)
    for m in re.finditer(r"^(?:#+\s+.*|[（(]《伤寒杂病论》[^）)]*[）)])\s*$",
                         raw, re.M):
        for i in range(m.start(), m.end()):
            skip[i] = True
    ch, keep = [], {}
    for i, c in enumerate(raw):
        if skip[i]:
            continue
        if "\u4e00" <= c <= "\u9fff":
            keep.setdefault(len(ch), i)
            ch.append(c)
    V = "".join(ch)

    # 篇标题在 V 中的位置
    vheads = []
    for m in re.finditer(r"^##\s+(.+)$", raw, re.M):
        p = sum(1 for i, c in enumerate(raw[:m.start()])
                if ("\u4e00" <= c <= "\u9fff") and not skip[i])
        vheads.append((p, m.group(1).strip()))

    def vpage(p):
        """V 中第 p 个汉字对应的页码。"""
        oi = keep.get(p, 0)
        pg = None
        for a, n in marks:
            if a <= oi:
                pg = n
        return pg

    def vpian(p):
        r = "（篇前）"
        for a, nm in vheads:
            if a <= p:
                r = nm
        return r

    def epian(p):
        for a, b, fn in bounds:
            if a <= p < b:
                return fn
        return bounds[-1][2]

    anc = anchors_of(E, V)
    print("锚点 %d 个" % len(anc))
    ops = []
    seg = [(0, 0)] + anc + [(len(E), len(V))]
    for (ea, va), (eb, vb) in zip(seg, seg[1:]):
        if eb < ea or vb < va:
            continue
        sm = difflib.SequenceMatcher(None, E[ea:eb], V[va:vb], autojunk=False)
        for t, i1, i2, j1, j2 in sm.get_opcodes():
            if t == "equal":
                continue
            ops.append({
                "E位置": ea + i1, "V位置": va + j1,
                "篇": epian(ea + i1), "落点": vpian(va + j1), "页": vpage(va + j1),
                "电子": E[ea + i1:ea + i2], "转录": V[va + j1:va + j2],
                "op": t,
            })
    print("原始差异 %d 处" % len(ops))

    # 归类
    def klass(o):
        a, b, t = o["电子"], o["转录"], o["op"]
        if t == "replace" and len(a) == len(b) == 1:
            return "异体字" if VARIANT.get(a) == b or VARIANT.get(b) == a else "异文"
        if t == "replace" and len(a) == len(b) and all(
                VARIANT.get(x) == y or VARIANT.get(y) == x for x, y in zip(a, b)):
            return "异体字"
        return "异文"

    for o in ops:
        o["类型"] = klass(o)

    # 合并相邻同类（同一段内的细碎 op 合为一条，便于人工判读）
    merged = []
    for o in ops:
        if merged and o["E位置"] - merged[-1]["E末"] <= 3 \
                and o["篇"] == merged[-1]["篇"] and o["类型"] == merged[-1]["类型"]:
            m = merged[-1]
            m["电子"] += "□" + o["电子"]
            m["转录"] += "□" + o["转录"]
            m["E末"] = o["E位置"] + len(o["电子"])
        else:
            o["E末"] = o["E位置"] + len(o["电子"])
            merged.append(dict(o))
    print("合并后 %d 处" % len(merged))

    json.dump({"差异": merged, "E字数": len(E), "V字数": len(V),
               "锚点": len(anc)},
              open(os.path.join(WORK, "差异明细.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 汇总
    from collections import Counter, defaultdict
    c = Counter(o["类型"] for o in merged)
    byp = defaultdict(lambda: Counter())
    for o in merged:
        byp[o["篇"]][o["类型"]] += 1
    L = ["# 差异汇总（电子文本 ↔ 转录件）", "",
         "锚点 %d、差异 %d 处（电子 %d 字 / 转录 %d 字）" % (len(anc), len(merged), len(E), len(V)),
         "", "| 类型 | 处数 |", "|---|---:|"]
    for k in ("异体字", "异文"):
        L.append("| %s | %d |" % (k, c.get(k, 0)))
    L += ["", "| 篇 | 异体字 | 异文 | 合计 |", "|---|---:|---:|---:|"]
    for fn, cnt in sorted(byp.items()):
        L.append("| %s | %d | %d | %d |" % (fn, cnt.get("异体字", 0),
                                            cnt.get("异文", 0), sum(cnt.values())))
    open(os.path.join(WORK, "差异汇总.txt"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
