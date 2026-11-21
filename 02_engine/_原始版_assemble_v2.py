#!/usr/bin/env python3
"""总装合并器:读 N 个版本包 → 生成 398×N 主表 + 全部产出件 + HTML 浏览器。

用法:
    python3 -m shjkit.assemble <版本包目录> [<版本包目录> ...] --out <输出目录>

流程:
    1. 读各包 `交付/版本包.json`
    2. 以宋本 398 条为骨架,横向合并各版
    3. 产出:条文总表.json / 条文对照本.md / 差异索引.md / 版本独有内容.md /
            方剂对照表.md / 各版条文清单.md / 待复核清单.md / 锚点表.md /
            篇级对照.md / 各版体例说明.md / README.md / 对照浏览器.html

**合并规则(总装契约)**:
- 骨架唯一:宋本 398 条,各包不得改
- 字段名统一:各包 `版本包.json` 用同一套字段名,总装不做字段翻译
- 「此版无」的原因与证据原样带出,不改写
- 独有内容独立成篇,不入主表
- 一个版本包缺失 → 总装报错,不静默跳过
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

from . import align as AL
from . import reason as RS
from . import skeleton as SK

# SKEL_NAME 改为按骨架 id 在 assemble() 内计算（v1.1：支持 --骨架）
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


def _norm_conf(score):
    """按相似度分数推断置信(仅在段内与条目顶层都无 `置信` 时兜底)。"""
    if score is None:
        return "低置信"
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "低置信"
    if s >= 0.80:
        return "高置信"
    if s >= 0.45:
        return "中置信"
    return "低置信"


def normalize_pack(d):
    """字段归一化 —— 容忍不同来源版本包的段结构差异。

    各包由不同承接人产出,分段里的置信字段命名不统一:
      · 引擎产出:段内有 `置信`
      · 人工裁定的包:段内只有 `score`(相似度分数),`置信` 在**条目顶层**
    总装口径:条目顶层的 `置信` 是裁定结果,优先;段内无则按 `score` 兜底。
    """
    for e in d.get("条目", []):
        top = e.get("置信")
        for seg in (e.get("分段") or []):
            if not isinstance(seg, dict):
                continue
            if not seg.get("置信"):
                seg["置信"] = top or _norm_conf(seg.get("score"))
            seg.setdefault("页", e.get("页"))
            seg.setdefault("原文", "")
            seg.setdefault("异文", "")
    return d


def load_pack(pkg_dir):
    # ★ 优先读叠加人工裁定后的「最终版本包.json」;没有则退回引擎版「版本包.json」
    #   2026-11-03:引擎与人工裁定分离后,最终版才是总装的输入。
    p = os.path.join(pkg_dir, "交付", "最终版本包.json")
    if not os.path.exists(p):
        p = os.path.join(pkg_dir, "交付", "版本包.json")
    if not os.path.exists(p):
        raise FileNotFoundError(f"缺 {p}")
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    if "条目" not in d:
        raise ValueError(f"{p} 缺 '条目' 字段")
    return normalize_pack(d)


# 宋本转录件(用于取无条号篇)—— 可由 spec 指定
SONGBEN_FILE = "/workspace/output/伤寒论版本大全/版本正文/07_宋本伤寒论.md"


def song_pians(songben_file=SONGBEN_FILE):
    """宋本中**无条号**的篇(辨脉法、平脉法、伤寒例、辨痉湿暍、可·不可发汗吐下等)。

    骨架 `宋本398条.json` 只含 398 条**有编号**的条;无编号篇需从宋本转录件切取。
    这些篇在对照体系中以「篇」为对照单位。
    """
    if not os.path.exists(songben_file):
        return []
    from . import pipeline_shim as PS
    recs = PS.songben_no_number(songben_file)
    out = []
    for r in recs:
        # ★ 2026-11-04 修复:songben_no_number() 返回的键是 "n",不是 "pian"。
        #   原先取 r.get("pian") 恒为 None → spian 列表恒空 → HTML 显示「宋本无条号篇共 0 个」。
        name = RS.norm_pian(r.get("n") or r.get("pian") or "")
        if not name:
            continue
        # ★ 2026-11-04 修复:键名与 songben_no_number() 返回结构对齐("pg"/"len",非 "page")
        pg, ln = r.get("pg"), r.get("len", 0)
        if out and out[-1]["n"] == name:
            out[-1]["len"] += ln
            out[-1]["pg_end"] = pg
        else:
            out.append({"n": name, "pg": pg, "pg_end": pg, "len": ln})
    return out


def _indep_pians(pack):
    """从「独有」文本流切出该版实际存在的篇及其字数。

    独有流里各篇以**篇标题行**起头(如「平脉法第一」「杂病例第五」),
    按标题行切分即可还原该版的篇次 —— 这是比「篇目」表更可靠的来源,
    因为它直接来自实际文本流,而非人工著录。
    """
    title_map = {}
    for x in pack.get("篇目", []):
        for k in (x.get("名"), x.get("raw")):
            kk = RS.norm_pian(k or "")
            if kk:
                title_map.setdefault(kk, x.get("名") or x.get("raw"))
    out = {}
    cur = None
    for u in pack.get("独有", []):
        t = (u.get("文本") or "").strip()
        n = RS.norm_pian(t)
        hit = None
        if n:
            if n in title_map:
                hit = title_map[n]
            else:
                for k, v in title_map.items():
                    if k and len(n) <= len(k) + 4 and (k in n or n in k):
                        hit = v
                        break
        if hit:
            cur = hit
            out.setdefault(cur, {"n": 0, "c": 0})
        if cur:
            out[cur]["n"] += len(t)
            out[cur]["c"] += 1
    return out


def _spian_matrix(byver, names, sp):
    """宋本无编号篇 × 各版 有无/字数。

    判据双通道:
      1) 该版「篇目」表里存在同名篇 → 取其字数
      2) 该版「独有」文本流里出现过该篇标题行 → 取其独有字数
    两通道都不中 → 0(此版无此篇)。
    ★ 2026-11-04 修复:原先写成嵌套推导式,条件表达式里引用了生成器内部变量,
      实际捕获外层残留变量,导致整张矩阵全 0。
    """
    mat = {}
    for spn in sp:
        target = spn["n"]
        row = {}
        for nm in names:
            pack = byver[nm]
            hit = 0
            for x in pack.get("篇目", []):
                if RS.norm_pian(x.get("名") or "") == RS.norm_pian(target):
                    hit = max(hit, x.get("字数", 0))
                    break
            if not hit:
                ip = _indep_pians(pack)
                for pname, info in ip.items():
                    if RS.norm_pian(pname) == RS.norm_pian(target):
                        hit = max(hit, info["n"])
                        break
            row[nm] = hit
        mat[target] = row
    return mat


def _match_song_pian(vname, sp_names):
    """版本篇名 → 宋本篇名。"""
    if not vname:
        return None
    for sn in sp_names:
        if vname == sn:
            return sn
    for sn in sp_names:
        if sn and vname and (sn in vname or vname in sn):
            return sn
    return None


def _pian_score(vname, sp_names):
    """篇名匹配分(与引擎篇级层同口径)。"""
    if not vname:
        return 0.0
    best = 0.0
    for sn in sp_names:
        if vname == sn:
            return 1.0
        if sn and vname and (sn in vname or vname in sn):
            best = max(best, 0.7)
        else:
            common = set(vname) & set(sn)
            best = max(best, 0.4 * len(common) / max(1, min(len(vname), len(sn))))
    return best


def assemble(pkg_dirs, out_dir, skel_id=None):
    os.makedirs(out_dir, exist_ok=True)
    SKEL_NAME = SK.skel_spec(skel_id).get('名称', '宋本《伤寒论》398 条')
    items = SK.load_skeleton(skel_id)
    packs = []
    for d in pkg_dirs:
        pack = load_pack(d)
        packs.append((d, pack))
    names = [p[1]["版本名"] for p in packs]
    if len(set(names)) != len(names):
        raise ValueError(f"版本名重复:{names}")

    byver = {p[1]["版本名"]: p[1] for p in packs}
    dirmap = {p[1]["版本名"]: p[0] for p in packs}
    # 条号 → 版本 → 段
    vidx = defaultdict(lambda: defaultdict(list))
    for nm, pack in byver.items():
        for e in pack["条目"]:
            if e["状态"] == "有":
                vidx[e["条号"]][nm].extend(e.get("分段") or [])

    master = []
    reason_counter = Counter()
    for it in items:
        no = it["no"]
        rec = {"条号": no, "篇": it["pian"], "页": it["page"],
               "宋本": it["body"], "各版": {}}
        for nm, pack in byver.items():
            segs = vidx[no].get(nm, [])
            if segs:
                rec["各版"][nm] = {
                    "状态": "有",
                    "置信": segs[0]["置信"],
                    "页": segs[0]["页"],
                    "原文": "\n".join(x["原文"] for x in segs),
                    "异文": "\n".join(x["异文"] for x in segs),
                    "分段": segs,
                }
            else:
                cell = next((e for e in pack["条目"] if e["条号"] == no), None)
                rsn = cell.get("原因", "暂未匹配") if cell else "暂未匹配"
                evid = cell.get("证据", "") if cell else ""
                rec["各版"][nm] = {"状态": "无", "原因": rsn, "证据": evid}
                reason_counter[(nm, rsn)] += 1
        master.append(rec)

    with open(os.path.join(out_dir, "01_条文总表.json"), "w", encoding="utf-8") as fh:
        json.dump({"骨架": SKEL_NAME + "(公共地基)",
                   "版本": names, "条目": master}, fh, ensure_ascii=False, indent=1)

    # 02 条文对照本
    L = ["# 《伤寒论》多版本条文对照本", "",
         f"> **骨架**:{SKEL_NAME}(公共地基,只读)。",
         f"> **版本**:{'、'.join(names)}。",
         "> **对照单位**:条。差异以【】标出;某版缺此条者,注明**原因**与**原文依据**。",
         "> **置信**:校记锚点 / 高置信 ≥0.85 / 中置信 ≥0.6 / 低置信 <0.6(列入待复核)。", ""]
    cur = None
    for rec in master:
        if rec["篇"] != cur:
            cur = rec["篇"]
            L += [f"## {cur}", ""]
        L += [f"### 条 {rec['条号']}", "", f"**宋本**(p{rec['页']}):{rec['宋本']}", ""]
        for nm in names:
            c = rec["各版"][nm]
            if c["状态"] == "有":
                for i, sg in enumerate(c.get("分段") or []):
                    pre = f"- **{nm}**" if i == 0 else "  ↳"
                    L.append(f"{pre}({sg['置信']},p{sg['页']}):{sg['异文']}")
            else:
                L.append(f"- **{nm}**:此版无 —— **{c['原因']}**。依据:{c['证据']}")
            L.append("")
        L += ["---", ""]
    open(os.path.join(out_dir, "02_条文对照本.md"), "w", encoding="utf-8").write("\n".join(L))

    # 04 差异索引
    L = ["# 差异索引", "",
         f"> {len(master)} 条中,以下条目在至少一版存在文字差异。", ""]
    ndiff = 0
    for rec in master:
        diffs = [(nm, rec["各版"][nm]["异文"]) for nm in names
                 if rec["各版"][nm]["状态"] == "有" and "【" in rec["各版"][nm]["异文"]]
        if diffs:
            ndiff += 1
            L += [f"## 条 {rec['条号']} 〔{rec['篇']}〕", ""]
            for nm, mk in diffs:
                L.append(f"- **{nm}**:{mk[:400]}")
            L.append("")
    L.insert(3, f"> {SK.n_items(skel_id)} 条中,{ndiff} 条在至少一版存在文字差异。\n")
    open(os.path.join(out_dir, "04_差异索引.md"), "w", encoding="utf-8").write("\n".join(L))

    # 05 版本独有内容
    L = ["# 版本独有内容", "",
         f"> 凡本版自有、而骨架中无对应者,一律给独立 ID(`版本-独-序号`),不入主表。", ""]
    for nm, pack in byver.items():
        items_ = pack.get("独有", [])
        L += [f"## {nm}({len(items_)} 项)", ""]
        for u in items_:
            tag = " · 前置材料" if u.get("前置") else ""
            L.append(f"- **{u.get('iid')}**(p{u.get('页')}){tag}:{(u.get('文本') or '')[:200]}")
        L.append("")
    open(os.path.join(out_dir, "05_版本独有内容.md"), "w", encoding="utf-8").write("\n".join(L))

    # 06 方剂对照表
    fang = {}
    for nm, pack in byver.items():
        fang[nm] = pack.get("方剂", [])
    allf = sorted({x["name"] for nm in fang for x in fang[nm]})
    L = ["# 方剂对照表(按方名聚合)", "",
         "> 「有」=该版有此方;「—」=该版无此方;「独有」=仅此版有此方。",
         "> 方名为启发式抽取,个别可能带赘字,详见各包《待复核》。", "",
         "| 方名 | " + " | ".join(names) + " |",
         "| --- |" + " --- |" * len(names)]
    for name in allf:
        row = []
        for nm in names:
            hit = [x for x in fang[nm] if x["name"] == name]
            if hit:
                zc = hit[0].get("zucheng", "")[:60]
                row.append(f"有 p{hit[0]['page']}" + (f"｜{zc}" if zc else ""))
            else:
                row.append("—")
        L.append(f"| {name} | " + " | ".join(row) + " |")
    L += ["", "## 各版方剂统计", ""]
    cnt = Counter(x["name"] for nm in fang for x in fang[nm])
    for nm in names:
        names_ = {x["name"] for x in fang[nm]}
        only = sorted(n for n in names_ if cnt[n] == 1)
        L.append(f"- **{nm}**:共 {len(names_)} 方;其中**该版独有** {len(only)} 方"
                 + (f"({'、'.join(only[:24])})" if only else ""))
    open(os.path.join(out_dir, "06_方剂对照表.md"), "w", encoding="utf-8").write("\n".join(L))

    # 03 锚点表
    L = ["# 校记锚点表", "",
         "> 各版校记中直接指明「同《宋本伤寒论》第X条」者,系编者已核定的条号对应,本表为最高置信依据。",
         "> 类型:**主锚**=条直接对应;**副锚**=一条指两条(本版为合并条);**附条**=仅说明方药位置,不作条对应。", ""]
    for nm, pack in byver.items():
        anc = pack.get("锚点", [])
        if not anc:
            continue
        L += [f"## {nm}({len(anc)} 条)", "",
              "| 类型 | 宋本条号 | 圈码 | 页 | 校记原文 |", "| --- | --- | --- | --- | --- |"]
        for a in anc:
            L.append(f"| {a.get('类型', '主锚')} | {a['条号']} | {a['圈码']} | p{a['页']} | {a['校记']} |")
        L.append("")
    open(os.path.join(out_dir, "03_锚点表.md"), "w", encoding="utf-8").write("\n".join(L))

    # 07 各版条文清单
    L = ["# 各版条文清单", "",
         "> 每版按其自身体例的条/篇次列出,并标注对应的宋本条号。", ""]
    for nm, pack in byver.items():
        L += [f"## {nm}", "", "| 宋本条号 | 置信 | 页 | 本版原文 |", "| --- | --- | --- | --- |"]
        for e in pack["条目"]:
            if e["状态"] != "有":
                continue
            for sg in (e.get("分段") or []):
                L.append(f"| {e['条号']} | {sg['置信']} | p{sg['页']} | {sg['原文'][:90]} |")
        L.append("")
    open(os.path.join(out_dir, "07_各版条文清单.md"), "w", encoding="utf-8").write("\n".join(L))

    # 08 待复核清单
    L = ["# 待复核清单", "",
         "> 低置信匹配与「暂未匹配」条目,建议人工逐条过一遍。", "",
         "| 宋本条号 | 版本 | 状态 | 页 | 摘要 |", "| --- | --- | --- | --- | --- |"]
    for nm, pack in byver.items():
        for e in pack["条目"]:
            if e["状态"] == "有":
                for sg in (e.get("分段") or []):
                    if sg["置信"] == "低置信":
                        L.append(f"| {e['条号']} | {nm} | 低置信 | p{sg['页']} | {sg['原文'][:70]} |")
            elif e.get("原因") == "暂未匹配":
                L.append(f"| {e['条号']} | {nm} | 暂未匹配 |  | {e.get('原因','')} |")
    L.append("")
    open(os.path.join(out_dir, "08_待复核清单.md"), "w", encoding="utf-8").write("\n".join(L))

    # 10 体例说明
    L = ["# 各版体例说明", "",
         "> 各版正文起讫、篇目构成、编号体例,以及「此版无」原因判定的原文依据。", ""]
    for nm, pack in byver.items():
        L += [f"## {nm}", "",
              f"- 对上骨架条数:**{sum(1 for e in pack['条目'] if e['状态'] == '有')}** / {SK.n_items(skel_id)}",
              f"- 校记硬锚点:**{len(pack.get('锚点', []))}**",
              f"- 独立内容:**{len(pack.get('独有', []))}** 项", ""]
        L += ["- 本版篇目:", ""]
        for x in pack.get("篇目", []):
            L.append(f"  - {x.get('名')}({x.get('字数', 0)} 字,p{x.get('页')})")
        L += ["", "| 原因 | 条数 |", "| --- | --- |"]
        for (v, rsn), c in sorted(reason_counter.items()):
            if v == nm:
                L.append(f"| {rsn} | {c} |")
        L.append("")
    open(os.path.join(out_dir, "10_各版体例说明.md"), "w", encoding="utf-8").write("\n".join(L))

    # 宋本**有编号**篇名 —— 取自 398 条骨架自身的「篇」字段。
    #   ★ 2026-11-04 修复:原先 sp_names 被赋成 song_pians() 的结果(即**无编号**篇),
    #   却拿它去匹配各版的**有编号**篇名(如「辨太阳病脉证并治上」),
    #   导致篇级对照 s 字段对所有版本匹配率 0% —— 篇级对照其实从未真正工作过。
    sp_names = []
    for rec in master:
        pn = RS.norm_pian(rec.get("篇") or "")
        if pn and pn not in sp_names:
            sp_names.append(pn)

    # 宋本**无编号**篇(辨脉法/平脉法/伤寒例/辨痉湿暍等)—— 整篇无条号者。
    #   song_pians() 会把有编号篇的**标题行**也带出来(标题行本身 no=None),
    #   故须减去有编号篇集合,剩下的才是真正的无编号篇。
    sp = song_pians()
    spion_names = [x["n"] for x in sp if x["n"] not in sp_names]
    # 无编号篇矩阵只保留真·无编号篇
    sp = [x for x in sp if x["n"] in spion_names]

    # viewer 数据
    vitems = []
    for rec in master:
        vitems.append({
            "n": rec["条号"], "pian": rec["篇"], "pg": rec["页"], "s": rec["宋本"],
            "v": {nm: ({"ok": 1, "cf": rec["各版"][nm]["置信"], "pg": rec["各版"][nm]["页"],
                        "t": rec["各版"][nm]["原文"], "d": rec["各版"][nm]["异文"]}
                      if rec["各版"][nm]["状态"] == "有" else
                      {"ok": 0, "rs": rec["各版"][nm]["原因"], "ev": rec["各版"][nm]["证据"]})
                   for nm in names},
        })
    viewer = {
        "vers": names,
        "items": vitems,
        "fang": {nm: {x["name"]: {"pg": x["page"], "zc": x.get("zucheng", "")} for x in fang[nm]}
                 for nm in names},
        "fangStat": {nm: {"n": len({x["name"] for x in fang[nm]}),
                          "only": sorted(nm2 for nm2 in {x["name"] for x in fang[nm]}
                                         if sum(1 for vv in fang if nm2 in {x["name"] for x in fang[vv]}) == 1)}
                     for nm in names},
        "indep": {nm: [{"id": u.get("iid"), "pg": u.get("页"), "t": (u.get("文本") or "")[:400]}
                       for u in byver[nm].get("独有", [])] for nm in names},
        # 篇级数据:各版本篇目 → 对应宋本篇
        # ★ 2026-11-04:篇级对照补「归属」——
        #   s  = 对应宋本**有编号**篇(如「辨太阳病脉证并治上」)
        #   sp = 对应宋本**无编号**篇(如「平脉法」「伤寒例」「辨痉湿暍」)
        #   own= 1 表示本版独有篇(宋本无论有无编号篇都没有)
        #   「暂未匹配」只针对原文,篇名未匹配属篇级差异,不算裁定结论。
        "pian": {nm: [{"v": x.get("名"), "raw": x.get("raw"),
                       "s": _match_song_pian(x.get("名"), sp_names),
                       "sp": _match_song_pian(x.get("名"), spion_names),
                       "own": 1 if (not _match_song_pian(x.get("名"), sp_names)
                                    and not _match_song_pian(x.get("名"), spion_names)) else 0,
                       "sc": round(_pian_score(x.get("名"), sp_names), 3),
                       "len": x.get("字数", 0)}
                      for x in byver[nm].get("篇目", [])] for nm in names},
        # 宋本无编号篇 × 各版 有无 对照矩阵(篇级覆盖的真实全貌)
        "spianMap": _spian_matrix(byver, names, sp),
        # 宋本无条号篇(辨脉法、平脉法、伤寒例、可·不可发汗吐下等)
        "spian": [{"n": x.get("n"), "pg": x.get("pg"), "len": x.get("len", 0)}
                  for x in sp],
        # 宋本**有编号**篇名单 —— 供 HTML 端自检交叉验证:
        #   无编号篇清单里若混进有编号篇,即为数据错误(旧版曾如此)。
        "numberedPian": list(sp_names),
        "review": [],
        "cover": {},
        "stats": {nm: {"hit": sum(1 for e in byver[nm]["条目"] if e["状态"] == "有"),
                       "hi": sum(1 for e in byver[nm]["条目"] if e["状态"] == "有"
                                 and e.get("置信") in ("高置信", "校记锚点")),
                       "anc": sum(1 for e in byver[nm]["条目"] if e["状态"] == "有"
                                  and e.get("置信") == "校记锚点"),
                       "ind": len(byver[nm].get("独有", []))}
                 for nm in names},
        "reason": {f"{v}|{r}": c for (v, r), c in reason_counter.items()},
    }
    for nm, pack in byver.items():
        for e in pack["条目"]:
            if e["状态"] == "有":
                for sg in (e.get("分段") or []):
                    if sg["置信"] == "低置信":
                        viewer["review"].append({"n": e["条号"], "v": nm, "st": "低置信",
                                                 "pg": sg["页"], "t": sg["原文"][:70]})
            elif e.get("原因") == "暂未匹配":
                viewer["review"].append({"n": e["条号"], "v": nm, "st": "暂未匹配",
                                         "pg": "", "t": e.get("原因", "")})
    # ★ 各版注文(如成无己《注解伤寒论》注文 × 宋本 398 条)—— 2026-11-04
    #   F 包交回的《注文对照.md》是那一包最值钱的产出,不能只躺在 md 里。
    #   解析「## 宋本第 N 条」→【成无己注】,挂到条号上,HTML 里逐条显示。
    import re as _re
    notes_by_no = {}
    for nm, d in dirmap.items():
        fp = os.path.join(d, "交付", "注文对照.md")
        if not os.path.exists(fp):
            continue
        try:
            txt = open(fp, encoding="utf-8").read()
        except Exception:
            continue
        blocks = _re.split(r"\n##\s+宋本第\s*(\d+)\s*条", txt)
        # blocks[0] 是前言,之后 (条号, 正文) 成对
        got = 0
        for i in range(1, len(blocks) - 1, 2):
            try:
                no = int(blocks[i])
            except ValueError:
                continue
            m = _re.search(r"【成无己注】\s*\n(.*?)(?=\n【|\n---|\Z)", blocks[i + 1], _re.S)
            if not m:
                continue
            body = m.group(1).strip()
            if not body:
                continue
            notes_by_no.setdefault(str(no), {})[nm] = body
            got += 1
        if got:
            print(f"  · 注文载入:{nm} {got} 条")
    viewer["notes"] = notes_by_no

    # 骨架元信息(丙方案:多骨架数据层)
    _spec = SK.skel_spec(skel_id)
    viewer["expect"] = SK.n_items(skel_id)
    viewer["skel"] = {
        "id": _spec.get("id"),
        "名称": _spec.get("名称"),
        "编号空间": _spec.get("编号空间"),
        "条数": SK.n_items(skel_id),
        "分层": bool(_spec.get("分层", False)),
        "子层": _spec.get("子层"),
    }
    with open(os.path.join(out_dir, "viewer_data.json"), "w", encoding="utf-8") as fh:
        json.dump(viewer, fh, ensure_ascii=False, separators=(",", ":"))

    # 00 README
    L = ["# 《伤寒论》多版本结构化对照 · 总览", "",
         f"> 骨架:{SKEL_NAME}(公共地基,只读)。",
         f"> 版本数:{len(names)} —— {'、'.join(names)}", "",
         "## 文件", "",
         "| 文件 | 内容 |", "| --- | --- |",
         f"| `01_条文总表.json` | 机器可读主数据:{SK.n_items(skel_id)} 条 × N 版 |",
         "| `02_条文对照本.md` | 人读主文件 |",
         "| `03_锚点表.md` | 校记硬锚点 |",
         "| `04_差异索引.md` | 有文字差异的条目 |",
         "| `05_版本独有内容.md` | 各版独立内容 |",
         "| `06_方剂对照表.md` | 按方名聚合 |",
         "| `07_各版条文清单.md` | 各版条次 + 对应宋本条号 |",
         "| `08_待复核清单.md` | 低置信与暂未匹配 |",
         "| `10_各版体例说明.md` | 体例与「此版无」依据 |",
         "| `对照浏览器.html` | 自包含单文件浏览器(离线可用) |",
         "", "## 统计", "",
         "| 版本 | 对上宋本条数 | 高置信 | 校记锚点 | 独立内容 |", "| --- | --- | --- | --- | --- |"]
    for nm in names:
        s = viewer["stats"][nm]
        L.append(f"| {nm} | {s['hit']} | {s['hi']} | {s['anc']} | {s['ind']} |")
    L += ["", "## 「此版无」原因分布", "", "| 版本 | 原因 | 条数 |", "| --- | --- | --- |"]
    for (v, rsn), c in sorted(reason_counter.items()):
        L.append(f"| {v} | {rsn} | {c} |")
    L.append("")
    open(os.path.join(out_dir, "00_README.md"), "w", encoding="utf-8").write("\n".join(L))

    # 09 篇级对照 —— 2026-11-03 补:数据一直有算(viewer["pian"]),但**从没写过文件**,
    #   于是总装产出少一件(旧版 12 件 → 新版 11 件)。
    L = ["# 篇级对照(无条号篇)", "",
         "> 辨脉法、平脉法、伤寒例、辨痉湿暍、可·不可发汗吐下等篇,宋本不编条号,故以「篇」为对照单位。", ""]
    for nm in names:
        L.append(f"## {nm}")
        L.append("")
        L.append("| 本版篇 | 原题 | 对应宋本篇 | 匹配分 | 本版字数 |")
        L.append("| --- | --- | --- | --- | --- |")
        for x in viewer["pian"].get(nm, []):
            s = x.get("s") or "**独立篇**"
            raw = x.get("raw") or ""
            # 原题与归一名不同时才多列一栏(如「平脉法」←「平脉法第一」)
            rawcell = raw if raw and raw != x.get("v") else ""
            L.append(f"| {x.get('v')} | {rawcell} | {s} | {x.get('sc')} | {x.get('len')} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## 宋本无条号篇")
    L.append("")
    L.append("| 篇 | 页 | 字数 |")
    L.append("| --- | --- | --- |")
    for x in viewer["spian"]:
        L.append(f"| {x.get('n')} | {x.get('pg')} | {x.get('len')} |")
    L.append("")
    open(os.path.join(out_dir, "09_篇级对照.md"), "w", encoding="utf-8").write("\n".join(L))

    return {"版本": names, "条目数": len(master), "输出": out_dir}


def main():
    args = sys.argv[1:]
    out = None
    skel_id = None
    dirs = []
    i = 0
    while i < len(args):
        if args[i] == "--out":
            out = args[i + 1]
            i += 2
        elif args[i] in ("--骨架", "--skel"):
            skel_id = args[i + 1]
            i += 2
        else:
            dirs.append(args[i])
            i += 1
    if not dirs or not out:
        print("用法:python3 -m shjkit.assemble <版本包目录> [...] --out <输出目录> [--骨架 shanghan|jingui]")
        sys.exit(2)
    r = assemble(dirs, out, skel_id)
    print(f"总装完成:{r['条目数']} 条 × {len(r['版本'])} 版 → {r['输出']}")
    print("版本:", "、".join(r["版本"]))


if __name__ == "__main__":
    main()
