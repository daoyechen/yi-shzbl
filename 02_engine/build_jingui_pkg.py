#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""金匮各版 md 原文 → 版本包形态（供 shjkit.assemble --骨架 jingui 使用）

背景
----
27 号交付里金匮 5 版是 md 原文（`## 条 N · 篇名` + 正文），不是
`交付/版本包.json` 形态。本脚本做这一层转换。

对齐依据（已实测，非推测）
------------------------
5 版 md 均为 **1556 个 `## 条 N`，N = 1..1556 连续**，N 即骨架
`条目[].句[].源no`。骨架 465 条每条辖若干段（1–5 段），故：

    骨架条 no 的本版正文 = md 中 `句[].源no` 各段正文按序拼接

- 全部段为「（本版此条未检出）」→ 状态=无
- 部分段检出            → 状态=有，分段只含已检出段，置信降为中置信
- 全部段检出            → 状态=有，置信=高置信

首版异文留空
------------
`异文` 需逐字比对（引擎 align.py），本脚本不做，写空串。
assemble 会把它拼成 `d` 字段，空串即不显示差异高亮。
补比对属独立工序，不在本脚本职责内。

用法
----
    python3 build_jingui_pkg.py <版本正文md> --name 赵开美本1599 \
        --out ../版本包_金匮基线/版本包_赵开美本1599
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shjkit import skeleton as SK  # noqa: E402

UNDETECTED = "（本版此条未检出）"

# <!-- p12 --> 换行 ## 条 12 · 篇名 换行空行 正文（直到下一个 <!-- p 或文件尾）
BLOCK = re.compile(
    r"<!--\s*p(\d+)\s*-->\s*\n##\s*条\s*(\d+)\s*·\s*([^\n]*)\n([\s\S]*?)(?=<!--\s*p\d+\s*-->|\Z)"
)


def parse_md(path):
    """→ {段号: {"篇":str, "正文":str, "未检出":bool}}"""
    raw = open(path, encoding="utf-8").read()
    segs = {}
    for m in BLOCK.finditer(raw):
        anchor, no, pian, body = int(m.group(1)), int(m.group(2)), m.group(3).strip(), m.group(4)
        body = body.strip()
        if anchor != no:
            # 锚点与条号不一致时以条号为准，但记账
            segs.setdefault("__mismatch__", []).append((anchor, no))
        segs[no] = {"篇": pian, "正文": body, "未检出": body == UNDETECTED or not body}
    segs.pop("__mismatch__", None) if "__mismatch__" in segs else None
    return segs, raw


def build(md_path, version_name):
    sk_items = SK.load_skeleton("jingui")
    sk_spec = SK.skel_spec("jingui")
    md, raw = parse_md(md_path)

    # 文件头声明行（用于原始资料索引）
    heads = [l.strip() for l in raw.split("\n")[:8] if l.strip().startswith(">")]

    entries = []
    n_ok = n_none = n_partial = 0
    for it in sk_items:
        no = it["no"]
        segno = [j["源no"] for j in it.get("句") or []]
        segs = []
        missing = []
        for sn in segno:
            cell = md.get(sn)
            if cell is None:
                missing.append(sn)
                continue
            if cell["未检出"]:
                missing.append(sn)
                continue
            segs.append({
                "页": sn,                      # 转录段号（金匮无影印页信息）
                "原文": cell["正文"],
                "异文": "",                    # 待 align 工序补
                "置信": "高置信" if not missing else "中置信",
            })
        base = {
            "条号": no,
            "篇": it["篇"],
            "页": it.get("段首", it.get("页")),
            "宋本": it["原文"],
        }
        if not segs:
            n_none += 1
            entries.append(dict(base, **{
                "状态": "无",
                "原因": "本版未检出",
                "证据": f"骨架 no{no} 辖段 {segno}，该版此 {len(segno)} 段均标「{UNDETECTED}」",
            }))
        elif missing:
            n_partial += 1
            entries.append(dict(base, **{
                "状态": "有",
                "置信": "中置信",
                "分段": segs,
                "原文": "\n".join(s["原文"] for s in segs),
                "异文": "",
                "证据": f"辖段 {segno} 中缺 {missing}",
            }))
        else:
            n_ok += 1
            entries.append(dict(base, **{
                "状态": "有",
                "置信": "高置信",
                "分段": segs,
                "原文": "\n".join(s["原文"] for s in segs),
                "异文": "",
            }))

    # 篇目：按 md 的篇名出现顺序聚合
    order, seen = [], {}
    for sn in sorted(k for k in md if isinstance(k, int)):
        p = md[sn]["篇"]
        if p not in seen:
            seen[p] = {"名": p, "raw": p, "页": sn, "字数": 0}
            order.append(seen[p])
    for e in entries:
        if e["状态"] == "有":
            for x in order:
                if x["名"] == e["篇"]:
                    x["字数"] += len(e["原文"])

    pack = {
        "版本名": version_name,
        "骨架": sk_spec.get("名称", "金匮条级骨架"),
        "条目": entries,
        "独有": [],
        "锚点": [],
        "方剂": [],
        "篇目": order,
        "原因分布": {"本版未检出": n_none},
        "统计": {
            "对上条数": n_ok + n_partial,
            "高置信": sum(1 for e in entries if e.get("置信") == "高置信"),
            "独立内容": 0,
            "方剂数": 0,
            "待复核": n_partial,
            "条数": len(entries),
        },
        "_生成": {
            "源文件": os.path.basename(md_path),
            "头部声明": heads,
            "md段数": len([k for k in md if isinstance(k, int)]),
            "骨架条数": len(sk_items),
            "状态分布": {"有_全覆盖": n_ok, "有_部分缺": n_partial, "无": n_none},
            "异文": "未做（待 align 工序）",
            "方剂": "未抽（待补）",
            "独有": "未判定（md 为骨架框架，无骨架外内容）",
        },
    }
    return pack


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--name", required=True, help="版本名（进 viewer 的版本 tab）")
    ap.add_argument("--out", required=True, help="版本包目录")
    args = ap.parse_args()

    pack = build(args.md, args.name)
    os.makedirs(os.path.join(args.out, "交付"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "版本正文"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "_工作"), exist_ok=True)

    with open(os.path.join(args.out, "交付", "版本包.json"), "w", encoding="utf-8") as fh:
        json.dump(pack, fh, ensure_ascii=False, indent=1)

    # 转录件随包（spec 约定）
    import shutil
    shutil.copy2(args.md, os.path.join(args.out, "版本正文", os.path.basename(args.md)))

    with open(os.path.join(args.out, "spec.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "版本名": args.name,
            "骨架": "jingui",
            "文件": os.path.basename(args.md),
            "转录层": "段级（md 已含 <!-- pN --> 锚点，N=骨架句级源no）",
            "异文": "未做",
            "方剂": "未抽",
            "生成": "build_jingui_pkg.py",
        }, fh, ensure_ascii=False, indent=1)

    g = pack["_生成"]
    print(f"{args.name}  →  {args.out}")
    print(f"  条 {g['骨架条数']} | 有·全覆盖 {g['状态分布']['有_全覆盖']} "
          f"| 有·部分缺 {g['状态分布']['有_部分缺']} | 无 {g['状态分布']['无']}")
    print(f"  md 段数 {g['md段数']} | 篇目 {len(pack['篇目'])}")


if __name__ == "__main__":
    main()
