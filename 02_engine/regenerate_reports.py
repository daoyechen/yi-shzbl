#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 viewer_data（注入后）重出人读产物：01 / 02 / 04 / 08。

assemble 生成的这些文件取自「版本包」，不含 H01/H02/M01/L01/L02/M02 六份回传的注入结果；
若不重出，`viewer_data` 与 `08_待复核清单` / `04_差异索引` 就是两个状态
（v0.3.0 上实测：viewer_data 的 review=6，08 却列 115 条）——违反「状态只有一个真源」。

只读 viewer_data，不碰骨架、不动版本包。

用法：
  python3 regenerate_reports.py --out 38_总装产出_金匮_v0.3.0
"""
import argparse
import json
import os
import re

B = "/Users/levi/Documents/医/共创/伤寒杂病论"


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(B, "38_总装产出_金匮_v0.3.0"))
    ap.add_argument("--book", default="金匮要略")
    a = ap.parse_args()
    out = a.out
    vd = jload(os.path.join(out, "viewer_data.json"))
    items = vd["items"]
    vers = vd["vers"]
    n_all = len(items)

    # ── 01 条文总表.json ─────────────────────────────────────────
    master = []
    for it in items:
        rec = {"条号": it["n"], "篇": it["pian"], "页": it["pg"],
               "宋本": it["s"], "各版": {}}
        for v in vers:
            c = it["v"].get(v) or {}
            if int(c.get("ok") or 0) == 1 and (c.get("t") or "").strip():
                rec["各版"][v] = {
                    "状态": "有", "置信": c.get("cf", ""), "页": c.get("pg", ""),
                    "异文": c.get("d") or c.get("t"),
                    "分段": [{"置信": c.get("cf", ""), "页": c.get("pg", ""),
                             "异文": c.get("d") or c.get("t"),
                             "原文": c.get("t"), "依据": c.get("ev", "")}],
                }
            else:
                rec["各版"][v] = {
                    "状态": "无",
                    "原因": c.get("rs") or c.get("ev") or "未取得",
                    "证据": c.get("ev", ""),
                }
        master.append(rec)
    with open(os.path.join(out, "01_条文总表.json"), "w", encoding="utf-8") as fh:
        json.dump({"骨架": "赵开美本《金匮要略方论》465 条(公共地基)",
                   "版本": vers, "条目": master,
                   "_说明": "v0.3.0 由 viewer_data 重出，已含六份回传注入结果"},
                  fh, ensure_ascii=False, indent=1)

    # ── 02 条文对照本.md ────────────────────────────────────────
    L = [f"# 《{a.book}》多版本条文对照本", "",
         "> **骨架**：赵开美本《金匮要略方论》465 条（公共地基，只读）。",
         f"> **版本**：{'、'.join(vers)}。",
         "> **对照单位**：条。差异以【】标出；某版缺此条者，注明**原因**。",
         "> **置信**：校记锚点 / 高置信 ≥0.85 / 中置信 ≥0.6 / 低置信 <0.6（列入待复核）。",
         "> **v0.3.0**：已注入 H01/H02/M01/L01/L02/M02 六份回传。", ""]
    cur = None
    for rec in master:
        if rec["篇"] != cur:
            cur = rec["篇"]
            L += [f"## {cur}", ""]
        L += [f"### 条 {rec['条号']}", "", f"**宋本**(p{rec['页']})：{rec['宋本']}", ""]
        for v in vers:
            c = rec["各版"][v]
            if c["状态"] == "有":
                L.append(f"- **{v}**（{c['置信']}，p{c['页']}）：{c['异文']}")
            else:
                L.append(f"- **{v}**：此版无 —— **{c['原因']}**。")
            L.append("")
        L += ["---", ""]
    open(os.path.join(out, "02_条文对照本.md"), "w", encoding="utf-8").write("\n".join(L))

    # ── 04 差异索引.md ──────────────────────────────────────────
    L = ["# 04 差异索引 · 金匮 465 条 × 4 版", "",
         "> 由 `viewer_data` 重出（v0.3.0，含 M01 989 格异文）。",
         "> 口径：以赵开美本（骨架 `宋本` 字段）为基准；本版脱字无法用【】表示，单列。", ""]
    ndiff = 0
    for rec in master:
        diffs = [(v, rec["各版"][v]["异文"]) for v in vers
                 if rec["各版"][v]["状态"] == "有" and "【" in rec["各版"][v]["异文"]]
        if diffs:
            ndiff += 1
            L += [f"## 条 {rec['条号']} 〔{rec['篇']}〕", ""]
            for v, mk in diffs:
                L.append(f"- **{v}**：{mk[:400]}")
            L.append("")
    L.insert(3, f"> {n_all} 条中，**{ndiff}** 条在至少一版存在文字差异。\n")
    open(os.path.join(out, "04_差异索引.md"), "w", encoding="utf-8").write("\n".join(L))

    # ── 08 待复核清单.md ────────────────────────────────────────
    L = ["# 08 待复核清单", "",
         "> 由 `viewer_data` 重出（v0.3.0）。口径＝`ok=0` 且 `tk` 为真，或 `cf=低置信`。",
         "> 与 `viewer_data.review` 同源，不再是 assemble 时的 115 条旧账。", "",
         "| 条号 | 版本 | 状态 | 页 | 原因 / 摘要 |", "| --- | --- | --- | --- | --- |"]
    n_low = 0
    for it in items:
        for v in vers:
            c = it["v"].get(v) or {}
            low = c.get("tk") or c.get("cf") == "低置信"
            if not low:
                continue
            n_low += 1
            txt = (c.get("t") or c.get("rs") or c.get("ev") or "")[:70].replace("\n", " ")
            L.append(f"| {it['n']} | {v} | 待核 | p{c.get('pg','')} | {txt} |")
    L.insert(3, f"> 共 **{n_low}** 格待复核（`viewer_data.review` 记 {len(vd.get('review') or [])} 条）。\n")
    open(os.path.join(out, "08_待复核清单.md"), "w", encoding="utf-8").write("\n".join(L))

    print(f"重出完成：01 条文总表（{len(master)} 条）、02 对照本、"
          f"04 差异索引（{ndiff} 条有异文）、08 待复核（{n_low} 格）")


if __name__ == "__main__":
    main()