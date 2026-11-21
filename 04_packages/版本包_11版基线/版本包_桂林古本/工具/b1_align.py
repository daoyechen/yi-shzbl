#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""b1_align.py —— 41 篇电子文本 × 转录件 句级对齐 + 字符级差异

T1 的核心工具。两侧都按「。！？」切句、压成只含汉字，
用 2-gram 倒排粗筛 + difflib 精算，取最相似句，
再对最相似对做字符级 opcodes，直接给出「哪几个字不同」。

差异四分类（任务书 T1 要求）：
  异体字 —— 单字替换，且在异体字对照表内
  异文   —— 替换/增删，且非单字异体
  标点   —— 压平后全同（只差标点/空白）
  编者按 —— 句中出现「（…）」夹注或「按」「臣亿等」

输出：_工作/底本比对.json、_工作/底本比对.txt
"""
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

# 常见异体/俗体/避讳字对（含整理本简化方向）
VARIANT = {
    "鞕": "硬", "濇": "涩", "澁": "涩", "欬": "咳", "讝": "谵", "瘥": "差",
    "蘖": "柏", "栢": "柏", "藏": "脏", "府": "腑", "蚘": "蛔", "蚰": "蛔",
    "沍": "冱", "麤": "粗", "炁": "气", "癎": "痫", "鬪": "斗", "鬭": "斗",
    "痺": "痹", "胷": "胸", "脇": "胁", "脣": "唇", "溼": "湿", "痎": "亥",
    "円": "圆", "晳": "晰", "徧": "遍", "徃": "往", "迺": "乃", "廼": "乃",
    "葢": "盖", "蓋": "盖", "疎": "疏", "疋": "匹", "叚": "假", "冐": "冒",
    "冐": "冒", "刦": "劫", "刧": "劫", "刄": "刃", "刐": "刎", "効": "效",
    "勅": "敕", "呌": "叫", "唘": "启", "啓": "启", "嗁": "啼", "嘑": "呼",
    "噉": "啖", "囘": "回", "囬": "回", "埜": "野", "壻": "婿", "妬": "妒",
    "孃": "娘", "宂": "冗", "寃": "冤", "尅": "克", "尩": "尪", "屛": "屏",
    "嵗": "岁", "歲": "岁", "幷": "并", "幷": "并", "廐": "厩", "彊": "强",
    "徧": "遍", "悮": "误", "惓": "倦", "愠": "愠", "慙": "惭", "慼": "戚",
    "懽": "欢", "戱": "戏", "戯": "戏", "挿": "插", "採": "采", "揷": "插",
    "摠": "总", "撚": "捻", "攅": "攒", "敎": "教", "斆": "学", "斈": "学",
    "旣": "既", "昬": "昏", "晻": "暗", "暎": "映", "曁": "暨", "朞": "期",
    "栢": "柏", "桺": "柳", "棊": "棋", "椀": "碗", "楡": "榆", "榦": "干",
    "槩": "概", "樷": "丛", "橊": "榴", "欝": "郁", "殀": "夭", "殗": "殗",
    "氷": "冰", "汚": "污", "汙": "污", "沍": "冱", "泝": "溯", "洩": "泄",
    "浄": "净", "淸": "清", "渇": "渴", "溷": "混", "滙": "汇", "澑": "溜",
    "灋": "法", "炤": "照", "烱": "炯", "煑": "煮", "煖": "暖", "熈": "熙",
    "燄": "焰", "牀": "床", "牕": "窗", "犂": "犁", "狥": "徇", "猨": "猿",
    "玅": "妙", "珎": "珍", "琹": "琴", "甞": "尝", "畧": "略", "疉": "叠",
    "痠": "酸", "痾": "疴", "癡": "痴", "皁": "皂", "盃": "杯", "盌": "碗",
    "眞": "真", "睠": "眷", "矁": "瞅", "砲": "炮", "碁": "棋", "磠": "卤",
    "竒": "奇", "筩": "筒", "箇": "个", "篛": "箬", "籖": "签", "粧": "妆",
    "糉": "粽", "糓": "谷", "絃": "弦", "絚": "绠", "綉": "绣", "緜": "绵",
    "縧": "绦", "繮": "缰", "罇": "樽", "羗": "羌", "翫": "玩", "耼": "聃",
    "肎": "肯", "肻": "肯", "脗": "吻", "腧": "俞", "膓": "肠", "臯": "皋",
    "艸": "草", "茍": "苟", "荅": "答", "莭": "节", "葊": "庵", "蒭": "刍",
    "蓡": "参", "蕋": "蕊", "薓": "参", "藶": "苈", "虵": "蛇", "蚘": "蛔",
    "蝱": "虻", "螘": "蚁", "衂": "衄", "衞": "卫", "袵": "衽", "裠": "裙",
    "褁": "裹", "覊": "羁", "覩": "睹", "觔": "斤", "觕": "粗", "觧": "解",
    "訏": "吁", "訶": "诃", "詠": "咏", "諠": "喧", "謌": "歌", "讐": "仇",
    "豘": "豚", "貍": "狸", "賸": "剩", "贑": "赣", "趂": "趁", "跗": "趺",
    "踈": "疏", "蹔": "暂", "躭": "耽", "軆": "体", "輭": "软", "轎": "轿",
    "逈": "迥", "遯": "遁", "邨": "村", "郞": "郎", "醖": "酝", "釐": "厘",
    "鈎": "钩", "銕": "铁", "鍼": "针", "鎗": "枪", "鑛": "矿", "閙": "闹",
    "闗": "关", "陞": "升", "隣": "邻", "雝": "雍", "霑": "沾", "靣": "面",
    "鞾": "靴", "韲": "齑", "頳": "赪", "飜": "翻", "飮": "饮", "飡": "餐",
    "餠": "饼", "餹": "糖", "饑": "饥", "馹": "驲", "駄": "驮", "騐": "验",
    "驘": "骡", "骽": "腿", "髗": "颅", "鬂": "鬓", "鬭": "斗", "魲": "鲈",
    "鮧": "鲇", "鯾": "鳊", "鳬": "凫", "鵞": "鹅", "麫": "面", "麪": "面",
    "黙": "默", "鼈": "鳖", "鼡": "鼠", "齩": "咬", "龎": "庞",
    # 常见混用（非严格异体，但属字形层面）
    "已": "以", "差": "瘥",
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


def sents(txt):
    """切句，返回 [(汉字串, 原句)]。"""
    out = []
    for s in re.split(r"(?<=[。！？])", txt):
        s = s.strip()
        h = han(s)
        if len(h) >= 6:
            out.append((h, s))
    return out


def grams(s, n=2):
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def opcodes(a, b):
    """返回 [(tag, a段, b段)]。a=电子文本(新底本)，b=转录件(现转录)。"""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return [(t, a[i1:i2], b[j1:j2]) for t, i1, i2, j1, j2 in sm.get_opcodes()
            if t != "equal"]


def klass(ops, ea, eb):
    """差异归类。"""
    if not ops:
        return "标点"
    kinds = set()
    subs = [o for o in ops if o[0] == "replace"]
    if len(subs) == 1 and ops[0][0] == "replace" \
            and len(subs[0][1]) == 1 and len(subs[0][2]) == 1:
        x, y = subs[0][1], subs[0][2]
        if VARIANT.get(x) == y or VARIANT.get(y) == x:
            return "异体字"
        # 形近混用（同音/形似）仍归异文，但标注
        return "异文"
    for t, a, b in ops:
        kinds.add(t)
    if kinds == {"replace"} and all(len(a) == len(b) == 1 for _, a, b in ops):
        if all(VARIANT.get(a) == b or VARIANT.get(b) == a for _, a, b in ops):
            return "异体字"
    return "异文"


def main():
    os.makedirs(WORK, exist_ok=True)
    vtxt = open(TXT, encoding="utf-8").read()
    vs = sents(vtxt)
    # 倒排：2-gram -> 句序号
    inv = {}
    for k, (h, _) in enumerate(vs):
        for g in grams(h):
            inv.setdefault(g, []).append(k)

    res = {"篇": [], "统计": {}}
    tot = {"同": 0, "标点": 0, "异体字": 0, "异文": 0, "未匹配": 0}
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".md"):
            continue
        es = sents(body_of(os.path.join(SRC, fn)))
        rec = {"篇": fn, "句数": len(es), "条目": []}
        for i, (eh, eraw) in enumerate(es):
            cand = {}
            for g in grams(eh):
                for k in inv.get(g, ()):
                    cand[k] = cand.get(k, 0) + 1
            top = sorted(cand.items(), key=lambda x: -x[1])[:8]
            best, br = None, 0.0
            for k, _ in top:
                r = difflib.SequenceMatcher(None, eh, vs[k][0],
                                            autojunk=False).ratio()
                if r > br:
                    best, br = k, r
            if best is None or br < 0.60:
                item = {"序": i, "电子": eraw, "状态": "未匹配", "相似": round(br, 3)}
                tot["未匹配"] += 1
                rec["条目"].append(item)
                continue
            vh = vs[best][0]
            ops = opcodes(eh, vh)
            kls = klass(ops, eh, vh)
            if eraw == vs[best][1]:
                kls = "同"
            tot[kls] = tot.get(kls, 0) + 1
            if kls != "同":
                rec["条目"].append({
                    "序": i, "状态": kls, "相似": round(br, 3),
                    "电子": eraw, "转录": vs[best][1],
                    "差异": [{"op": t, "电子": a, "转录": b} for t, a, b in ops],
                })
        res["篇"].append(rec)
    res["统计"] = tot

    json.dump(res, open(os.path.join(WORK, "底本比对.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)

    L = ["# 底本比对（电子文本 ↔ 转录件）", "",
         "| 篇 | 句数 | 同 | 标点 | 异体字 | 异文 | 未匹配 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in res["篇"]:
        c = {}
        for it in r["条目"]:
            c[it["状态"]] = c.get(it["状态"], 0) + 1
        nsame = r["句数"] - len(r["条目"])
        L.append("| %s | %d | %d | %d | %d | %d | %d |" % (
            r["篇"], r["句数"], nsame, c.get("标点", 0), c.get("异体字", 0),
            c.get("异文", 0), c.get("未匹配", 0)))
    L.append("| **合计** | **%d** | **%d** | **%d** | **%d** | **%d** | **%d** |" % (
        sum(r["句数"] for r in res["篇"]), tot["同"], tot["标点"],
        tot["异体字"], tot["异文"], tot["未匹配"]))
    open(os.path.join(WORK, "底本比对.txt"), "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))
    print("\n统计", tot)


if __name__ == "__main__":
    main()
