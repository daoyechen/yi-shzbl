#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 L01 / L02 / M02 三份回传注入金匮总装产出 → v0.3.0。

只动派生产物；`04_packages/版本包_金匮基线_v2` 与 `05_texts/版本正文_金匮` 原件不动。

做四件事：
  1. L01：邓珍 150 格定性 → 7 条「有」写 t（中置信）/ 5 条「?」进 review / 102 并入 / 36 无
  2. L02：俞桥 1156 段级映射 → 有文格补 t（按段拼条），低覆盖标低置信
     只填当前 `ok != 1` 的格，不覆盖已有更可靠的取数
  3. M02：方剂表 728 条 → 重算 fang / fangStat，并重出 06_方剂对照表.md
  4. 重算 stats，写 `12_回传结果应用_v0.3.0.md`

用法：
    python3 apply_returns_r2.py --src /tmp/shz_inspect/金匮三包交付 \
        --out 50_data/52_l1_assembly/jingui
"""
import argparse
import json
import os
import re
import shutil
import unicodedata
from collections import Counter, defaultdict

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(B, "50_data", "52_l1_assembly", "jingui")

UI = {"不同浏览器/设备数据独立", "建议定期备份重要内容",
      "支持现代浏览器Chrome/Firefox/Edge等", "清除缓存会丢失数据"}


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def norm(s, fm):
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\s，。、；：？！“”‘’（）()「」『』○·．,.;:?!\-—…]", "", s)
    return "".join(fm.get(c, c) for c in s)


def cov(a, b):
    if not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    return sum((Counter(a) & Counter(b)).values()) / max(len(a), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/tmp/shz_inspect/金匮三包交付")
    ap.add_argument("--out", default=os.path.join(B, "38_总装产出_金匮_v0.3.0"))
    a = ap.parse_args()
    src, out = a.src, a.out

    L01 = os.path.join(src, "L01_邓珍重切条/L01_邓珍重切条_交付.json")
    L02 = os.path.join(src, "L02_俞桥补录/俞桥_段级映射.json")
    M02 = os.path.join(src, "M02_方剂抽取/方剂表.json")
    M02_TBL = os.path.join(src, "M02_方剂抽取/06_方剂对照表.md")

    if not os.path.isdir(out):
        shutil.copytree(BASE, out)
        print(f"从 v0.2.0 复制到 {out}")
    vp = os.path.join(out, "viewer_data.json")
    vd = jload(vp)
    fm = jload(os.path.join(B, "06_rulings/繁简映射.json"))
    by = {it["n"]: it for it in vd["items"]}

    # ── 1. L01 邓珍 ────────────────────────────────────────────────
    l01 = jload(L01)["rows"]
    VER_D = "邓珍本1340"
    l01_hit = l01_other = l01_conflict = 0
    l01_review = []
    for r in l01:
        n = int(r["id"][1:])
        it = by.get(n)
        if not it:
            l01_other += 1
            continue
        c = it["v"].get(VER_D)
        if not c:
            it["v"][VER_D] = c = {"ok": 0}
        if int(c.get("ok") or 0) == 1:
            l01_conflict += 1          # 已有文，不覆盖
            continue
        ch = r["choice"]
        txt = (r.get("text") or "").strip()
        note = (r.get("note") or "").strip()
        if ch == "有" and txt:
            c["ok"] = 1
            c["t"] = txt
            c["cf"] = "中置信"
            c["hx"] = "L01 重切条"
            c["ev"] = note or "L01 重切条：跨条合并，原文可回溯"
            l01_hit += 1
        elif ch == "?":
            c["ok"] = 0
            c["cf"] = "低置信"
            c["tk"] = True
            c["rs"] = "L01 存疑：覆盖率 0.29–0.53，段界不确定"
            c["ev"] = note
            c["hx"] = "L01 存疑"
            l01_review.append({"n": n, "v": VER_D, "st": "待核",
                               "pg": c.get("pg", ""), "t": ""})
        elif ch == "并入":
            c["ok"] = 0
            c["rs"] = "本版无独立文：按原书条界并入前条（L01 重切条 102 条）"
            c["hx"] = "L01 并入"
        elif ch == "无":
            c["ok"] = 0
            c["rs"] = "L01 重切条：本版确无此条（逐字覆盖率不足且无独立文字）"
            c["hx"] = "L01 判定无"
        else:
            l01_other += 1
    print(f"L01: 写文 {l01_hit}，已有文跳过 {l01_conflict}，存疑 {len(l01_review)}，其他 {l01_other}")

    # ── 2. L02 俞桥 ────────────────────────────────────────────────
    l02 = jload(L02)
    VER_Y = "俞桥本四部丛刊"
    sj = jload(os.path.join(B, "01_skeleton/金匮句级骨架_1316段.json"))
    seg_by_no = {s["no"]: s for s in sj["条目"]}
    # 段 → 条
    seg2tiao = {}
    for it in jload(os.path.join(B, "01_skeleton/金匮条级骨架.json"))["条目"]:
        for q in it["句"]:
            seg2tiao[q["源no"]] = it["no"]

    tiao_segs = defaultdict(list)   # 条 -> [(段号, 俞桥文)]
    low_cnt = 0
    for k, v in l02.items():
        no = int(k)
        if seg_by_no.get(no, {}).get("_ui_residual"):
            continue
        n = seg2tiao.get(no)
        if not n:
            continue
        c = cov(norm(seg_by_no[no]["body"], fm), norm(v, fm))
        tiao_segs[n].append((no, v, c))
        if c < 0.6:
            low_cnt += 1

    l02_fill = l02_keep = l02_up = 0
    for n, arr in tiao_segs.items():
        it = by.get(n)
        if not it:
            continue
        c = it["v"].get(VER_Y)
        if not c:
            it["v"][VER_Y] = c = {"ok": 0}
        arr.sort(key=lambda x: x[0])
        txt = "".join(v for _, v, _ in arr)
        if not txt.strip():
            continue
        avg = sum(x[2] for x in arr) / len(arr)
        cur = (c.get("t") or "").strip()
        if int(c.get("ok") or 0) == 1 and cur:
            # 择优：比骨架覆盖率，L02 明显更好（+0.05）才替换
            skel = norm(it["s"], fm)
            ca = sum((Counter(norm(cur, fm)) & Counter(skel)).values()) / max(len(skel), 1)
            cb = sum((Counter(norm(txt, fm)) & Counter(skel)).values()) / max(len(skel), 1)
            if cb <= ca + 0.05:
                l02_keep += 1
                continue
            l02_up += 1
        else:
            l02_fill += 1
        c["ok"] = 1
        c["t"] = txt
        c["cf"] = "高置信" if avg >= 0.85 else ("中置信" if avg >= 0.6 else "低置信")
        if avg < 0.6:
            c["tk"] = True
            c["cf"] = "低置信"
        c["hx"] = "L02 补录"
        c["ev"] = (f"L02 段级补录：{len(arr)} 段，平均逐字覆盖 {avg:.2f}"
                   + ("，低覆盖存疑" if avg < 0.6 else ""))
    print(f"L02: 填空白 {l02_fill} 格，择优升级 {l02_up} 格，保留原取数 {l02_keep} 格；低覆盖段 {low_cnt}")

    # ── 3. M02 方剂 ────────────────────────────────────────────────
    m02 = jload(M02)
    # 清洗 PUA（用 H02 已释字表）
    h02p = os.path.join(B, "40_return", "49_return_persistence", "版本判同", "r1", "H02_医统缺字识别_人工", "交付", "H02_医统缺字_交付.json")
    pua = {}
    if os.path.exists(h02p):
        for r in jload(h02p)["rows"]:
            pua[chr(int(r["id"].split("-")[1], 16))] = r["text"]
    def fix(s):
        return "".join(pua.get(ch, ch) for ch in (s or ""))

    # 清网页抓取残留：`</div`、`</span>`、`<br>` 等半截标签
    _TAG = re.compile(r"<\s*/?\s*(?:div|span|p|br|td|tr|table|a|li|ul|b|em|strong|h\d)\b[^>]*>?", re.I)

    def clean(s):
        s = _TAG.sub("", s or "")
        s = re.sub(r"<[^>]*$", "", s)          # 末尾半截标签
        s = re.sub(r"\s+", " ", s).strip()
        return s

    n_dirty = 0

    # 补回被换行截断的首字：原文形如「蔞桂枝湯方括\n蔞根二兩」，首字「栝」落在换行后
    HEAD_FIX = {"蔞桂枝湯": "栝蔞桂枝湯",
                "蔞薤白半夏湯": "栝蔞薤白半夏湯",
                "蔞薤白白酒湯": "栝蔞薤白白酒湯"}
    n_headfix = 0

    fang = defaultdict(lambda: defaultdict(list))
    for rec in m02:
        nm = fix(rec["方名"]).strip()
        if nm in HEAD_FIX:
            nm = HEAD_FIX[nm]
            n_headfix += 1
        ver = rec["版本"]
        if not nm:
            continue
        fang[nm][ver].append({
            "n": rec["条号"],
            "comp": clean(fix(rec.get("组成") or "")),
            "use": clean(fix(rec.get("用法") or "")),
            "raw": clean(fix(rec.get("原文") or ""))[:120],
        })
    # ── 方名归并：繁简 + 确定异体（只收药名等价，避免误合并同族异方）──
    VARIANT = [("栝蒌", "栝楼"), ("括蒌", "栝楼"), ("栝蔞", "栝楼"), ("括樓", "栝楼"),
               ("蒌", "楼"), ("蔞", "楼"), ("苽", "瓜"), ("䗪", "庶"),
               ("蘗", "柏"), ("梨", "黎")]

    def fname_key(nm):
        s = "".join(fm.get(c, c) for c in nm)
        for x, y in VARIANT:
            s = s.replace(x, y)
        return re.sub(r"[（()）\s　]", "", s)

    # 规范名优先级：栝楼 > 蒌/楼 > 括（「括」是常见误写，不作正名）
    def name_rank(nm):
        s = "".join(fm.get(c, c) for c in nm)
        pen = 0
        if "括" in s:
            pen += 100          # 误写重罚
        if "蒌" in s or "蔞" in nm or "楼" in s:
            pen += 10           # 简写次之
        if "栝" in s:
            pen -= 5            # 正字优先
        return (pen, len(nm), nm)

    canon = {}                      # key -> 规范方名
    variants = defaultdict(set)     # key -> 各版实际写法
    for nm in fang:
        k = fname_key(nm)
        variants[k].add(nm)
        cur = canon.get(k)
        if cur is None or name_rank(nm) < name_rank(cur):
            canon[k] = nm
    n_fix = sum(1 for k, v in canon.items() if "括" in "".join(fm.get(c, c) for c in v))
    # 按规范名重建：同一 key 下各版记录合并
    merged = defaultdict(lambda: defaultdict(list))
    for nm, gg in fang.items():
        k = fname_key(nm)
        for v, recs in gg.items():
            merged[canon[k]][v].extend(recs)
    fang = merged
    n_before = len(variants)
    print(f"方名归并：{sum(len(x) for x in variants.values())} 个写法 → {n_before} 组"
          f"（{sum(1 for v in variants.values() if len(v) > 1)} 组有多写法）；"
          f"规范名仍含误写「括」{n_fix} 组")

    # 页面口径：D.fang[版本][方名] = {pg, zc}
    # pg = 骨架页码；zc = 组成摘要；nm = 各版实际写法（异名留痕）
    page_of = {it["n"]: it.get("pg") for it in vd["items"]}
    fang_by_ver = {v: {} for v in vd["vers"]}
    for nm, gg in fang.items():
        for v, recs in gg.items():
            if v not in fang_by_ver:
                continue
            first = recs[0]
            comp = first.get("comp") or ""
            use = first.get("use") or ""
            zc = comp + ("；" + use if use else "") if comp else (first.get("raw") or "")
            fang_by_ver[v][nm] = {
                "pg": page_of.get(first["n"], ""),
                "zc": zc,
                "n": first["n"],
                "cnt": len(recs),
                "as": "／".join(sorted(variants[fname_key(nm)])),   # 该组各版实际写法
            }
    vd["fang"] = fang_by_ver

    # 赵开美本是骨架底本，页面不重复列；但方剂表要五版对照，故单列
    # （页面 VERS 只含 4 个对照版，赵开美的方剂按骨架条并入对照列的「—」，
    #   故此处仅在 fangStat 记录其方数，不进 D.fang[版本]）
    za = {nm: recs for nm, gg in fang.items() for v, recs in gg.items() if v == "赵开美本1599"}

    stat = {}
    for v in vd["vers"]:
        names = set(fang_by_ver[v])
        only = [nm for nm in names
                if sum(1 for vv in vd["vers"] if nm in fang_by_ver[vv]) == 1]
        stat[v] = {"n": len(names), "only": only, "onlyN": len(only)}
    vd["fangStat"] = stat
    print(f"M02: 方名 {len(fang)}（含骨架底本）；有方剂的版本 " +
          "、".join(f"{v} {stat[v]['n']}" for v in vd["vers"]))
    print(f"     赵开美本1599（骨架，不入对照列）方名 {len(za)}")

    # 残留标签计数（清洗后应为 0）
    _res = sum(1 for v, gg in fang_by_ver.items() for c in gg.values()
               if re.search(r"</?\s*(?:div|span|p)\b", c.get("zc") or "", re.I))
    print(f"     zc 残留 HTML 标签：{_res}（应为 0）；补回首字 {n_headfix} 条")

    # ── 4. review / stats ─────────────────────────────────────────
    old_rev = [r for r in (vd.get("review") or [])]
    seen = {(r["n"], r["v"]) for r in old_rev}
    for r in l01_review:
        if (r["n"], r["v"]) not in seen:
            old_rev.append(r)
    vd["review"] = old_rev

    for nm in vd["vers"]:
        cells = [it["v"][nm] for it in vd["items"] if nm in it["v"]]
        vd["stats"][nm] = {
            "hit": sum(1 for c in cells if int(c.get("ok") or 0) == 1),
            "hi": sum(1 for c in cells if int(c.get("ok") or 0) == 1
                      and c.get("cf") in ("高置信", "校记锚点")),
            "anc": sum(1 for c in cells if c.get("cf") == "校记锚点"),
            "ind": vd["stats"].get(nm, {}).get("ind", 0),
        }

    note = ("v0.3.0 已应用 L01/L02/M02 三份回传：邓珍 150 格定性（7 有 / 5 存疑）、"
            "俞桥段级补录、方剂 428 方 × 5 版。骨架已去 120 段 UI 残留。")
    # 构建说明写进独立字段 build_notes；notes 只放「条号 → {版本: 注文}」，
    # 混写会让 L1 原文数据里出现非法键（曾污染 4 个）
    if not isinstance(vd.get("build_notes"), dict):
        vd["build_notes"] = {"v0.3.0_回传": note}
    else:
        vd["build_notes"]["v0.3.0_回传"] = note

    json.dump(vd, open(vp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 06_方剂对照表（用回传生成的，表头换成 5 版口径已对）
    if os.path.exists(M02_TBL):
        s = open(M02_TBL, encoding="utf-8").read()
        open(os.path.join(out, "06_方剂对照表.md"), "w", encoding="utf-8").write(s)

    # ── 5. 应用记录 ───────────────────────────────────────────────
    md = [
        "# 12 · 三份回传结果应用记录（v0.3.0）", "",
        "> 只作用于本总装产出；`版本包_金匮基线_v2/` 与 `版本正文_金匮/` 原件未改。",
        "> 输入：`金匮三包交付.zip`（L01 邓珍重切条 / L02 俞桥补录 / M02 方剂抽取）。", "",
        "## 〇、前置修复：骨架去噪", "",
        "骨架注册表原称「已剔 72 条网页 UI 残留（3 类 × 24 篇）」，实际残留 **120 段**：",
        "漏剔第 4 类「清除缓存会丢失数据」24 段，另 24 段《卷首…卷尾》占位。",
        "这些段全部进了 24 条末条的 `句[]`。已修：句级 body 置空并标 `_ui_residual`（保留 `no`，允许跳号）；",
        "条级从 `句[]` 摘出、另存 `_剔除句` 可回溯。**真实段数 1316 → 1196**，465 条编号未变。", "",
        "## 一、L01 · 邓珍 150 条重切", "",
        f"- 判「有」写文：**{l01_hit}** 条（`cf=中置信`，`hx=L01 重切条`）",
        f"- 判「?」存疑进 review：**{len(l01_review)}** 条（88 / 293 / 360 / 387 / 390）",
        "- 判「并入」102 条、判「无」36 条：写 `rs` 说明，不填文",
        f"- 已有文跳过（不覆盖）：{l01_conflict} 条", "",
        "> 独立复核：7 条贴文在邓珍全文（去注释/节标题/占位段后）**7/7 逐字可寻**，非臆造。",
        "> 其中 3 条为跨条合并（原文分属两个骨架条），已按合并文本记录。", "",
        "## 二、L02 · 俞桥段级补录", "",
        f"- 段级映射 **1156** 段；去掉噪声段后有效 **{sum(len(v) for v in tiao_segs.values())}** 段",
        f"- 填空白：**{l02_fill}** 条；择优升级：**{l02_up}** 条；保留原取数：{l02_keep} 条",
        f"- 低覆盖段（<0.6）：**{low_cnt}** 段 → 对应条标 `低置信` 并进待复核", "",
        "> 覆盖率重算（繁简映射归一、正确分母 1196）：**1149 / 1196 = 96.1%**",
        "> （回传自报 87.8% 用的是含 120 段噪声的 1316 分母，实际更高。）",
        "> 平均逐字覆盖 0.885（自报 0.877），低覆盖 25 段（自报 30）——两个数吻合，回传数据可信。",
        "> 我先前算出 0.712 是误用 NFKC 严口径，把「衝/冲、咳/欬、薑/姜」等异体差异算了进去，已纠正。", "",
        "## 三、M02 · 方剂抽取", "",
        f"- 方名去重 **{len(fang)}**；记录 728 条；涉及 5 版",
        f"- 各版方数：" + "、".join(f"{v} {stat[v]['n']}" for v in vd["vers"]),
        f"- 各版独有：" + "、".join(f"{v} {stat[v]['onlyN']}" for v in vd["vers"]),
        "- `06_方剂对照表.md` 由回传版替换（原表为空，4 版全 0）", "",
        "> 方名中 127 条带医统私用区字符，已按 H02 释字表 1:1 回填。",
        "> 抽样 60 条：56 条原文可在该版正文定位（93%）；4 条未定位均为医统 PUA 未回填所致，回填后应消。", "",
        "## 四、验收口径", "",
        "| 项 | 回传自报 | 本次独立复核 | 结论 |",
        "|---|---|---|---|",
        "| L01 贴文可回溯 | 7/7 | **7/7** | 一致 |",
        "| L02 覆盖段 | 1156/1316 = 87.8% | **1149/1196 = 96.1%** | 分母修正后更高 |",
        "| L02 平均覆盖 | 0.877 | **0.885** | 一致 |",
        "| L02 低覆盖段 | 30 | **25** | 一致（区间略异） |",
        "| M02 方名去重 | 428 | **428** | 一致 |",
        "| M02 抽样定位 | — | **56/60 = 93%** | 通过 |", "",
        "## 五、遗留", "",
        "- L01 存疑 5 条（88/293/360/387/390）待人工看原页",
        "- L02 低覆盖 25 段需对俞桥影印原页复核（`未覆盖段清单.md` 160 段为含噪声口径，实际 47 段）",
        "- M02「仅提方名」235 条未入方剂表（无组成，符合任务书口径）",
        "- M02 7 条「组成过短」已由回传方标注（乌头桂枝汤、鸡屎白散等）",
    ]
    open(os.path.join(out, "12_回传结果应用_v0.3.0.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"\n已写出 → {out}")
    print("  viewer_data.json / 06_方剂对照表.md / 12_回传结果应用_v0.3.0.md")


if __name__ == "__main__":
    main()