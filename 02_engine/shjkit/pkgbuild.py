#!/usr/bin/env python3
"""版本包产出:一个版本包 → 交付/ 下的标准件 + _工作/ 下的中间产物。

交付件(与公共地基的产出口径一致):
  版本对照.md    逐条对照(宋本 ↔ 本版),带置信与异文
  本版独有.md    该版独立内容,带独立 ID
  锚点表.md      该版校记硬锚点
  待复核.md      低置信与暂未匹配条目
  体例说明.md    该版体例、收篇、正文起讫、「此版无」依据
  方剂表.md      该版方剂清单
  版本包.json    机器可读:单元 + 逐条判定 + 统计
"""
import json
import os
import re
from collections import Counter, defaultdict

from . import align as AL
from . import reason as RS
from . import skeleton as SK

SKEL_NAME = SK.skel_spec().get('名称', '宋本《伤寒论》398 条')
from . import spec as SP
from . import textutil as T

FANG_TAIL = r"(?:汤|散|丸|饮|煎|膏|粥)"
FANG_PAT = [
    re.compile(rf"^([一-鿿]{{2,12}}方)[①-⑳]?$"),
    re.compile(rf"([一-鿿]{{2,10}}{FANG_TAIL})主之"),
    re.compile(rf"(?:宜|与|用|服|以)([一-鿿]{{2,10}}{FANG_TAIL})"),
    re.compile(rf"([一-鿿]{{2,10}}{FANG_TAIL})方"),
]
LEAD_VERB = re.compile(
    r"^(?:宜|与|用|服|以|即|乃|复|更|先|后|急|当|改|作|为|是|主|之|者|其|于|合|如|仍|又|并|及|据|按|别|本|此|随|药|温|冷|热)")
BAD_CHAR = re.compile(r"[病证之也者卷门篇通计及则而以与宜用服]")


def extract_fang(recs):
    """按邻近关系抽方名与组成:方名之后的连续药行即其组成。"""
    res = []
    for i, r in enumerate(recs):
        st = r["raw"]
        if r["kind"] in ("foot", "toc"):
            continue
        if T.is_yaofang(st) and not re.match(rf"^[一-鿿]{{2,12}}方[①-⑳]?$", st):
            continue
        for pat in FANG_PAT:
            for m in pat.finditer(st):
                nm = m.group(1)
                if nm.endswith("方"):
                    nm = nm[:-1]
                nm = LEAD_VERB.sub("", nm)
                if len(nm) < 2:
                    continue
                if re.fullmatch(rf"[一二三四五六七八九十百千万0-9]+{FANG_TAIL}", nm):
                    continue
                if BAD_CHAR.search(nm):
                    continue
                if len(nm) > 12:
                    continue
                zc = []
                for r2 in recs[i + 1: i + 5]:
                    t2 = r2["raw"]
                    if T.is_yaofang(t2) or re.match(rf"^上[①-⑳]?[一二三四五六七八九十]+味", t2):
                        zc.append(t2)
                    else:
                        break
                res.append({"name": nm, "page": r["page"], "zucheng": " ".join(zc)})
    agg = {}
    for o in res:
        k = o["name"]
        if k not in agg or (not agg[k]["zucheng"] and o["zucheng"]):
            agg[k] = o
    return list(agg.values())


def build(pkg_dir, spec, items=None, out_dir=None):
    """跑完一个版本包,返回统计 dict。"""
    items = items or SK.load_skeleton()
    out_dir = out_dir or os.path.join(pkg_dir, "交付")
    work_dir = os.path.join(pkg_dir, "_工作")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    vname = spec["版本名"]
    units = AL.align_version(pkg_dir, spec, items=items)
    recs = AL.version_lines(os.path.join(pkg_dir, spec["文件"]))
    front, recs = AL.split_front_body(recs, spec.get("正文起点"))
    vp = RS.version_pians(spec, recs)
    # ★ 前置材料里的篇目也要收进篇目表 —— 2026-11-03 修正
    #   桂林古本设了「正文起点」,前 12 篇(平脉法、六气主客、伤寒例、温病、六淫等)
    #   走 front 通道进独有序(内容没丢),但**篇目表里一篇不见** → 16 篇而非 28 篇,
    #   篇级对照因此残缺。
    #   对 front 再跑一次 version_pians 即可(front 里 kind 仍是 head/text,能识别篇题)。
    vp_front = [x for x in RS.version_pians(spec, front)
                if x.get("name") != "(卷首前段)"]
    if vp_front:
        vp = vp_front + vp
    vp_map = {}
    for x in vp:
        vp_map.setdefault(x["name"], []).append(x)

    vidx = defaultdict(list)
    for u in units:
        if u["no"] is not None:
            vidx[u["no"]].append(u)

    rows = []
    review = []
    reason_counter = Counter()
    for no in sorted(set(i["no"] for i in items)):
        s = next(i for i in items if i["no"] == no)
        base = T.strip_for_match(s["body"])
        us = vidx.get(no, [])
        if us:
            segs = []
            for u in us:
                tag = AL.confidence(u["score"])
                segs.append({"置信": tag, "页": u["page"], "原文": u["body"],
                             "异文": T.diff_mark(base, T.strip_for_match(u["body"])),
                             "score": u["score"]})
            rows.append({"条号": no, "篇": s["pian"], "页": s["page"],
                         "宋本": s["body"], "状态": "有", "分段": segs,
                         "置信": segs[0]["置信"],
                         "原文": "\n".join(x["原文"] for x in segs),
                         "异文": "\n".join(x["异文"] for x in segs)})
            if any(x["置信"] == "低置信" for x in segs):
                worst = min(us, key=lambda x: x["score"])
                review.append((no, "低置信", worst["page"], worst["body"][:70]))
        else:
            rsn, evid = RS.classify(no, s, spec, vp_map)
            rows.append({"条号": no, "篇": s["pian"], "页": s["page"],
                         "宋本": s["body"], "状态": "无", "原因": rsn, "证据": evid})
            reason_counter[rsn] += 1
            if rsn == "暂未匹配":
                review.append((no, "暂未匹配", "", rsn))

    indep = [u for u in units if u["no"] is None]
    fang = extract_fang(recs)
    anchors = AL.extract_anchors(recs)

    # ---- 版本对照.md ----
    L = [f"# {vname} · 与{SKEL_NAME}对照", "",
         f"> 骨架:{SKEL_NAME}(公共地基,未改动)。",
         f"> 差异以【】标出;本版缺此条者,注明**原因**与**原文依据**。",
         f"> 置信:校记锚点=编者校记明注条号;高置信≥0.85;中置信≥0.6;低置信<0.6。", ""]
    cur_pian = None
    for r in rows:
        if r["篇"] != cur_pian:
            cur_pian = r["篇"]
            L += [f"## {cur_pian}", ""]
        L += [f"### 条 {r['条号']}", "", f"**宋本**(p{r['页']}):{r['宋本']}", ""]
        if r["状态"] == "有":
            for i, sg in enumerate(r["分段"]):
                pre = "  ↳" if i else "- **本版**"
                L.append(f"{pre}({sg['置信']},p{sg['页']}):{sg['异文']}")
        else:
            L.append(f"- **本版**:此版无 —— **{r['原因']}**。依据:{r['证据']}")
        L.append("")
    open(os.path.join(out_dir, "版本对照.md"), "w", encoding="utf-8").write("\n".join(L))

    # ---- 本版独有.md ----
    L = [f"# {vname} · 本版独有内容", "",
         f"> 凡本版自有、而骨架中无对应者,一律给独立 ID(`版本-独-序号`),不入主表。", ""]
    for u in indep:
        tag = " · 前置材料" if u.get("front") else ""
        L.append(f"- **{u.get('iid')}**(p{u['page']}){tag}:{u['text'][:200]}")
    L.append("")
    open(os.path.join(out_dir, "本版独有.md"), "w", encoding="utf-8").write("\n".join(L))

    # ---- 锚点表.md ----
    L = [f"# {vname} · 校记锚点表", "",
         "> 编者校记中直接指明「同《宋本伤寒论》第X条」者,系编者已核定的条号对应,本表为最高置信依据。",
         "> 圈码①②③为原书圈码,同页内条文行内圈码与页脚校记按序配对。", "",
         "锚点类型:**主锚** = 条的直接对应;**副锚** = 一条校记指两条(本版为合并条);",
         "**附条** = 仅说明方药在别条之下,**不构成条对应**,只作参考。", ""]
    if anchors:
        L += ["| 类型 | 宋本条号 | 圈码 | 页 | 校记原文 |", "| --- | --- | --- | --- | --- |"]
        for no, marker, note, page, nc, cands, kind, sub in anchors:
            L.append(f"| {kind} | {no} | {marker} | p{page} | {note} |")
    else:
        L.append("(本版无「同《宋本》第X条」式硬锚点)")
    L.append("")
    open(os.path.join(out_dir, "锚点表.md"), "w", encoding="utf-8").write("\n".join(L))

    # ---- 待复核.md ----
    L = [f"# {vname} · 待复核清单", "",
         "> 低置信匹配与「暂未匹配」条目,建议人工逐条过一遍。", "",
         "| 宋本条号 | 状态 | 页 | 摘要 |", "| --- | --- | --- | --- |"]
    for no, st, page, txt in review:
        L.append(f"| {no} | {st} | {page} | {txt} |")
    L.append("")
    open(os.path.join(out_dir, "待复核.md"), "w", encoding="utf-8").write("\n".join(L))

    # ---- 体例说明.md ----
    cov = spec.get("收录范围") or {}
    L = [f"# {vname} · 体例说明", "",
         "- 对上骨架条数:**%d** / %d" % (sum(1 for r in rows if r["状态"] == "有"), SK.n_items()),
         "- 正文起点:「%s」" % (spec.get("正文起点") or "本选集起始即正文"),
         "- 前置材料(序/凡例/校注说明/目录等):%d 行,不参与条文对照" % len(front),
         "- 收篇数:%d" % len(vp), ""]
    if cov:
        L += [f"- **「此版无」主因**:{cov.get('kind')}", f"  - 原文依据:{cov.get('evid')}", ""]
    L += ["- 本版篇目:", ""]
    for x in vp:
        L.append(f"  - {x['name']}({len(x['text'])} 字,p{x['page']})")
    L += ["", "## 「此版无」原因分布", "", "| 原因 | 条数 |", "| --- | --- |"]
    for k, c in reason_counter.most_common():
        L.append(f"| {k} | {c} |")
    L.append("")
    open(os.path.join(out_dir, "体例说明.md"), "w", encoding="utf-8").write("\n".join(L))

    # ---- 方剂表.md ----
    L = [f"# {vname} · 方剂清单", "",
         "> 方名由正文与方名行按「汤/散/丸/饮/煎/膏/粥」后缀规则抽取,属启发式,个别方名可能带赘字,详见《待复核》。", "",
         "| 方名 | 页 | 组成 |", "| --- | --- | --- |"]
    for x in sorted(fang, key=lambda z: z["name"]):
        L.append(f"| {x['name']} | p{x['page']} | {x['zucheng'][:80]} |")
    L.append("")
    open(os.path.join(out_dir, "方剂表.md"), "w", encoding="utf-8").write("\n".join(L))

    # ---- 版本包.json ----
    payload = {
        "版本名": vname,
        "骨架": SKEL_NAME + "(公共地基)",
        "条目": rows,
        "独有": [{"iid": u.get("iid"), "页": u["page"], "文本": u["text"],
                  "前置": bool(u.get("front"))} for u in indep],
        "锚点": [{"条号": a[0], "圈码": a[1], "校记": a[2], "页": a[3], "类型": a[6],
                  "副条": a[7]} for a in anchors],
        "方剂": fang,
        # raw = 原始篇题(如「平脉法第一」)。归一化会把「第X」去掉,
        # 于是「平脉法第一」「平脉法第二」都变成「平脉法」,篇级对照表看不出区别 —— 故留 raw。
        "篇目": [{"名": x["name"], "raw": x.get("raw", x["name"]),
                  "页": x["page"], "字数": len(x["text"])} for x in vp],
        "原因分布": dict(reason_counter),
        "统计": {
            "对上条数": sum(1 for r in rows if r["状态"] == "有"),
            "高置信": sum(1 for r in rows if r["状态"] == "有" and r["置信"] in ("高置信", "校记锚点")),
            "校记锚点": sum(1 for r in rows if r["状态"] == "有" and r["置信"] == "校记锚点"),
            "独立内容": len(indep),
            "方剂数": len({x["name"] for x in fang}),
            "待复核": len(review),
        },
    }
    with open(os.path.join(out_dir, "版本包.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    # ★ 引擎产出已变 → 作废上一次的叠加结果 —— 2026-11-03
    #   verify 与总装优先读「最终版本包.json」(引擎+人工裁定)。
    #   若它比引擎版旧,verify 就会拿过期数据下结论(实测金匮本因此出现假阳性)。
    #   故引擎重跑后必须删掉它,强制重跑 `shjkit.overlay`。
    fin = os.path.join(out_dir, "最终版本包.json")
    if os.path.exists(fin):
        os.remove(fin)
        print("ℹ  引擎产出已更新,已作废旧的《最终版本包.json》"
              "—— 请重跑 `python3 -m shjkit.overlay <版本包目录>`")

    with open(os.path.join(work_dir, "单元.json"), "w", encoding="utf-8") as fh:
        json.dump(units, fh, ensure_ascii=False)
    with open(os.path.join(work_dir, "篇目.json"), "w", encoding="utf-8") as fh:
        json.dump(vp, fh, ensure_ascii=False, indent=1)

    return payload["统计"]


if __name__ == "__main__":
    import sys
    pkg = sys.argv[1]
    sp = SP.load(pkg)
    src = os.path.join(pkg, sp["文件"])
    if not os.path.exists(src):
        print(f"✗ 找不到转录件:{sp['文件']}")
        print(f"  位置应为:{src}")
        print(f"  spec 里的「文件」字段指向的是包内相对路径。")
        print(f"  若刚拿到包还没开始转录,这属正常 —— 先按《任务书.md》产出转录件再跑。")
        sys.exit(2)
    st = build(pkg, sp)
    print(f"{sp['版本名']}: {st}")
