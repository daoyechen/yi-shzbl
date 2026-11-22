#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""注本交付自检：查结构、条号、占位、契约字段。

用法：
    python3 自检_注本.py <交付目录> --side sh|jg [--id 注本ID]

退出码 0 = 通过，1 = 有硬伤。硬伤定义见 07_templates/注本任务书_模板.md 第七节。
"""
import json
import os
import re
import sys

SIDE_N = {"sh": 398, "jg": 465}
REQUIRED_MANIFEST = ("id", "name", "targets", "base", "source", "source_page",
                     "layer", "status", "条数", "覆盖", "text_source", "proof_level",
                     "files")
PLACEHOLDER = re.compile(r"待核|未决|存疑|TODO|XXX|？？|\?\?|【\s*】")
TAG_RESIDUE = re.compile(r"[<>]|属性：|<篇名>|<目录>")


def han(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    d = sys.argv[1]
    side = "jg"
    if "--side" in sys.argv:
        side = sys.argv[sys.argv.index("--side") + 1]
    N = SIDE_N.get(side)
    if not N:
        print("side 只能是 sh 或 jg")
        return 1

    errs, warns = [], []
    np_, mp = os.path.join(d, "notes.json"), os.path.join(d, "manifest.json")

    if not os.path.exists(np_):
        print("[硬伤] 缺 notes.json")
        return 1
    if not os.path.exists(mp):
        print("[硬伤] 缺 manifest.json")
        return 1

    try:
        notes = json.load(open(np_, encoding="utf-8"))
        man = json.load(open(mp, encoding="utf-8"))
    except Exception as e:
        print("[硬伤] JSON 解析失败：%s" % e)
        return 1

    # ---- manifest
    for k in REQUIRED_MANIFEST:
        if k not in man or man[k] in ("", None, [], {}):
            errs.append("manifest 缺字段 %s" % k)
    tgt = man.get("targets") or []
    if side == "jg" and "宋本" in tgt:
        warns.append("targets 写着宋本，但按 jg 侧交付——确认是否搞反了")

    # ---- notes
    if not isinstance(notes, list) or not notes:
        print("[硬伤] notes.json 不是非空数组")
        return 1

    prev = 0
    ns = []
    total = 0
    for i, x in enumerate(notes):
        if not isinstance(x, dict):
            errs.append("第 %d 项不是对象" % (i + 1))
            continue
        if "n" not in x or "text" not in x:
            errs.append("第 %d 项缺 n 或 text" % (i + 1))
            continue
        n = x["n"]
        if not isinstance(n, int):
            errs.append("第 %d 项 n 不是整数：%r" % (i + 1, n))
            continue
        if not (1 <= n <= N):
            errs.append("第 %d 项 n=%d 越界（1..%d）" % (i + 1, n, N))
        if n < prev:
            errs.append("第 %d 项 n=%d 小于前一条 %d（条号必须单调不减）" % (i + 1, n, prev))
        prev = max(prev, n)
        t = x["text"]
        if not isinstance(t, str) or not t.strip():
            errs.append("第 %d 项 text 为空" % (i + 1))
            continue
        if han(t) < 5:
            warns.append("第 %d 项（n=%d）只有 %d 个汉字，可能是碎片" % (i + 1, n, han(t)))
        m = PLACEHOLDER.search(t)
        if m:
            errs.append("第 %d 项（n=%d）正文含占位「%s」" % (i + 1, n, m.group(0)))
        if TAG_RESIDUE.search(t):
            errs.append("第 %d 项（n=%d）正文含标签残留「%s」" % (i + 1, n, TAG_RESIDUE.search(t).group(0)))
        if "\n" in t:
            warns.append("第 %d 项（n=%d）正文含硬换行" % (i + 1, n))
        ns.append(n)
        total += han(t)

    uniq = sorted(set(ns))
    cover = len(uniq) / float(N)

    print("=" * 56)
    print("交付目录 : %s" % d)
    print("侧       : %s（%d 条）" % (side.upper(), N))
    print("段数     : %d" % len(notes))
    print("条号     : %d 个，范围 %s..%s" % (len(uniq), uniq[0] if uniq else "-", uniq[-1] if uniq else "-"))
    print("覆盖     : %d/%d = %.1f%%" % (len(uniq), N, cover * 100))
    print("汉字     : %d" % total)
    print("=" * 56)

    # 与 manifest 自报对比
    if str(man.get("条数")) != str(len(notes)):
        warns.append("manifest 报条数 %s，实际段数 %d" % (man.get("条数"), len(notes)))
    print("\n硬伤 %d，提示 %d" % (len(errs), len(warns)))
    for e in errs[:30]:
        print("  [硬伤] " + e)
    if len(errs) > 30:
        print("  … 另 %d 条硬伤" % (len(errs) - 30))
    for w in warns[:20]:
        print("  [提示] " + w)
    if len(warns) > 20:
        print("  … 另 %d 条提示" % (len(warns) - 20))

    if errs:
        print("\n不合格：硬伤未清，不得交付")
        return 1
    print("\n通过（硬伤 0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
