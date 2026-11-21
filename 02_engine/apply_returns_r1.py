#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 H01 / H02 / M01 三份回传结果注入金匮总装产出（v0.2.0）。

只动派生产物，不动 `版本包_金匮基线_v2` 与 `版本正文_金匮` 原件。

做四件事：
  1. H02：15 个私用区码位 → 本字，替换 viewer_data 各版 t/d（1:1，不改长度）
  2. H01：115 格定性回填 viewer_data 的 ok/cf/ev；review 收敛为 1 条存疑
  3. M01：989 格异文标注（带【】）写入各版 d，驱动页面高亮与「只看异文」
  4. 重算 stats，写 `12_回传结果应用.md`

用法：
    python3 apply_returns_r1.py [--out 38_总装产出_金匮_v0.2.0]
"""
import argparse
import json
import os
import re
import shutil

B = "/Users/levi/Documents/医/共创/伤寒杂病论"
R = os.path.join(B, "37_回传验收_r1")
H01 = os.path.join(R, "回传包_H01_待核校核定_r2/H01_待核校核定_人工/交付/H01_待核校核定_交付.json")
H02 = os.path.join(R, "H02_医统缺字识别_人工/交付/H02_医统缺字_交付.json")
M01 = os.path.join(R, "回传包_M01_异文对齐/M01_异文对齐_机械/交付/异文标注.json")
M01_IDX = os.path.join(R, "回传包_M01_异文对齐/M01_异文对齐_机械/交付/04_差异索引.md")


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def is_pua(c):
    o = ord(c)
    return (0xE000 <= o <= 0xF8FF) or (0xF0000 <= o <= 0xFFFFD) or (0x100000 <= o <= 0x10FFFD)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(B, "38_总装产出_金匮_v0.2.0"))
    a = ap.parse_args()
    out = a.out
    vp = os.path.join(out, "viewer_data.json")
    vd = jload(vp)

    h01, h02, m01 = jload(H01), jload(H02), jload(M01)
    pua = {chr(int(r["id"].split("-")[1], 16)): r["text"] for r in h02["rows"]}

    def fix(s):
        return "".join(pua.get(c, c) for c in (s or ""))

    # 备份只做一次，重复运行不覆盖成「已注入版」
    bak = os.path.join(out, "viewer_data.assemble.json")
    if not os.path.exists(bak):
        shutil.copy2(vp, bak)

    by = {it["n"]: it for it in vd["items"]}
    pua_before = sum(is_pua(c) for it in vd["items"]
                     for x in it["v"].values()
                     for c in (x.get("t") or "") + (x.get("d") or ""))

    # ── 1. H02 替换 ────────────────────────────────────────────────
    for it in vd["items"]:
        for x in it["v"].values():
            if x.get("t"):
                x["t"] = fix(x["t"])
            if x.get("d"):
                x["d"] = fix(x["d"])

    # ── 2. H01 回填 ────────────────────────────────────────────────
    hit = miss = 0
    for r in h01["rows"]:
        m = re.match(r"T(\d+)-(.+?)(?:#p\d+)?$", r["id"])
        n, ver = int(m.group(1)), m.group(2)
        it = by.get(n)
        c = (it or {}).get("v", {}).get(ver)
        if not c:
            miss += 1
            continue
        hit += 1
        ch = r["choice"]
        note = (r.get("note") or "").strip()
        if ch == "有":
            c["cf"] = "中置信"
            c["hx"] = "H01 核定"
        elif ch == "残":
            c["cf"] = "残缺"
            c["hx"] = "H01 核定"
        elif ch == "无":
            c["ok"] = 0
            c["rs"] = "人工核定：本版无此条"
            c["ev"] = note
            c["hx"] = "H01 核定"
            for k in ("t", "d", "cf", "pg"):
                c.pop(k, None)
        elif ch == "?":
            c["cf"] = "低置信"
            c["tk"] = True
            c["hx"] = "H01 存疑"
        if note and ch in ("有", "残", "?"):
            c["ev"] = note

    # review 收敛：H01 只留 1 条存疑
    new_rev = []
    for r in h01["rows"]:
        if r["choice"] != "?":
            continue
        m = re.match(r"T(\d+)-(.+?)(?:#p\d+)?$", r["id"])
        n, ver = int(m.group(1)), m.group(2)
        c = by[n]["v"].get(ver, {})
        new_rev.append({"n": n, "v": ver, "st": "待核",
                        "pg": c.get("pg", ""), "t": (c.get("t") or "")[:70]})
    vd["review"] = new_rev

    # ── 3. M01 异文 ───────────────────────────────────────────────
    inj = bad = 0
    bad_rows = []
    for ver, rows in m01.items():
        for k, txt in rows.items():
            n = int(k)
            c = by.get(n, {}).get("v", {}).get(ver)
            if not c or int(c.get("ok") or 0) != 1:
                continue
            t = re.sub(r"\s+", "", fix(c.get("t") or ""))
            plain = re.sub(r"\s+", "", fix(re.sub(r"[【】]", "", txt)))
            if plain != t:
                bad += 1
                if len(bad_rows) < 8:
                    bad_rows.append(f"{ver} 条{n}")
                continue
            c["d"] = fix(txt)
            inj += 1

    # ── 4. stats 重算 ─────────────────────────────────────────────
    for nm in vd["vers"]:
        cells = [it["v"][nm] for it in vd["items"] if nm in it["v"]]
        vd["stats"][nm] = {
            "hit": sum(1 for c in cells if int(c.get("ok") or 0) == 1),
            "hi": sum(1 for c in cells if int(c.get("ok") or 0) == 1
                      and c.get("cf") in ("高置信", "校记锚点")),
            "anc": sum(1 for c in cells if c.get("cf") == "校记锚点"),
            "ind": vd["stats"].get(nm, {}).get("ind", 0),
        }

    pua_after = sum(is_pua(c) for it in vd["items"]
                    for x in it["v"].values()
                    for c in (x.get("t") or "") + (x.get("d") or ""))
    diff_uniq = len({it["n"] for it in vd["items"]
                     if any("【" in (c.get("d") or "") for c in it["v"].values())})

    note = ("v0.2.0 已应用三份回传：H02 15 码位释字、H01 115 格定性、"
            "M01 989 格异文（按条去重 394）。版本包基线未动，本层为派生产物。")
    # 构建说明写 build_notes；notes 专用于「条号 → {版本: 注文}」，
    # 混写会污染 L1 原文数据（曾出现 4 个非法键）
    if not isinstance(vd.get("build_notes"), dict):
        vd["build_notes"] = {}
    vd["build_notes"]["v0.2.0_回传"] = note

    json.dump(vd, open(vp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ── 5. 其余文本产物同步释字 ───────────────────────────────────
    changed = []
    for fn in ("01_条文总表.json", "02_条文对照本.md", "07_各版条文清单.md"):
        p = os.path.join(out, fn)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        t = "".join(pua.get(c, c) for c in s)
        if t != s:
            open(p, "w", encoding="utf-8").write(t)
            changed.append(fn)

    if os.path.exists(M01_IDX):
        shutil.copy2(M01_IDX, os.path.join(out, "04_差异索引.md"))

    # ── 6. 应用记录 ───────────────────────────────────────────────
    md = [
        "# 12 · 三份回传结果应用记录（v0.2.0）",
        "",
        "> 只作用于本总装产出；`版本包_金匮基线_v2/` 与 `版本正文_金匮/` 原件未改。",
        "> 输入：`37_回传验收_r1/`（H01 r2、H02、M01）。",
        "",
        "## 一、H02 · 15 码位释字",
        "",
        f"- viewer_data 中医统 t/d 私用区字符：**{pua_before} → {pua_after}**",
        f"- 同步释字文件：{'、'.join(changed) if changed else '无'}",
        "",
        "## 二、H01 · 115 格定性回填",
        "",
        f"- 命中 {hit} 格；未命中 {miss} 格（应为 0）",
        "- 有 61 → `cf=中置信`；残 51 → `cf=残缺`；无 2 → `ok=0` 并写原因；存疑 1 → 保留低置信",
        f"- `review` 由 115 条收敛为 **{len(new_rev)} 条**（仅 T0233 邓珍）",
        "",
        "## 三、M01 · 989 格异文注入",
        "",
        f"- 写入 `d` 字段 {inj} 格；与 t 不一致跳过 {bad} 格"
        + (f"（{', '.join(bad_rows)}）" if bad_rows else ""),
        f"- 页面「有异文」条数（按条去重）：**{diff_uniq}**",
        "- 医统 d 先按 H02 映射回填，再写入；括号位置不变",
        "",
        "## 四、页面",
        "",
        "- `20_双区对照_v0.14.0.html` 由 SH `34_总装产出_v0.12.0/viewer_data.json` + 本目录 `viewer_data.json` 合成",
        "- `index.html` 已替换为 v0.14.0（旧版备份 `index_v0.13.0.html`）",
        "",
    ]
    open(os.path.join(out, "12_回传结果应用.md"), "w", encoding="utf-8").write("\n".join(md))

    print(f"H02 释字: {pua_before} -> {pua_after}")
    print(f"H01: 命中 {hit} / 未命中 {miss}; review {len(new_rev)} 条")
    print(f"M01: 注入 {inj} 格 / 跳过 {bad}; 有异文 {diff_uniq} 条")
    print("stats:", json.dumps(vd["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
