#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清洗 viewer_data 条文里的网页抓取残留（H03 回传附带发现）。

症状（v0.3.0 实测）：
  · 邓珍本 23 格，正文后挂 ~500 字符维基文库导航残留
      「File:新编金匮方论17.jpg / 查 论 编 / 《新编金匮方论》—汉·张仲景 / 目录 / …
        底本：《中华再造善本丛书》影印北京大学藏…」
  · 人卫本 24 格，尾部残留 `</div`
  · M01 注入异文后，残留会被当成异文包进【】，于是变成 `File:【新编金匮方论17.jpg`
    （固定字符串匹配会漏，必须按「File:」定位后整段截断）

修法：
  1. 从最早的残留起点（`File:` / `《新编金匮方论》—汉` / `底本：《中华再造善本`）整段截断；
     实测这些标记全部出现在正文之后，无前置、无夹杂。
  2. 再循环剥离尾部残留：`查 论 编`、半截 HTML 标签、未闭合的 `【`。
  3. 写修复记录，不静默改。

用法：
  python3 clean_viewer_junk.py --out 50_data/52_l1_assembly/jingui
  python3 clean_viewer_junk.py --out ... --dry   # 只报告
"""
import argparse
import json
import os
import re

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CUT_MARKS = [
    "File:",                       # 维基文库图片链接；【】可能插在 File: 之后，故只锚 File: 本身
    "《新编金匮方论》—汉",
    "《金匮要略方论》—汉",
    "底本：《中华再造善本",
]

# 尾部残留，循环剥离（长句在前）
TAIL_PATTERNS = [
    re.compile(r"<\s*/?\s*(?:div|span|p|br|td|tr|table|a|li|ul|b|em|strong|h\d)\b[^>]*>?\s*$", re.I),
    re.compile(r"\s*查\s*论\s*编\s*$"),
    re.compile(r"\s*【\s*$"),      # M01 留下的未闭合异文括号
    re.compile(r"\s+$"),
]


def clean_text(t):
    """返回 (新文本, 是否改动)"""
    if not t:
        return t, False
    orig = t
    cut = len(t)
    for m in CUT_MARKS:
        i = t.find(m)
        if i >= 0:
            cut = min(cut, i)
    if cut < len(t):
        t = t[:cut].rstrip()
    # 循环剥离尾部（可能连续多层：`</div`、`查 论 编`、`【`）
    for _ in range(8):
        before = t
        for pat in TAIL_PATTERNS:
            t = pat.sub("", t)
        if t == before:
            break
    return t, (t != orig)


def scan(vd):
    """返回 (格数, 字符数) 的残留统计"""
    bad = 0
    chars = 0
    for it in vd["items"]:
        for v in vd["vers"]:
            c = it["v"].get(v) or {}
            for fld in ("t", "d"):
                s = c.get(fld) or ""
                if any(m in s for m in CUT_MARKS) or "查\n论\n编" in s:
                    bad += 1
                    chars += len(s)
                elif TAIL_PATTERNS[0].search(s):
                    bad += 1
                    chars += len(s)
    return bad, chars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(B, "50_data", "52_l1_assembly", "jingui"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    vp = os.path.join(a.out, "viewer_data.json")
    vd = json.load(open(vp, encoding="utf-8"))

    before, _ = scan(vd)
    print(f"清洗前残留：{before} 格")

    changed, dropped = {}, {}
    for it in vd["items"]:
        for v in vd["vers"]:
            c = it["v"].get(v)
            if not c:
                continue
            for fld in ("t", "d"):
                if not c.get(fld):
                    continue
                new, ch = clean_text(c[fld])
                if ch:
                    changed.setdefault(v, []).append(it["n"])
                    dropped[v] = dropped.get(v, 0) + len(c[fld]) - len(new)
                    if not a.dry:
                        c[fld] = new

    for v in vd["vers"]:
        if v in changed:
            print(f"  {v}: {len(changed[v])} 格改写，删除 {dropped[v]} 字符")
    if not changed:
        print("  无需清洗")

    if a.dry:
        print("\n（dry-run，未写入）")
        return

    vd.setdefault("build_notes", {})
    note = ("v0.3.1 清洗：条文格内网页导航残留（邓珍「File:…jpg + 查论编 + 目录 + 底本说明」、"
            "人卫尾部 `</div`）已剔；只删残留，不动正文。")
    if isinstance(vd["build_notes"], dict):
        vd["build_notes"]["v0.3.1_清洗"] = note
    json.dump(vd, open(vp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    after, _ = scan(vd)
    print(f"\n已写入。清洗后残留：{after}（应为 0）")


if __name__ == "__main__":
    main()