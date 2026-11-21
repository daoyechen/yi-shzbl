#!/usr/bin/env python3
"""宋本切条的补充工具 —— 只取**无条号篇**。

骨架 `宋本398条.json` 只含 398 条**有编号**的条(对照的主坐标系)。
宋本另有辨脉法、平脉法、伤寒例、辨痉湿暍、可·不可发汗吐下等**无编号篇**,
这些篇在对照体系中以「篇」为对照单位,需从宋本转录件切取。

切条规则(与主引擎严格一致 —— 逐位校验「每条只认期望的下一个编号」):
  - 遇篇目标题 → 开启新篇;若上一篇仍悬着编号,则该编号为「无编号篇」的内容
  - 遇符合期望编号的行 → 切出一条,期望号 +1
  - 不符合期望编号的行 → 归入当前篇(无编号部分)
  - 篇首行带编号 → 该篇有编号;否则为无编号篇
"""
import re

NUMCH = "〇零○一二三四五六七八九十百"

# 宋本篇目标题
PIAN_RE = re.compile(
    r"^(辨[一-鿿]{2,12}脉证并治[上下中]?第[一二三四五六七八九十百]+"
    r"|辨痉湿暍脉证第[一二三四五六七八九十百]+"
    r"|伤寒例第[一二三四五六七八九十百]+"
    r"|平脉法第[一二三四五六七八九十百]+"
    r"|辨脉法第[一二三四五六七八九十百]+"
    r"|辨厥利呕哕[^。]{0,12}第[一二三四五六七八九十百]+"
    r"|辨[一-鿿]{2,14}第[一二三四五六七八九十百]+)")

DIG = {'〇': 0, '零': 0, '○': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
       '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '百': 100}


def cn2int(s):
    if not s:
        return None
    if "十" in s:
        a, b = s.split("十", 1)
        tens = DIG.get(a, 1) if a else 1
        units = DIG.get(b, 0) if b else 0
        return tens * 10 + units
    if len(s) == 3:
        return DIG.get(s[0], 0) * 100 + DIG.get(s[1], 0) * 10 + DIG.get(s[2], 0)
    if len(s) == 2:
        return DIG.get(s[0], 0) * 10 + DIG.get(s[1], 0)
    return DIG.get(s, None)


def exp_digits(v):
    if v < 10:
        return [v]
    if v == 10:
        return [1, 0]
    if v < 20:
        return [1, v - 10]
    if v < 100:
        return [v // 10, v % 10]
    return [v // 100, (v // 10) % 10, v % 10]


def tok_digits(tok):
    if "十" in tok:
        a, b = tok.split("十", 1)
        tens = 1
        if a:
            tens = "一二三四五六七八九".index(a) + 1 if a in "一二三四五六七八九" else None
        units = 0
        if b:
            units = "一二三四五六七八九".index(b) + 1 if b in "一二三四五六七八九" else None
        return [tens, units]
    out = []
    for ch in tok:
        if ch in "〇零○":
            out.append(0)
        elif ch in "一二三四五六七八九":
            out.append("一二三四五六七八九".index(ch) + 1)
        else:
            out.append(None)
    return out


def try_num(tok, expect):
    ed = exp_digits(expect)
    td = tok_digits(tok)
    if len(td) == len(ed):
        if all(a == b for a, b in zip(td, ed)):
            return True, False
        if all(a is None or a == b for a, b in zip(td, ed)):
            return True, True
    real = [a for a in td if a is not None]
    if len(td) > len(ed) and len(real) == len(ed) - 1 and real == ed[1:]:
        return True, True
    return False, False


def songben_parts(path):
    """切出宋本全部内容:返回 [{no, pian, page, text}]。

    no=None 的项 = 无编号部分(篇首材料或无编号篇)。
    与主引擎 `pipeline.split_songben` 同规则。
    """
    from . import textutil as T
    body = T.load(path)
    body = body[body.find("伤寒论卷第一"):]
    blocks = T.page_blocks(body)
    items = []
    cur_pian, cur = None, None
    expect = 1
    for pno, lines in blocks:
        for ln in lines:
            st = ln.strip()
            if st.startswith("## ") or st.startswith("**"):
                s2 = st[3:].strip() if st.startswith("## ") else st.strip("*").strip()
                m = PIAN_RE.match(s2)
                if m and s2 != cur_pian:
                    if cur is not None:
                        items.append(cur)
                        cur = None
                    cur_pian = s2
                continue
            if re.fullmatch(r"[0-9]{1,4}", st):
                continue
            tok = re.match(rf"^([-—–‐－\.·]{{0,3}}[{NUMCH}①-⑳]+)", st)
            got = None
            if tok:
                t = tok.group(1).rstrip("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳")
                ok, _ = try_num(t, expect)
                if ok:
                    got = expect
            if got is not None:
                if cur:
                    items.append(cur)
                cur = {"no": got, "pian": cur_pian, "page": pno, "text": st}
                expect += 1
            else:
                if cur:
                    cur["text"] += "\n" + st
                else:
                    items.append({"no": None, "pian": cur_pian, "page": pno,
                                  "text": st, "_nohao": True})
    if cur:
        items.append(cur)
    # 合并相邻的无编号项
    merged = []
    for it in items:
        if it.get("_nohao") and merged and merged[-1].get("_nohao") and merged[-1]["pian"] == it["pian"]:
            merged[-1]["text"] += "\n" + it["text"]
            merged[-1]["page_end"] = it["page"]
        else:
            merged.append(dict(it))
    return merged


def norm_pian(s):
    if not s:
        return ""
    s = re.sub(r"^《[^》]*》", "", s)
    s = re.sub(r"第[一二三四五六七八九十百]+.*$", "", s)
    s = re.sub(r"\s*合[一二三四五六七八九十百]+法.*$", "", s)
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = s.replace("**", "").strip()
    s = s.replace("形证治", "脉证并治").replace("病形证", "病脉证并治")
    return s


def songben_no_number(path):
    """宋本**无编号篇**:返回 [{pian, page, len}]。"""
    out = []
    for it in songben_parts(path):
        if it["no"] is not None:
            continue
        name = norm_pian(it.get("pian") or "")
        if not name:
            continue
        text = it.get("text", "")
        # 去掉纯目录/标题残留:无编号篇必须有实质内容
        if len(text) < 20:
            continue
        if out and out[-1]["n"] == name:
            out[-1]["len"] += len(text)
            out[-1]["pg_end"] = it["page"]
        else:
            out.append({"n": name, "pg": it["page"], "pg_end": it["page"],
                        "len": len(text)})
    return out


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else \
        "/workspace/output/伤寒论版本大全/版本正文/07_宋本伤寒论.md"
    for r in songben_no_number(p):
        print(f"  p{r['pg']}-{r.get('pg_end', r['pg'])}  {r['n'][:30]:<32} ({r['len']}字)")
