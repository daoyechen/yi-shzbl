#!/usr/bin/env python3
"""对齐引擎:把某版本转录件对齐到宋本 398 条公共骨架。

对齐判据(与公共地基一致,不得私改):
  1. 校记硬锚点优先 —— 编者校记明注「同《宋本伤寒论》第X条」者,直接采用
  2. 字符 n-gram 召回候选,按「短文本覆盖率」排序
  3. 单调序列比对(DP)约束位置 —— 版本内条文顺序不得任意跳回
  4. 药行/服法行/脚注行不参与匹配,归属前一条
  5. 匹配不上者 = 该版独立内容,给独立 ID(`版本-独-序号`),不入主表

**算法只做高置信度辅助,主体靠逐条比对** —— 匹配结果均带置信分,低置信者
自动进入待复核清单,由人工逐条核验。
"""
import difflib
import os
import re
from collections import defaultdict

from . import textutil as T
from . import skeleton as SK
from . import spec as SP

MARK = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

# 校记锚点:编者明注「同《宋本伤寒论》第X条」者
SONG_NUM = re.compile(r"同《宋本伤寒论》第([一二三四五六七八九十百零]+)条")
# 更宽松的写法:「同宋本第X条」「与宋本第X条同」「按《宋本》第X条」
SONG_NUM2 = re.compile(r"(?:同|与|按|依)\s*《?宋本》?(?:伤寒论)?第([一二三四五六七八九十百零]+)条")
# 一条校记可能同时指两条:「同《宋本伤寒论》第六十八条和第七十条」
SONG_NUM_MULTI = re.compile(
    r"同《宋本伤寒论》第([一二三四五六七八九十百零]+)条"
    r"(?:(?:和|与|、)\s*第([一二三四五六七八九十百零]+)条)?")
# 附带引用(不作强制锚点):方药在别条之下、「缺此条」之类
SONG_REF = re.compile(r"《宋本[^》]*》(?:方药)?(?:则)?(?:列|附)在第([一二三四五六七八九十百零]+)条")

MIN_SCORE = 0.45
JUMP_C = 0.22
JUMP_D = 0.05
IND_C = 0.9
IND_S = 0.02


def cn2int(s):
    """**通行写法**中文数字 → 整数。

    校记里的条号用的是通行写法(一百=100、三百零四=304、二百三十六=236),
    与宋本正文的**逐位写法**(九九=99、三九八=398)不是同一套 —— 两者不可混用解析器。

    旧解析器只处理「十」不处理「百」,且把「一百」解析成 10,
    导致 64 条校记锚点中 25 条指向错误条号、9 条被静默丢弃。本函数为修正版。
    """
    if not s:
        return None
    D = {'零': 0, '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
         '六': 6, '七': 7, '八': 8, '九': 9}
    sec = 0
    num = 0
    for ch in s:
        if ch in D:
            num = D[ch]
        elif ch == '十':
            sec += (num or 1) * 10
            num = 0
        elif ch == '百':
            sec += (num or 1) * 100
            num = 0
        elif ch == '零':
            num = 0
    v = sec + num
    return v if v > 0 else None


def version_lines(path):
    """把转录件拆成行记录,带页码;标出药行/脚注行/目录行。"""
    body = T.load(path)
    recs = []
    for pno, lines in T.page_blocks(body):
        for ln in lines:
            st = ln.strip()
            if not st:
                continue
            if st.startswith("## ") or st.startswith("**"):
                recs.append({"page": pno, "raw": st.strip("*").strip().lstrip("#").strip(),
                             "kind": "head"})
                continue
            if re.fullmatch(r"[0-9]{1,4}", st):
                continue
            if T.is_footnote(st):
                kind = "foot"
            elif T.is_yaofang(st):
                kind = "yao"
            elif ("…" in st or "⋯" in st or "~~~~" in st or re.search(r"[.]{4,}", st)):
                kind = "toc"
            else:
                kind = "text"
            recs.append({"page": pno, "raw": st, "kind": kind})
    return recs


def split_front_body(recs, marker):
    """按正文起点标志切掉前置材料(序/凡例/目录/校注说明)。"""
    if not marker:
        return [], list(recs)
    idx = None
    for i, r in enumerate(recs):
        if marker in r["raw"]:
            idx = i
    if idx is None:
        return list(recs), []
    return list(recs[:idx]), list(recs[idx:])


def best_song(key, items, idx, topk=4):
    """把一段文字匹配到宋本条。主指标 = 短文本覆盖率。"""
    if len(key) < 4:
        return []
    cnt = defaultdict(int)
    for g in T.ngrams(key):
        for i in idx.get(g, ()):
            cnt[i] += 1
    if not cnt:
        return []
    out = []
    for i, c in cnt.items():
        k2 = items[i]["key"]
        if not k2:
            continue
        sm = difflib.SequenceMatcher(None, key, k2, autojunk=False)
        m = sum(b.size for b in sm.get_matching_blocks())
        cov = m / max(1, min(len(key), len(k2)))
        out.append((round(cov, 4), m, items[i]["no"], i))
    out.sort(reverse=True)
    return out[:topk]


def align_monotonic(recs, items, idx, forced=None):
    """序列比对:行序 ↔ 宋本条序,单调前进。"""
    text_rows = [i for i, r in enumerate(recs) if r["kind"] == "text"]
    cand = {}
    for i in text_rows:
        key = T.strip_for_match(recs[i]["raw"])
        cs = best_song(key, items, idx, topk=6)
        cand[i] = {c[3]: (c[0] if c[1] >= 10 else 0.0) for c in cs}
    m = len(items)
    NEG = -1e9
    forced = forced or {}
    for i, jv in forced.items():
        j = jv[0] if isinstance(jv, tuple) else jv
        cand[i] = {j: 5.0}
    dp = [0.0] * (m + 1)
    back = []
    for i in text_rows:
        s = cand.get(i, {})
        ndp = [NEG] * (m + 1)
        bk = [0] * (m + 1)
        run, runk = NEG, 0
        for j in range(m + 1):
            best, bj = dp[j], j
            if run > NEG / 2:
                v = run - JUMP_D * j - JUMP_C + JUMP_D
                if v > best:
                    best, bj = v, runk
            ndp[j] = best + s.get(j, 0.0)
            bk[j] = bj
            if dp[j] + JUMP_D * j > run:
                run, runk = dp[j] + JUMP_D * j, j
        if dp[m] > NEG / 2:
            ndp[m] = dp[m] - IND_S
            bk[m] = m
        for j in range(m):
            v = dp[m] - IND_C + s.get(j, 0.0)
            if v > ndp[j]:
                ndp[j] = v
                bk[j] = m
        dp = ndp
        back.append(bk)
    state = max(range(m + 1), key=lambda k: dp[k])
    path = []
    for i in range(len(text_rows) - 1, -1, -1):
        path.append(state)
        state = back[i][state]
    path.reverse()
    out = {}
    for pos, i in enumerate(text_rows):
        st = path[pos]
        out[i] = (None if st == m else items[st]["no"],
                  None if st == m else st,
                  cand.get(i, {}).get(st, 0.0) if st != m else 0.0)
    return out


def extract_anchors(recs):
    """抽取硬锚点。

    返回 [(宋本条号, 圈码, 校记原文, 页码, 同码候选数, 候选行下标, 锚点类型)]

    锚点类型:
      主锚  校记明注「同《宋本伤寒论》第X条」——条的直接对应,最高置信
      副锚  一条校记同时指两条(「第六十八条和第七十条」)——只取第一条作主锚,
            第二条另记入 `副条`,因其对应的是本版的**合并条**,非一一对应
      附条  「方药《宋本》列在第X条下」—— 只说明方药位置,不等于本条对应,
            **不作强制锚点**,仅作参考信息保留

    配对规则:同页内,第 k 个带该圈码的条文 ↔ 第 k 个带该圈码的页脚校记。
    """
    by_page_txt = defaultdict(list)
    by_page_note = defaultdict(list)
    for ri, r in enumerate(recs):
        if r["kind"] == "text":
            for ch in MARK:
                if ch in r["raw"]:
                    by_page_txt[r["page"]].append((ri, ch))
        elif r["kind"] == "foot":
            m = re.match(rf"^([{MARK}])\s*(.*)$", r["raw"])
            if m:
                by_page_note[r["page"]].append((m.group(1), m.group(2)))
    out = []
    for page, notes in by_page_note.items():
        for marker, note in notes:
            m = SONG_NUM_MULTI.search(note)
            if m:
                no = cn2int(m.group(1))
                sub = cn2int(m.group(2)) if m.group(2) else None
                if not no:
                    continue
                cands = [t for t in by_page_txt.get(page, []) if t[1] == marker]
                if not cands:
                    continue
                out.append((no, marker, note, page, len(cands), cands,
                            "主锚" if not sub else "副锚",
                            sub))
                continue
            m = SONG_NUM2.search(note)
            if m:
                no = cn2int(m.group(1))
                if not no:
                    continue
                cands = [t for t in by_page_txt.get(page, []) if t[1] == marker]
                if not cands:
                    continue
                out.append((no, marker, note, page, len(cands), cands, "主锚", None))
                continue
            m = SONG_REF.search(note)
            if m:
                no = cn2int(m.group(1))
                if not no:
                    continue
                cands = [t for t in by_page_txt.get(page, []) if t[1] == marker]
                if not cands:
                    continue
                out.append((no, marker, note, page, len(cands), cands, "附条", None))
    return out


def anchor_index(recs):
    """(页, 圈码) → [(条文行下标, 宋本条号, 校记原文, 锚点类型)]。

    只收主锚/副锚;「附条」仅说明方药位置,不作强制对应。
    """
    mp = {}
    for no, marker, note, page, nc, cands, kind, sub in extract_anchors(recs):
        if kind == "附条":
            continue
        k = len(mp.get((page, marker), []))
        if k < len(cands):
            mp.setdefault((page, marker), []).append((cands[k][0], no, note, kind))
    return mp


_IDX_CACHE = [None]


def align_version(pkg_dir, spec, items=None, idx=None, split_on_change=True):
    """把一个版本对齐到骨架,返回单元列表。

    单元结构(与公共地基一致):
      no       对应的宋本条号;None = 该版独立内容
      page     起始页;page_end 结束页
      lines    全部行(含药行/脚注行)
      body     去掉药行/脚注行后的条文正文
      score    匹配得分
      iid      独立内容 ID(仅 no 为 None 时)
    """
    if items is None:
        items = SK.load_skeleton()
    if idx is None:
        idx = SK.build_index(items)
    _IDX_CACHE[0] = idx
    path = os.path.join(pkg_dir, spec["文件"])
    recs = version_lines(path)
    # 正文起点之前的内容不能丢 —— 逐行生成 front 独立单元。
    # (旧实现把 front 移出 recs 后主循环只遍历 body,导致这部分内容彻底消失;
    #  对多数版本 front 只是「序/凡例」,不明显;对桂林古本 front 是 12 篇正文,损失巨大。)
    front, body = split_front_body(recs, spec.get("正文起点"))
    for r in front:
        r["kind"] = "front"
    recs = body

    forced = {}
    anchored = set()
    if spec.get("校记锚点"):
        amap = anchor_index(recs)
        no2i = {it["no"]: k for k, it in enumerate(items)}
        for i, r in enumerate(recs):
            if r["kind"] != "text":
                continue
            for ch in MARK:
                if ch in r["raw"] and (r["page"], ch) in amap:
                    hit = [t for t in amap[(r["page"], ch)] if t[0] == i]
                    if not hit:
                        continue
                    k = no2i.get(hit[0][1])
                    if k is not None:
                        forced[i] = (k, hit[0][2], hit[0][3])
                        anchored.add(i)
                    break
    assigns = align_monotonic(recs, items, idx, forced)
    for i in anchored:
        if i in assigns:
            assigns[i] = (assigns[i][0], assigns[i][1], 5.0)

    units = []
    cur = None
    prev_ended = True
    vname = spec["版本名"]

    # ---- 前置材料(正文起点之前)→ 独立内容,逐行保留 ----
    if front:
        for r in front:
            units.append({"no": None, "page": r["page"], "page_end": r["page"],
                          "lines": [r["raw"]], "src": [], "score": 0.0, "pian": None,
                          "indep": True, "front": True})

    for i, r in enumerate(recs):
        no, idx_, sc = assigns.get(i, (None, None, 0.0))
        if r["kind"] == "front":
            if cur is not None:
                units.append(cur)
                cur = None
            units.append({"no": None, "page": r["page"], "page_end": r["page"],
                          "lines": [r["raw"]], "src": [i], "score": 0.0, "pian": None,
                          "indep": True, "front": True})
            prev_ended = True
            continue
        if r["kind"] in ("yao", "foot", "toc"):
            if r["kind"] == "toc":
                if cur is not None:
                    units.append(cur)
                    cur = None
                units.append({"no": None, "page": r["page"], "page_end": r["page"],
                              "lines": [r["raw"]], "src": [i], "score": 0.0, "pian": None,
                              "indep": True})
            elif cur is not None:
                cur["lines"].append(r["raw"])
                cur["src"].append(i)
                cur["page_end"] = r["page"]
            # 校记(脚注)是页下注,不是正文流的一部分,
            # **不应重置续行判定** —— 否则跨页续写的条文会被页脚校记切断。
            # 药行/目录行则仍按原逻辑收束。
            if r["kind"] != "foot":
                prev_ended = r["raw"].rstrip()[-1:] in "。？！：;；"
            continue
        # 续行判定:上一行未以句读收尾 = 句子未完,本行是其续行。
        # 原实现额外要求同页,导致**跨页续行被拆成两个单元**(康治本 9 处),
        # 且落在续行末的校记锚点会错位到半个条上。
        # 放宽为允许跨页:「未以句读收尾」本身已足够强,且药行/脚注另行处理。
        cont = (not prev_ended) and cur is not None
        if cont:
            cur["lines"].append(r["raw"])
            cur["src"].append(i)
            cur["page_end"] = r["page"]
            cur["score"] = max(cur["score"], sc)
            prev_ended = r["raw"].rstrip()[-1:] in "。？！：;；"
            continue
        if cur is not None:
            units.append(cur)
            cur = None
        if no is not None and sc >= MIN_SCORE:
            cur = {"no": no, "page": r["page"], "page_end": r["page"],
                   "lines": [r["raw"]], "src": [i], "score": sc, "pian": None}
        else:
            units.append({"no": None, "page": r["page"], "page_end": r["page"],
                          "lines": [r["raw"]], "src": [i], "score": sc, "pian": None,
                          "indep": True})
        prev_ended = r["raw"].rstrip()[-1:] in "。？！：;；"
    if cur is not None:
        units.append(cur)

    # 校记锚点必须落到**条级**:
    #   圈码印在条末(如「麻黄汤主之③。」),而条文本身常跨多行。
    #   若只在行级套用 forced,锚点会落在续行上,组装单元时被丢弃 —— 锚点等于失效。
    #   故此处按「包含该锚点行的整个单元」回填条号与置信。
    if forced:
        for u in units:
            hit = [i for i in u.get("src", []) if i in forced]
            if not hit:
                continue
            fv = forced[hit[0]]
            k, note, akind = (fv if isinstance(fv, tuple) else (fv, "", "主锚"))
            u["no"] = items[k]["no"]
            u["score"] = 5.0
            u["anchored"] = True
            u.pop("indep", None)
            u["锚点校记"] = note
            u["锚点类型"] = akind


    k = 0
    for i, u in enumerate(units):
        u["id"] = f"{vname}#{i + 1}"
        body_lines = [l for l in u["lines"] if not T.is_footnote(l) and not T.is_yaofang(l)]
        u["body"] = "\n".join(body_lines)
        u["key"] = T.strip_for_match(u["body"])
        u["text"] = "\n".join(u["lines"])
        if u["no"] is None:
            k += 1
            u["iid"] = f"{vname}-独-{k:04d}"

    # 单元内再切分:
    #   某版的一条,在宋本可能拆成两条(如唐本「问曰:病有结胸…藏结」通篇不分,
    #   而宋本分为条128、条130);反之宋本一条该版可能分作两条。
    #   跨页合并后单元可能同时对应多个宋本条 —— 此时按「各行最优对应的条号变化处」切开,
    #   既保住跨页的完整文字,又不丢条号。
    if split_on_change:
        units = _split_by_no_change(units, assigns, items)

    units = _collect_candidates(units, items)

    # 重复主张检测:同一条宋本条被本版多个单元认领。
    # 这在「该版一条 = 宋本多条」或「该版多条 = 宋本一条」时必然出现,
    # 不是错误,但必须留痕 —— 否则读者会以为某一处重复是笔误。
    _claim = defaultdict(list)
    for u in units:
        if u.get("no") is not None:
            _claim[u["no"]].append(u["id"])
    for no, ids in _claim.items():
        if len(ids) > 1:
            for u in units:
                if u.get("no") == no:
                    u.setdefault("同条其他单元", [i for i in ids if i != u["id"]])

    # 锚点与文本冲突检测(须在 body 计算之后):
    #   校记明注的条号,若与该条宋本正文明显不符,说明校记本身有问题
    #   (实测:校记作「第223条」,而文字实为宋本第323条「少阴病,脉沉者,急温之,宜四逆汤」)。
    #   依「校记优先」原则仍采用校记条号,但**必须显式标出冲突**,
    #   交人工裁决 —— 不许静默改写,也不许装作没看见。
    #   若校记自身已载明差异(如「但《宋本》作…」「文字略有差异」「的后半条」),
    #   则不判冲突,只标「校记已载差异」。
    for u in units:
        if not u.get("anchored"):
            continue
        ref = next((it["body"] for it in items if it["no"] == u["no"]), "")
        if not ref or not u.get("body"):
            continue
        ratio = difflib.SequenceMatcher(
            None, u["body"][:40], ref[:40], autojunk=False).ratio()
        u["锚点相似度"] = round(ratio, 3)
        note = u.get("锚点校记", "")
        if _note_is_partial(note):
            # 校记明写「某条的后半条/前半条」—— 相似度天然低,不是错
            u["校记已载差异"] = True
            u["校记部分对应"] = note
        elif ratio < ANCHOR_CONFLICT_RATIO:
            near = _nearest_song(items, idx, u["body"])
            u["锚点冲突"] = True
            u["锚点冲突说明"] = (
                f"校记条号 {u['no']} 与本条文字不符(相似度 {ratio:.2f});"
                f"文字最接近宋本第 {near} 条,疑为校记条号有误,待人工裁决")
        elif ratio < ANCHOR_OK_RATIO and _note_documents_diff(note):
            u["校记已载差异"] = True
    return units


ANCHOR_CONFLICT_RATIO = 0.35   # 低于此值:校记条号与文字严重不符,判冲突
ANCHOR_OK_RATIO = 0.50         # 低于此值但校记已自载差异:只标差异,不判冲突

# 校记中自陈差异的措辞 —— 命中即说明「文字对不上」是编者已知的
_DIFF_WORDS = ("但《宋本》", "但《宋本", "略有差异", "文字略有", "的后半条",
               "的前半条", "略有异同", "作", "列在", "合为一条")


def _note_is_partial(note):
    """校记是否明写「某条的前半条/后半条」—— 此类相似度低属正常。"""
    if not note:
        return False
    return ("前半条" in note) or ("后半条" in note)


def _note_documents_diff(note):
    """校记原文是否已自陈差异。"""
    if not note:
        return False
    return any(w in note for w in _DIFF_WORDS)


def _nearest_song(items, idx, body):
    """给锚点冲突找最接近的宋本条号(仅作提示,不改判定)。"""
    key = T.strip_for_match(body)
    if not key:
        return None
    cs = best_song(key, items, idx, topk=1)
    return cs[0][2] if cs else None


def _split_by_no_change(units, assigns, items):
    """把「各行对应不同宋本条」的单元按变化处切开。

    仅对**无锚点**的单元执行 —— 有锚点的单元,条号由校记裁定,不算法改写。
    切分点取「该行 DP 归属的条号」发生变化处。
    """
    out = []
    for u in units:
        if u.get("anchored") or u.get("no") is None:
            out.append(u)
            continue
        src = u.get("src", [])
        if len(src) < 2:
            out.append(u)
            continue
        # 每个行对应的条号(DP 结果)
        nos = []
        for i in src:
            a = assigns.get(i)
            nos.append(a[0] if a else None)
        # 找变化点:与「上一个有效条号」比较,而不是与紧邻行比较。
        # 脚注行(校记)不参与 DP 归属,nos 中为 None;
        # 若只比相邻行,会被脚注行隔断,变化点就漏了。
        cuts = []
        last = None
        for j, nv in enumerate(nos):
            if not nv:
                continue
            if last is not None and nv != last:
                cuts.append(j)
            last = nv
        if not cuts:
            out.append(u)
            continue
        # 切
        bounds = [0] + cuts + [len(src)]
        for bi in range(len(bounds) - 1):
            a, b = bounds[bi], bounds[bi + 1]
            part = dict(u)
            part["src"] = src[a:b]
            part["lines"] = u["lines"][a:b]
            part["no"] = nos[a] if nos[a] else u["no"]
            out.append(part)
    return out


def _collect_candidates(units, items):
    """为每个单元记下其正文最接近的若干宋本条号(候选条)。

    用途:某版一条在宋本被拆成多条时(如唐本「问曰:病有结胸…答曰…」通篇不分,
    宋本分条128、条130),主条号只能取其一,其余必须留痕,
    **不许静默丢失** —— 交人工在证级层面裁定。
    """
    for u in units:
        if not u.get("body"):
            continue
        key = T.strip_for_match(u["body"])
        if len(key) < 8:
            continue
        cands = best_song(key, items, _IDX_CACHE[0], topk=3) if _IDX_CACHE[0] else []
        u["候选条"] = [c[2] for c in cands if c[0] >= 0.5]
        if u.get("no") and u["候选条"] and u["no"] not in u["候选条"]:
            u["候选条"].insert(0, u["no"])
    return units


def confidence(score):
    if score >= 5:
        return "校记锚点"
    if score >= 0.85:
        return "高置信"
    if score >= 0.6:
        return "中置信"
    return "低置信"
