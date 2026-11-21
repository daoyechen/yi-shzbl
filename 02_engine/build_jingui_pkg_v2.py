#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""金匮 5 版 → 版本包（v2，改用原 agent 的裁定源，不再依赖被压平的 md 槽位）

为什么有 v2
-----------
v1（build_jingui_pkg.py）直接读 `各版原文/*.md` 的 `<!-- pN -->` 槽位。实测该 md
是把「骨架 1556 节」逐节渲染出来的产物，多个原书条被压进第一节、其余节写
「（本版此条未检出）」。结果：

    俞桥 176/465 有文（md 正文仅 9,831 字，全书约 4 万）
    医统 326/465
    邓珍 269/465

而同一批交付里的裁定源其实是干净的段级数据：

| 源 | 覆盖 | 粒度 |
|---|---|---|
| `逐条核定表_2_5_A3.md`（俞桥）| 1154 段 / 1316 | 段级，含 覆盖/占比/F1/差异类型/置信 |
| `逐条核定表_2_5_A4.md`（医统）| 1170 段 / 1316 | 同上 |
| `A10_条级参照系.json`（人卫）  | 465 条 / 465  | 条级，含 起止段/字数/置信/待核校/条文 |
| `人工裁定_2_5.json`            | 1179 条裁定 | 段级，判定「有/无」+ 本版原文 |
| `各版原文/01_赵开美本1599.md`   | 1556 段 / 1556 | 段级（骨架本身）|

本脚本按上述分工取值，逐条落成 `版本包.json`。**不补、不改、不猜**：
取不到就写「无」，并在 `原因`/`证据` 里写清是「裁定无此条」还是「无对应段」。

用法
----
    python3 build_jingui_pkg_v2.py --out ../版本包_金匮基线_v2
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shjkit import skeleton as SK  # noqa: E402

ROOT = os.path.dirname(HERE)                     # 00_公共地基
SRC = os.path.join(ROOT, "金匮裁定源")
MD_DIR = os.path.join(ROOT, "版本正文_金匮")
UND = "（本版此条未检出）"

# 裁定源里的版本代号 → 版本包名
CODES = {
    "A2": "邓珍本1340",
    "A3": "俞桥本四部丛刊",
    "A4": "医统正脉1601",
    "A10": "人卫排印本1964",
}
ORDER = ["赵开美本1599", "邓珍本1340", "医统正脉1601", "俞桥本四部丛刊", "人卫排印本1964"]


_MAP = None
def _norm(s):
    """只留汉字,并把常见繁体折成简体(用交付自带 繁简映射);用于核「是否含此段文字」。"""
    global _MAP
    if _MAP is None:
        p = os.path.join(SRC, "繁简映射.json")
        _MAP = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        _MAP.pop("人", None)     # 该表 人→患 是错的(应为 患→人)
    out = []
    for ch in s:
        ch = _MAP.get(ch, ch)
        if "\u3400" <= ch <= "\u9fff":
            out.append(ch)
    return "".join(out)


def cover(a, b):
    """a 有多少比例的字能在 b 中按序对上（对 b 的长度不敏感）。"""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    m = sum(x.size for x in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return m / len(a)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse_md(path):
    """md 的 <!-- pN --> 槽位 → {段号: 正文}"""
    raw = open(path, encoding="utf-8").read()
    segs = {}
    for m in re.finditer(
            r"<!--\s*p(\d+)\s*-->\s*\n##\s*条\s*(\d+)\s*·\s*([^\n]*)\n([\s\S]*?)(?=<!--\s*p\d+\s*-->|\Z)", raw):
        no = int(m.group(2))
        body = m.group(4).strip()
        if body and body != UND:
            segs[no] = body
    return segs


def parse_table(path):
    """逐条核定表（段级）→ {段号: 记录}"""
    rows = {}
    for ln in open(path, encoding="utf-8"):
        if not ln.startswith("| ") or not re.match(r"^\| \d+ ", ln):
            continue
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) < 10:
            continue
        no = int(c[0])
        rows[no] = {
            "骨架": c[2], "本版": c[3].replace("\\|", "|"),
            "覆盖": c[4], "占比": c[5], "F1": c[6],
            "差异": c[7], "置信": c[8], "状态": c[9],
        }
    return rows


def load_review():
    """人工裁定 → {(版本代号, 段号): 记录}"""
    d = json.load(open(os.path.join(SRC, "人工裁定_2_5.json"), encoding="utf-8"))
    out = {}
    for r in d["裁定"]:
        code = (r.get("版本") or "").split("_")[0]
        out[(code, int(r["条号"]))] = r
    return out


def align_deng(sk_items, md):
    """邓珍 md 的槽号并不可靠（实测条 13 的文字落在槽 19）。

    做法：对每条按「骨架原文 vs 各槽文字」的逐字覆盖率找最佳槽，再按条序做单调约束
    （后条的槽号不得小于前条），避免同一槽被反复认领到相距很远的条上。
    返回 {条号: (槽号, 覆盖率)}；覆盖 < 0.55 视为该版无此条。
    """
    slots = sorted(md)
    used_upto = 0
    owner_of = {}          # 槽号 → 首个认领它的骨架条号
    out = {}
    for it in sk_items:
        t = it["原文"]
        best = (0.0, None)
        # 只在「游标之后 40 个实文槽」里找：按槽序个数而不是槽号跨度开窗
        # （邓珍的实文槽在 1556 个骨架槽里是稀的，按槽号开窗会半路断掉），
        # 同时避免同名方剂/套语被认到很远的槽（实测条 83 认到槽 297，中间整片落空）。
        fwd = 0
        for sn in slots:
            if sn < used_upto:
                continue
            fwd += 1
            if fwd > 40:
                break
            cv = cover(t, md[sn])
            if cv > best[0]:
                best = (cv, sn)
        if best[1] is not None and best[0] >= 0.55:
            sn = best[1]
            out[it["no"]] = (sn, best[0], owner_of.get(sn))
            owner_of.setdefault(sn, it["no"])
            used_upto = sn
    return out


def conf_rank(c):
    return {"高": 2, "中": 1, "低": 0}.get((c or "").replace("置信", ""), 1)


def conf_name(rank):
    return {2: "高置信", 1: "中置信", 0: "低置信"}[rank]


def build_version(vname, sk_items, ctx):
    """→ 版本包 dict"""
    entries = []
    for it in sk_items:
        no, pian = it["no"], it["篇"]
        segnos = [j["源no"] for j in (it.get("句") or [])]
        segs, notes = [], []
        for sn in segnos:
            got = ctx["seg_of"](vname, sn, no)
            if got:
                segs.append(got)
                notes.append(f"no{sn}:{got['置信']}/{got['异文_tag']}")
        base = {"条号": no, "篇": pian, "页": it.get("段首", it.get("页")), "宋本": it["原文"]}

        if segs:
            rank = min(conf_rank(s["置信"]) for s in segs)
            entries.append(dict(base, **{
                "状态": "有",
                "置信": conf_name(rank),
                "分段": segs,
                "原文": "\n".join(s["原文"] for s in segs),
                "异文": "",
                "证据": ctx["evid_of"](vname, segnos, segs, notes),
                "待核校": any(s.get("待核校") for s in segs),
            }))
        else:
            rsn, ev = ctx["reason_of"](vname, no, segnos)
            entries.append(dict(base, **{
                "状态": "无", "原因": rsn, "证据": ev, "待核校": False,
            }))

    # 篇目
    order, seen = [], {}
    for it in sk_items:
        p = it["篇"]
        if p not in seen:
            seen[p] = {"名": p, "raw": p, "页": it.get("段首", it.get("页")), "字数": 0}
            order.append(seen[p])
    for e in entries:
        if e["状态"] == "有":
            for x in order:
                if x["名"] == e["篇"]:
                    x["字数"] += len(e["原文"])

    n_ok = sum(1 for e in entries if e["状态"] == "有" and not e["待核校"])
    n_rev = sum(1 for e in entries if e.get("待核校"))
    n_none = sum(1 for e in entries if e["状态"] == "无")
    from collections import Counter
    reasons = Counter(e.get("原因") for e in entries if e["状态"] == "无")
    return {
        "版本名": vname,
        "骨架": SK.skel_spec("jingui").get("名称", "金匮条级骨架"),
        "条目": entries,
        "独有": [], "锚点": [], "方剂": [],
        "篇目": order,
        "原因分布": dict(reasons),
        "统计": {
            "对上条数": sum(1 for e in entries if e["状态"] == "有"),
            "高置信": sum(1 for e in entries if e.get("置信") == "高置信"),
            "独立内容": 0, "方剂数": 0,
            "待复核": n_rev, "条数": len(entries),
        },
        "_生成": ctx["meta_of"](vname, n_ok, n_none, n_rev),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "版本包_金匮基线_v2"))
    args = ap.parse_args()

    sk_items = SK.load_skeleton("jingui")
    zhao_md = parse_md(os.path.join(MD_DIR, "01_赵开美本1599.md"))
    deng_md = parse_md(os.path.join(MD_DIR, "02_邓珍本1340.md"))
    a3 = parse_table(os.path.join(SRC, "逐条核定表_2_5_A3.md"))
    a4 = parse_table(os.path.join(SRC, "逐条核定表_2_5_A4.md"))
    a10 = {int(x["条号"]): x for x in
           json.load(open(os.path.join(SRC, "A10_条级参照系.json"), encoding="utf-8"))["每条"]}
    review = load_review()
    # 骨架段首 → 条号（用于判定「并入前条」时指认归属槽位）
    SK_BY_NO = {it["no"]: it for it in sk_items}
    DENG_OWNER = {}
    for it in sk_items:
        sn = it.get("段首", it.get("页"))
        if isinstance(sn, int):
            DENG_OWNER[sn] = it["no"]

    # 每版「段 → 分段」取值器
    def from_table(tbl, code):
        def f(vname, sn):
            r = tbl.get(sn)
            if r and r["本版"].strip():
                return {"页": sn, "原文": r["本版"], "异文": "",
                        "置信": r["置信"] + "置信", "异文_tag": f"{r['状态']}/F1 {r['F1']}",
                        "待核校": r["状态"] == "残缺" or r["置信"] == "低"}
            rv = review.get((code, sn))
            if rv and rv.get("判定") == "有" and (rv.get("本版原文") or "").strip():
                return {"页": sn, "原文": rv["本版原文"], "异文": "",
                        "置信": (rv.get("置信") or "低置信"), "异文_tag": "人工裁定",
                        "待核校": True}
            return None
        return f

    DENG_ALIGN = align_deng(sk_items, deng_md)

    def from_md(md, code, aligned=None):
        """取值优先级:文字匹配到的槽 > 人工裁定 > 段首槽直取(须过覆盖率门槛)。

        邓珍的 md 槽号会错位（条 13 的文字在槽 19），所以给了 aligned 时不再信槽号；
        但 aligned 会有认不到、或被前条认领的条，这里继续回落到裁定与段首槽，
        且段首槽也要过 0.6 的逐字覆盖率——宁可留「无」，不拿错段充数。
        """
        consumed = set()      # 走 aligned 时整条只取一次，否则多段条会把同一段抄两遍

        def f(vname, sn, tiao_no=None):
            sk_body = SK_BY_NO[tiao_no]["原文"] if tiao_no in SK_BY_NO else ""
            if aligned is not None:
                al = aligned.get(tiao_no)
                if al and tiao_no in consumed:
                    return None
                if al:
                    consumed.add(tiao_no)
                    slot, cv, owner = al
                    if owner is None:
                        return {"页": slot, "原文": md[slot], "异文": "",
                                "置信": "高置信" if cv >= 0.85 else "中置信",
                                "异文_tag": f"md槽位{slot}(文字匹配 {cv:.2f})",
                                "待核校": cv < 0.75}
                    # owner 非空 = 与更早的条共用同一槽，本版此处未单列 → 不重复给文
                rv = review.get((code, tiao_no)) or review.get((code, sn))
                if rv and rv.get("判定") == "有" and (rv.get("本版原文") or "").strip():
                    return {"页": sn, "原文": rv["本版原文"], "异文": "", "置信": "低置信",
                            "异文_tag": "人工裁定", "待核校": True}
                if sn in md and cover(sk_body, md[sn]) >= 0.60:
                    cv = cover(sk_body, md[sn])
                    return {"页": sn, "原文": md[sn], "异文": "",
                            "置信": "高置信" if cv >= 0.85 else "中置信",
                            "异文_tag": f"段首槽{sn}(文字匹配 {cv:.2f})", "待核校": cv < 0.75}
                return None
            if sn in md:
                return {"页": sn, "原文": md[sn], "异文": "", "置信": "高置信",
                        "异文_tag": "md槽位", "待核校": False}
            rv = review.get((code, sn))
            if rv and rv.get("判定") == "有" and (rv.get("本版原文") or "").strip():
                return {"页": sn, "原文": rv["本版原文"], "异文": "", "置信": "低置信",
                        "异文_tag": "人工裁定", "待核校": True}
            return None
        return f

    def from_a10(vname, sn):
        # A10 是条级：只有「锚段」命中本条首段时整条给文
        return None

    # 取值器必须建一次就复用：from_md 内部用 consumed 记录「本条已取过」，
    # 每次调用都新建闭包会让去重失效（多段条把同一段抄两遍，实测条 2）。
    F_ZHAO = from_md(zhao_md, "A1")
    F_DENG = from_md(deng_md, "A2", DENG_ALIGN)

    def seg_of(vname, sn, tiao_no=None):
        if vname == "赵开美本1599":
            return F_ZHAO(vname, sn)
        if vname == "邓珍本1340":
            return F_DENG(vname, sn, tiao_no)
        if vname == "俞桥本四部丛刊":
            return from_table(a3, "A3")(vname, sn)
        if vname == "医统正脉1601":
            return from_table(a4, "A4")(vname, sn)
        if vname == "人卫排印本1964":
            return None      # 条级单独处理
        return None

    def evid_of(vname, segnos, segs, notes):
        if vname == "人卫排印本1964":
            return ""
        miss = [sn for sn in segnos if sn not in {s["页"] for s in segs}]
        tag = "；".join(notes)
        return f"辖段 {segnos}；取到 {[s['页'] for s in segs]}" + (f"；缺 {miss}" if miss else "") + f"｜{tag}"

    def reason_of(vname, no, segnos):
        rv = review.get(({"邓珍本1340": "A2", "俞桥本四部丛刊": "A3",
                          "医统正脉1601": "A4", "人卫排印本1964": "A10"}.get(vname, "?"), no))
        if vname == "人卫排印本1964":
            x = a10.get(no)
            if x and (x.get("条文") or "").strip():
                return "占位", ""
            return "A10 参照系无此条", "条级参照系 465 条内无对应"
        if rv and rv.get("判定") == "无":
            return "人工裁定：本版无此条", (rv.get("复核说明") or "")[:200]
        if vname == "邓珍本1340":
            # 邓珍 md 槽位按「骨架段首」落文；本条段首槽为空 → 其文字被渲染进更早的槽位，
            # 即本版此段未独立成条（邓珍全书 322 条，赵开美骨架 465 条，分条更粗）。
            first = segnos[0] if segnos else None
            owner = None
            for s0 in sorted(DENG_OWNER, reverse=True):
                if first is not None and s0 < first and s0 in deng_md:
                    owner = s0
                    break
            al = DENG_ALIGN.get(no)
            if al and al[2] is not None:
                return ("本版分条较粗：并入前条，未独立成条",
                        f"本条与骨架条 {al[2]} 共用邓珍 md 槽位 no{al[0]}（覆盖率 {al[1]:.2f}），"
                        f"即本版此处未独立分条")
            if owner:
                cv = cover(SK_BY_NO[no]["原文"], deng_md[owner])
                if cv >= 0.5:
                    return ("本版分条较粗：并入前条，未独立成条",
                            f"本条段首槽 no{first} 在邓珍 md 为空；前一条实文槽 no{owner}"
                            f"（骨架条 {DENG_OWNER[owner]}）逐字覆盖率 {cv:.2f}，本段文字确在其中")
                return ("本版无对应段（未核实是否并入前条）",
                        f"段首槽 no{first} 为空；前一条实文槽 no{owner} 与本文覆盖率仅 {cv:.2f}，"
                        f"不足以判为并入")
        return ("本版无对应段", f"辖段 {segnos} 在裁定表与 md 槽位中均无文字")

    def meta_of(vname, n_ok, n_none, n_rev):
        src = {
            "赵开美本1599": ["版本正文_金匮/01_赵开美本1599.md（骨架逐段渲染件，1556 段全有文）"],
            "邓珍本1340": ["版本正文_金匮/02_邓珍本1340.md（313 段有文）",
                       "金匮裁定源/人工裁定_2_5.json（题 A2_邓珍本1340，补低置信/未匹配段）"],
            "俞桥本四部丛刊": ["金匮裁定源/逐条核定表_2_5_A3.md（1154 段）",
                        "金匮裁定源/人工裁定_2_5.json（题 A3_俞桥本）"],
            "医统正脉1601": ["金匮裁定源/逐条核定表_2_5_A4.md（1170 段）",
                       "金匮裁定源/人工裁定_2_5.json（题 A4_医统正脉1601）"],
            "人卫排印本1964": ["金匮裁定源/A10_条级参照系.json（465 条，条级条文）"],
        }[vname]
        return {
            "源": src,
            "骨架条数": len(sk_items),
            "有文条数": n_ok, "无文条数": n_none, "待核校": n_rev,
            "异文": "未做（本包只落各版原文，未逐字标异文）",
            "方剂": "未抽",
            "独有": "未判定",
            "生成": "build_jingui_pkg_v2.py",
        }

    ctx = {"seg_of": seg_of, "evid_of": evid_of, "reason_of": reason_of, "meta_of": meta_of}

    os.makedirs(args.out, exist_ok=True)
    for vname in ORDER:
        if vname == "人卫排印本1964":
            # 人卫直接用条级参照系
            entries = []
            for it in sk_items:
                no = it["no"]
                x = a10.get(no)
                base = {"条号": no, "篇": it["篇"], "页": it.get("段首", it.get("页")), "宋本": it["原文"]}
                if x and (x.get("条文") or "").strip():
                    entries.append(dict(base, **{
                        "状态": "有", "置信": x.get("置信") or "中置信",
                        "分段": [{"页": x.get("起段", base["页"]), "原文": x["条文"],
                                  "异文": "", "置信": x.get("置信") or "中置信"}],
                        "原文": x["条文"], "异文": "",
                        "证据": f"A10 起段{x.get('起段')}–止段{x.get('止段')}（{x.get('段数')}段，{x.get('字数')}字）｜{x.get('依据','')}",
                        "待核校": bool(x.get("待核校")),
                    }))
                else:
                    entries.append(dict(base, **{"状态": "无", "原因": "A10 参照系无此条",
                                                 "证据": "条级参照系 465 条内无对应", "待核校": True}))
            order, seen = [], {}
            for it in sk_items:
                p = it["篇"]
                if p not in seen:
                    seen[p] = {"名": p, "raw": p, "页": it.get("段首", it.get("页")), "字数": 0}
                    order.append(seen[p])
            for e in entries:
                if e["状态"] == "有":
                    for x in order:
                        if x["名"] == e["篇"]:
                            x["字数"] += len(e["原文"])
            pack = {
                "版本名": vname, "骨架": SK.skel_spec("jingui").get("名称", "金匮条级骨架"),
                "条目": entries, "独有": [], "锚点": [], "方剂": [], "篇目": order,
                "原因分布": {}, "统计": {}, "_生成": {},
            }
            pack["统计"] = {
                "对上条数": sum(1 for e in entries if e["状态"] == "有"),
                "高置信": sum(1 for e in entries if e.get("置信") == "高置信"),
                "独立内容": 0, "方剂数": 0,
                "待复核": sum(1 for e in entries if e.get("待核校")), "条数": len(entries),
            }
            pack["_生成"] = meta_of(vname, pack["统计"]["对上条数"],
                                    sum(1 for e in entries if e["状态"] == "无"), pack["统计"]["待复核"])
        else:
            pack = build_version(vname, sk_items, ctx)

        d = os.path.join(args.out, "版本包_" + vname)
        os.makedirs(os.path.join(d, "交付"), exist_ok=True)
        os.makedirs(os.path.join(d, "版本正文"), exist_ok=True)
        os.makedirs(os.path.join(d, "_工作"), exist_ok=True)
        json.dump(pack, open(os.path.join(d, "交付", "版本包.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        spec = {
            "版本名": vname, "骨架": "jingui",
            "转录层": "段级（裁定表/参照系），非影印页",
            "异文": "未做", "方剂": "未抽",
            "生成": "build_jingui_pkg_v2.py",
            "源": pack["_生成"]["源"],
        }
        json.dump(spec, open(os.path.join(d, "spec.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        # 正文随包
        src_md = {"赵开美本1599": "01_赵开美本1599.md", "邓珍本1340": "02_邓珍本1340.md",
                  "医统正脉1601": "03_医统正脉1601.md", "俞桥本四部丛刊": "04_俞桥本四部丛刊.md",
                  "人卫排印本1964": "05_人卫排印本1964.md"}[vname]
        p = os.path.join(MD_DIR, src_md)
        if os.path.exists(p):
            import shutil
            shutil.copy2(p, os.path.join(d, "版本正文", src_md))

        s = pack["统计"]
        print(f"{vname:12s} 有 {s['对上条数']:3d}/465  高置信 {s['高置信']:3d}  "
              f"待核校 {s['待复核']:3d}  无 {465 - s['对上条数']:3d}")

    # 源清单
    man = {f: {"字节": os.path.getsize(os.path.join(SRC, f)),
               "sha256": sha(os.path.join(SRC, f))} for f in sorted(os.listdir(SRC)) if not f.startswith(".")}
    json.dump(man, open(os.path.join(args.out, "_源清单.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("→", args.out)


if __name__ == "__main__":
    main()
