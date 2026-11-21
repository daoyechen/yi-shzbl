#!/usr/bin/env python3
"""文本工具:与《伤寒论》转录件的排版约定绑定。

约定(不可改):
  - 转录件为 UTF-8 Markdown,`---` 之后为正文
  - 每一页以 `<!-- pN -->` 标记,N = 原书 PDF 页码
  - 缺字以 □ 保留,异体字一仍其旧(不校订)
"""
import re

DIG = {'〇': 0, '零': 0, '○': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
       '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '百': 100}
NUMCH = "〇零○一二三四五六七八九十百"


def load(path):
    """读转录件,返回 `---` 之后的正文。"""
    t = open(path, encoding="utf-8").read()
    return t.split("---", 1)[1]


def page_blocks(text):
    """按 <!-- pN --> 切成 (页码, 该页行列表);首个标记前的内容并入第一页。"""
    parts = re.split(r"<!-- p(\d+) -->", text)
    out = []
    for i in range(1, len(parts), 2):
        lines = [l.rstrip() for l in parts[i + 1].split("\n")
                 if l.strip() and not l.strip().startswith("<!--")]
        if i == 1 and parts[0].strip():
            head = [l.rstrip() for l in parts[0].split("\n") if l.strip()]
            lines = head + lines
        out.append((int(parts[i]), lines))
    return out


def is_footnote(s):
    """圈码脚注行(① 等开头)。"""
    return bool(re.match(r"^[①-⑳]", s.strip()))


def is_yaofang(s):
    """方名行 / 药行 / 「上X味」行 —— 这类行不参与条文匹配,直接归属前一条。"""
    s = s.strip()
    if re.match(r"^[一-龥]{2,10}方[①-⑳]?$", s):
        return True
    if re.match(r"^上[①-⑳]?[一二三四五六七八九十]+味", s):
        return True
    if s and s[-1] not in "。？！；：":
        if re.search(r"[两升合枚分钱个只斛斤]", s) and \
           not re.search(r"(主之|宜|云：|作：|不可|不得|而|则|之)", s):
            return True
    return False


def strip_for_match(s):
    """比对用:去脚注圈码、方次括注、「一作」等旁注、空白。"""
    s = re.sub(r"[①-⑳]", "", s)
    s = re.sub(r"\[[方一二三四五六七八九十百千0-9]+\]", "", s)
    s = re.sub(r"[〔（(][方一二三四五六七八九十百千0-9]+[〕）)]", "", s)
    s = re.sub(r"一作[：:][^，。；]{0,8}", "", s)
    s = re.sub(r"\s+", "", s)
    return s


def ngrams(s, n=3):
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def diff_mark(base, other):
    """标出 other 相对 base 的差异片段,差异部分用【】括起。"""
    import difflib
    if not base or not other:
        return other
    sm = difflib.SequenceMatcher(None, base, other, autojunk=False)
    res = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            res.append(other[j1:j2])
        else:
            frag = other[j1:j2]
            if frag:
                res.append(f"【{frag}】")
    return "".join(res)
