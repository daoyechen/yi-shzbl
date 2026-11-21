#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H02 医统正脉本私用区缺字 —— 书证核对台的题面生成器。

原来 H02 的题面只给「U+FF00C + 一串带方框的上下文」，接包人看到的是
Unicode 私用区码位，既认不出字，也没有原书可翻，实际上没法判断。

这里换一条路：
  1) 27 号交付里《逐条核定表_2_5_A4》本来就同时存着
     「骨架原文（赵开美本，正常字）」和「本版原文（医统本，含私用区方框）」两栏。
     两栏逐字对齐，就能机械推出每个私用区码位本来是哪个字，不用人猜。
  2) 题面主体改成**可读的候选本字 + 五版同条原文并排书证**：
     医统本（方框位置高亮）／赵开美本／俞桥本／人卫本／邓珍本。
     接包人做的是「对书证确认」，不是「从 Unicode 码位猜字」。
  3) 码位降级成小字技术备注，只供回填替换使用。

产出（由 mk_pkg_configs.py 调用 build_h02_config，或直接运行本文件）：
  - H02_配置.json（题面）
  - 数据/医统正脉1601_全文_已释字.md（把方框换成推定本字，人读版；原件不动）
  - 数据/释字对照表.md（13 个码位 → 本字 → 证据票数）
"""
import collections
import difflib
import html
import json
import os
import re

B = "/Users/levi/Documents/医/共创/伤寒杂病论"
PKG = os.path.join(B, "04_packages", "版本包_金匮基线_v2")
A4 = os.path.join(B, "06_rulings", "逐条核定表_2_5_A4.md")
VIEWER = os.path.join(B, "35_总装产出_金匮_v0.1.0", "viewer_data.json")
H02 = os.path.join(B, "36_派发包_剩余工序", "H02_医统缺字识别_人工")
WK = os.path.join(B, "金匮要略", "交付", "task_2_1", "底本")

# 卷首题署里另有 2 个私用区码位，不在 465 条正文内，靠俞桥本四部丛刊题署对校。
TITLE_PUA = {chr(0xFF006): "漢", chr(0xFF002): "書"}

PUNCT = set("，。；：、「」『』（）《》？！·…—　 \t\r\n,.:;?!()[]{}\"'○")
# 他版里的繁／简／异体写法，用于在原文中定位同一个字
VARIANTS = {
    "為": "為为爲", "見": "見见", "傷": "傷伤", "歸": "歸归帰", "備": "備备俻偹",
    "也": "也𠃟", "三": "三叁", "二": "二貳贰", "大": "大", "小": "小",
    "子": "子", "又": "又", "了": "了",
}

VERS = [
    ("医统正脉1601", "医统本 1601（方框原位置）"),
    ("赵开美本1599", "赵开美本 1599（骨架底本）"),
    ("俞桥本四部丛刊", "俞桥本／四部丛刊"),
    ("人卫排印本1964", "人卫排印本 1964"),
    ("邓珍本1340", "邓珍本 1340"),
]


def is_pua(c):
    o = ord(c)
    return (0xE000 <= o <= 0xF8FF) or (0xF0000 <= o <= 0xFFFFD) or (0x100000 <= o <= 0x10FFFD)


def esc(s):
    return html.escape(s or "", quote=False)


def clean(s):
    return "".join(c for c in (s or "") if c not in PUNCT)


def jload(p):
    return json.load(open(p, encoding="utf-8"))


# ── 1. 双栏逐字对齐 → 码位本字表 ──────────────────────────────────────
def a4_rows():
    out = []
    for ln in open(A4, encoding="utf-8"):
        if not ln.startswith("|"):
            continue
        parts = re.split(r"(?<!\\)\|", ln.rstrip("\n"))[1:-1]
        parts = [p.strip().replace("\\|", "|") for p in parts]
        if len(parts) >= 4 and parts[0].isdigit():
            out.append((int(parts[0]), parts[1], parts[2], parts[3]))
    return out


def derive_map():
    """返回 {码位字符: {'char':本字,'votes':[(字,票数)],'hit':直接对齐处数}}。"""
    vote = collections.defaultdict(collections.Counter)
    for _no, _pian, sk, yt in a4_rows():
        a, b = clean(yt), clean(sk)   # a 含私用区，b 是正常字
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            xa, xb = a[i1:i2], b[j1:j2]
            if not xa or not xb or len(xa) != len(xb):
                continue
            for k, c in enumerate(xa):
                if is_pua(c) and not is_pua(xb[k]):
                    vote[c][xb[k]] += 1
    out = {}
    for c, v in vote.items():
        out[c] = {
            "char": v.most_common(1)[0][0],
            "votes": v.most_common(),
            "hit": sum(v.values()),
        }
    return out


# ── 2. 全书出现次数 + 书证实例 ─────────────────────────────────────────
def collect_occurrences(pua_map):
    """遍历医统版本包，统计每个码位全书出现次数，并收集书证候选。"""
    pkg = jload(os.path.join(PKG, "版本包_医统正脉1601", "交付", "版本包.json"))
    cnt = collections.Counter()
    occ = collections.defaultdict(list)
    pian_of, page_of = {}, {}
    for e in pkg["条目"]:
        no = e["条号"]
        pian_of.setdefault(no, e.get("篇", ""))
        page_of.setdefault(no, e.get("页", ""))
        for s in e.get("分段") or []:
            t = s["原文"]
            for i, c in enumerate(t):
                if not is_pua(c):
                    continue
                cnt[c] += 1
                # 该码位在全书所有分段里都收，后面按「邻字干净 + 条号分散」挑
                occ[c].append({
                    "no": no,
                    "pian": e.get("篇", ""),
                    "page": s.get("页", e.get("页", "")),
                    "text": t,
                    "idx": i,
                })
    return pkg, cnt, occ, pian_of, page_of


def readable(t, pua_map):
    """把整句里的私用区字符全部换成推定本字，让医统本原文变得可读。"""
    return "".join(pua_map.get(c, {}).get("char", c) if is_pua(c) else c for c in t)


def pick_examples(lst, n=4):
    """挑 n 个书证：优先邻字没有其他方框、且条号分散。"""
    scored = []
    for o in lst:
        t, i = o["text"], o["idx"]
        left = t[max(0, i - 3):i]
        right = t[i + 1:i + 4]
        clean_neighbour = not any(is_pua(x) for x in left + right)
        scored.append((1 if clean_neighbour else 0, o))
    scored.sort(key=lambda x: -x[0])
    out, used = [], set()
    for _s, o in scored:
        if o["no"] not in used:
            out.append(o)
            used.add(o["no"])
        if len(out) >= n:
            break
    if len(out) < n:                      # 条数不够时允许同条多处
        for _s, o in scored:
            if o not in out:
                out.append(o)
            if len(out) >= n:
                break
    return out


# ── 3. 他版窗口 ─────────────────────────────────────────────────────────
def best_window(text, ch, left, right, radius=20):
    """在他版原文里找本字最贴合的位置。

    返回 5 元组 (左串, 本字, 右串, 是否贴合, 未命中时的同条原文节选)。
    末位节选保证即使该版没有这一句，接包人也仍看得到那一版同条文字。
    """
    if not text:
        return "", "", "", False, ""
    text = re.sub(r"\s+", "", text)
    excerpt = text[:80]
    variants = set(VARIANTS.get(ch, ch))
    idxs = [i for i, c in enumerate(text) if c in variants]
    if not idxs:
        return "", "", "", False, excerpt
    best_i, best = idxs[0], -1
    for i in idxs:
        sc = 0
        for k in (3, 2, 1):
            if left[-k:] and text[max(0, i - k):i] == left[-k:]:
                sc += k
        for k in (3, 2, 1):
            if right[:k] and text[i + 1:i + 1 + k] == right[:k]:
                sc += k
        if sc > best:
            best, best_i = sc, i
    c = text[best_i]
    return (text[max(0, best_i - radius):best_i], c,
            text[best_i + 1:best_i + 1 + radius], best > 0, excerpt)


def version_windows(item, ch, left, right):
    """返回 5 版窗口。赵开美本用骨架原文 it['s']，其余从 it['v'] 取。"""
    out = {}
    out["赵开美本1599"] = best_window(item.get("s", ""), ch, left, right, 22)
    for k in ("俞桥本四部丛刊", "人卫排印本1964", "邓珍本1340"):
        cell = (item.get("v") or {}).get(k, {})
        out[k] = best_window(cell.get("t") or "", ch, left, right, 22)
    return out


def render_yitong_row(ex, left_n=16, right_n=17):
    """医统本行：待判处标【?】，其余方框仍留 〔□〕。

    这里绝不把私用区码位替换成本字——那是接包人要做的判断，不是我方给的答案。
    """
    t, i = ex["text"], ex["idx"]
    mask = lambda s: "".join("〔□〕" if is_pua(c) else c for c in s)
    left, right = mask(t[max(0, i - left_n):i]), mask(t[i + 1:i + right_n])
    return (f"<div class='prow main'><span class='pv'>医统本 1601（待判方框）</span>"
            f"<span class='pt'>…{esc(left)}<b class='qmark'>【?】</b>{esc(right)}…</span></div>")


def render_other_row(label, win):
    """他版书证：原样并列那一版的原文，不圈答案。

    原文里本来就有那个字——给书是给材料，不是给结论；由接包人自己对齐判读。
    """
    left, ch, right, ok, excerpt = win
    if not ch:
        tail = (f"<br><span class='weak'>同条原文节选：{esc(excerpt)}…</span>" if excerpt else "")
        return (f"<div class='prow'><span class='pv'>{esc(label)}</span>"
                f"<span class='pt'><span class='miss'>（该版同条无可对齐文句，可能是缺段）</span>"
                f"{tail}</span></div>")
    weak = "" if ok else "<i class=\"weak\">（繁简/异体不同，位置按最相近处取）</i>"
    return (f"<div class='prow'><span class='pv'>{esc(label)}</span>"
            f"<span class='pt'>…{esc(left)}{esc(ch)}{esc(right)}…{weak}</span></div>")


def build_proof_html(ex, pua_map, viewer_by_n, target, ch):
    t, i = ex["text"], ex["idx"]
    # readable() 只用于在他版原文里定位对应句（引擎内部排版用），不展示给接包人。
    plain = readable(t, pua_map)
    left, right = plain[max(0, i - 16):i], plain[i + 1:i + 17]
    rows = [render_yitong_row(ex)]
    item = viewer_by_n.get(ex["no"], {})
    wins = version_windows(item, ch, left[-3:], right[:3])
    for key, label in VERS[1:]:
        rows.append(render_other_row(label, wins.get(key, ("", "", "", False, ""))))
    meta = f"书证 · 条 {ex['no']} · {esc(ex['pian'])} · 段页 {esc(str(ex['page']))}"
    return f"<div class='pf'><div class='pmeta'>{meta}</div>{''.join(rows)}</div>"


# ── 3b. 卷首题署里的另外 2 个码位（靠原书题署对校）─────────────────────
def _wk_text(juan):
    p = os.path.join(WK, f"维基文库_四部丛刊本_金匮要略方论_{juan}.htm")
    raw = open(p, "rb").read()
    h = None
    for enc in ("utf-8", "gb18030", "big5"):
        try:
            h = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if h is None:
        raise RuntimeError("维基文库 htm 解码失败: " + p)
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", h))


def title_evidence(pua_map):
    """返回 (医统题署原句列表, 俞桥本繁/简书证)。书证一律从本地 htm 实取，不手写。"""
    yt = open(os.path.join(H02, "数据", "医统正脉1601_全文.md"), encoding="utf-8").read()
    segs = []
    for m in re.finditer(chr(0xFF006), yt):
        segs.append(yt[m.start():m.start() + 110].split("。")[0].strip())
    trad, simp = _wk_text("卷中"), _wk_text("卷下")

    def grab(t, pats):
        for p in pats:
            m = re.search(p, t)
            if m:
                return m.group(0)
        return ""

    ev = {
        "漢": {"trad": grab(trad, [r"漢張仲景述晉王叔和編宋林億等詮次"]),
               "simp": grab(simp, [r"汉张仲景述晋王叔和编宋林亿等诠次"]),
               "yt_pattern": r"󿀆(張仲景述)"},
        "書": {"trad": grab(trad, [r"尚書司封郎中充秘閣校理"]),
               "simp": grab(simp, [r"尚书司封郎中充秘阁校理臣林亿等诠次"]),
               "yt_pattern": r"尚󿀂(司封郎中)"},
    }
    for k, v in ev.items():
        if not v["trad"] or not v["simp"] or len(segs) < 2:
            raise RuntimeError(f"卷首题署书证不足，不臆造：{k} / {len(segs)} 处")
    return segs, ev


def write_title_evidence(segs, ev, pua_map):
    """只把两边题署原文并列，不给结论——判断权留给接包人。"""
    p = os.path.join(H02, "数据", "卷首题署对校.md")
    lines = [
        "# 卷首题署对校 · 书证材料（无答案）",
        "",
        "> 另有 2 个待判码位**不在 465 条正文里**，只出现在卷中、卷下卷首题署，",
        "> A4 双栏核定表覆盖不到。本篇把医统本题署（含 □）与俞桥本四部丛刊题署原文并列，",
        "> **请自己对齐判读，把结论填进核定台**；本文件不提供答案。",
        "",
        "## 一、医统本卷首题署（原件，□ 为待判字）",
        "",
    ]
    for i, s in enumerate(segs[:2], 1):
        lines += [f"**卷{'中' if i == 1 else '下'}**：`{s}`", ""]
    lines += [
        "医统本待判处：`□張仲景述…`、`宋尚□司封郎中…`（各 2 处，卷中、卷下各一）。",
        "",
        "## 二、俞桥本四部丛刊的对应题署（书证来源）",
        "",
        "来源：`金匮要略/交付/task_2_1/底本/维基文库_四部丛刊本_金匮要略方论_卷中.htm`、",
        "`卷下.htm`（另见本包 `数据/影印原书/` 两册影印 PDF）。",
        "",
        "| 卷 | 题署原文（照录） |",
        "|---|---|",
        f"| 卷中（繁） | {ev['漢']['trad']} |",
        f"| 卷中（繁） | {ev['書']['trad']} |",
        f"| 卷下（简） | {ev['漢']['simp']} |",
        f"| 卷下（简） | {ev['書']['simp']} |",
        "",
        "## 三、著录差异（如实记录，不替派包方裁定）",
        "",
        "医统全文 md 的提要自称「四部丛刊景印明古今医统正脉本」，而",
        "`底本/` 两册 PDF 的交付著录为「四部丛刊影印俞桥本」。两者题署文字也有出入",
        "（医统题署另有吳勉學、徐鎔校字样）。",
        "本包按 PDF 原交付著录标为俞桥本四部丛刊；若需以医统本影印原件为据，",
        "请先向派包方核实这两册 PDF 的实际版本归属。",
        "",
    ]
    open(p, "w", encoding="utf-8").write("\n".join(lines))


def build_title_item(c, ch, n, cnt_all, segs, ev, pua_map):
    """卷首题署 2 题：书证是别本题署而非五版条文并排。"""
    code = f"U+{ord(c):05X}"
    rows = []
    for i, s in enumerate(segs[:2], 1):
        # 医统题署：待判处标【?】，其余方框留 〔□〕，绝不替换成本字
        parts = []
        for x in s:
            if x == c:
                parts.append("<b class='qmark'>【?】</b>")
            elif is_pua(x):
                parts.append("〔□〕")
            else:
                parts.append(esc(x))
        rows.append(f"<div class='prow main'><span class='pv'>"
                    f"医统本 1601 · 卷{'中' if i == 1 else '下'}题署（待判方框）</span>"
                    f"<span class='pt'>{''.join(parts)}</span></div>")
    for label, txt in (
        ("俞桥本四部丛刊 · 卷中题署（维基文库）", ev[ch]["trad"]),
        ("俞桥本四部丛刊 · 卷下题署（维基文库）", ev[ch]["simp"]),
    ):
        rows.append(f"<div class='prow'><span class='pv'>{esc(label)}</span>"
                    f"<span class='pt'>{esc(txt)}</span></div>")

    glyph = (
        "<div class='glyphbox'><div class='glyphwrap'>"
        "<div class='glyphbig'>?</div><div class='glyphcap'>待判码位</div></div>"
        "<div class='evi'>"
        f"<b>{esc(code)}</b> 只在<b>卷中、卷下卷首题署</b>出现 <b>{cnt_all[c]}</b> 处，"
        "不在 465 条正文里，A4 双栏对齐表覆盖不到。"
        "<br>请对照 <b>俞桥本四部丛刊同一行题署</b>（下附繁/简两处原文），"
        "自己判出医统本方框处是哪个字，填到下方输入框。"
        "<br><span class='weak'>这一题真正要翻「对应的书本」：字在别本题署里，不在码位里。</span>"
        "</div></div>"
    )
    body = (glyph + "<div class='pftitle'>卷首题署对校 · 医统本 ↔ 俞桥本四部丛刊（请自己对齐判读）</div>"
            + f"<div class='proofs'><div class='pf'>"
              f"<div class='pmeta'>书证 · 卷中／卷下卷首题署 · 各 1 处</div>"
              + "".join(rows) + "</div></div>")
    loc = (
        "<div class='loc'><b>原书定位</b>：卷中、卷下卷首题署「□張仲景述…宋尚□司封郎中…」。"
        f"<br><b>待判码位</b>：<code>{esc(code)}</code>（回填时按此码位替换）。"
        "<br><b>书证出处</b>：<a href='../数据/卷首题署对校.md' target='_blank'>卷首题署对校</a> · "
        "<a href='../数据/影印原书/四部丛刊影印俞桥本_金匮要略方论_第1册_ZJLib.pdf' target='_blank'>影印第1册</a> · "
        "<a href='../数据/影印原书/四部丛刊影印俞桥本_金匮要略方论_第2册_ZJLib.pdf' target='_blank'>第2册</a> · "
        "<a href='../数据/书影索引.md' target='_blank'>书影索引</a>"
        "<br><span class='weak'>著录差异：医统全文提要自称「四部丛刊景印明古今医统正脉本」，"
        "而 PDF 交付著录为「四部丛刊影印俞桥本」。本包如实并列，不替派包方裁定。</span></div>"
    )
    return {
        "id": f"PUA-{ord(c):X}",
        "tag": f"{n:02d} · {code} · 题署 {cnt_all[c]} 处",
        "listLabel": f"{n:02d}",
        "hint": "这两个方框在卷首题署里，<b>不在正文条目内</b>，没有条文上下文可推。"
                "请对照下面俞桥本四部丛刊同一行题署（繁/简两处），判出本字填在下框。",
        "stem": "",
        "bodyLabel": "待判码位与题署书证",
        "body": body, "bodyHtml": True,
        "ref": loc, "refHtml": True,
        "text": True, "oneChar": True,
        "placeholder": "填你判定的本字（一个汉字）",
        "options": [
            {"v": "定", "label": "能定（已在上框填字）"},
            {"v": "?", "label": "判不了，需查影印"},
        ],
    }


# ── 4. 主入口 ───────────────────────────────────────────────────────────
def build_h02_config():
    pua_map = derive_map()
    # 全文 md（含卷首题署、卷末注记）的口径，用于回填验收「私用区计数归零」。
    raw_all = open(os.path.join(H02, "数据", "医统正脉1601_全文.md"), encoding="utf-8").read()
    cnt_all = collections.Counter(c for c in raw_all if is_pua(c))
    # 题署里另外 2 个码位不在 A4 双栏表内，靠俞桥本四部丛刊题署对校。
    for c, ch in TITLE_PUA.items():
        pua_map[c] = {"char": ch, "votes": [(ch, cnt_all[c])],
                      "hit": cnt_all[c], "src": "卷首题署对校"}
    segs, ev = title_evidence(pua_map)
    write_title_evidence(segs, ev, pua_map)

    pkg, cnt, occ, _pian_of, _page_of = collect_occurrences(pua_map)
    viewer = jload(VIEWER)
    viewer_by_n = {x["n"]: x for x in viewer["items"]}
    total_body = sum(cnt.values())      # 465 条分段正文：13 码位 / 1419 处
    total_all = sum(cnt_all.values())   # 全文含题署：15 码位 / 1436 处

    # 影印页图（按篇序号就近取一张）
    scans = []
    sd = os.path.join(H02, "数据", "书影")
    if os.path.isdir(sd):
        scans = sorted(f for f in os.listdir(sd) if f.lower().endswith(".png"))

    items = []
    order = sorted((c for c in pua_map if c in cnt), key=lambda c: -cnt[c])
    for n, c in enumerate(order, 1):
        info = pua_map[c]
        ch, votes, hit = info["char"], info["votes"], info["hit"]
        code = f"U+{ord(c):05X}"
        exs = pick_examples(occ[c], 4)
        proofs = "".join(build_proof_html(e, pua_map, viewer_by_n, c, ch) for e in exs)
        nos = "、".join(str(e["no"]) for e in exs)
        pians = sorted({e["pian"] for e in exs})

        glyph = (
            "<div class='glyphbox'>"
            "<div class='glyphwrap'>"
            "<div class='glyphbig'>?</div>"
            "<div class='glyphcap'>待判码位</div>"
            "</div>"
            "<div class='evi'>"
            f"<b>{esc(code)}</b> 在 465 条正文里出现 <b>{cnt[c]}</b> 处。"
            "<br>下面每组书证把同一句在 <b>医统本 / 赵开美本 / 俞桥本 / 人卫本 / 邓珍本</b> "
            "五部书里的写法并排给你，医统本的待判处标成 <b class='qmark'>【?】</b>。"
            "<br><span class='weak'>请自己对齐五版同句，判出 【?】 处是哪个字，填到下方输入框。"
            "本包不给答案。</span>"
            "</div></div>"
        )
        body = (glyph + "<div class='pftitle'>同句书证 · 五版并排（自己对齐 【?】 位置判读）</div>"
                + f"<div class='proofs'>{proofs}</div>")

        loc = (
            "<div class='loc'>"
            f"<b>原书定位</b>：{esc('、'.join(pians))} · 条 {esc(nos)} · "
            f"医统版本包段页 {esc('、'.join(str(e['page']) for e in exs))}。"
            f"<br><b>待判码位</b>：<code>{esc(code)}</code>"
            f"（字符原样：<span class='pua'>{esc(c)}</span>；浏览器无字形属正常，回填按此码位替换）。"
            "<br><b>可翻的原书</b>："
            "<a href='../数据/裁定表_A4_医统.md' target='_blank'>A4 双栏核定表（骨架原文／医统原文并排）</a> · "
            "<a href='../数据/医统正脉1601_全文.md' target='_blank'>医统本全文·原件</a> · "
            "<a href='../数据/各版原文/01_赵开美本1599.md' target='_blank'>赵开美本</a> · "
            "<a href='../数据/各版原文/04_俞桥本四部丛刊.md' target='_blank'>俞桥本</a> · "
            "<a href='../数据/各版原文/05_人卫排印本1964.md' target='_blank'>人卫本</a> · "
            "<a href='../数据/各版原文/02_邓珍本1340.md' target='_blank'>邓珍本</a>"
            "<br><b>影印书影</b>："
            "<a href='../数据/影印原书/四部丛刊影印俞桥本_金匮要略方论_第1册_ZJLib.pdf' target='_blank'>俞桥本影印·第1册</a> · "
            "<a href='../数据/影印原书/四部丛刊影印俞桥本_金匮要略方论_第2册_ZJLib.pdf' target='_blank'>第2册</a> · "
            "<a href='../数据/书影索引.md' target='_blank'>书影索引</a>"
            "<br><span class='weak'>注：库内影印按原交付著录为<b>俞桥本四部丛刊</b>；"
            "医统全文提要另有不同说法，著录差异见书影索引与卷首题署对校，"
            "本包不替派包方裁定。</span>"
            "</div>"
        )
        if scans:
            # 就近取一张同篇页样张，可点开看刻本行款
            pidx = 1
            for k, p in enumerate(pkg["篇目"], 1):
                if p["名"] in pians:
                    pidx = k
                    break
            numbered = [(f, int(m.group(1))) for f in scans
                        for m in [re.match(r"篇(\d+)_", f)] if m]
            exact = [f for f, k in numbered if k == pidx]
            cand = exact or ([min(numbered, key=lambda x: abs(x[1] - pidx))[0]]
                             if numbered else [])
            if cand:
                rel = html.escape("../数据/书影/" + cand[0], quote=True)
                loc += (f"<details class='scanbox'><summary>看这一篇的影印页样张（{esc(cand[0])}）</summary>"
                        f"<a href='{rel}' target='_blank'><img class='scan' src='{rel}' "
                        f"alt='{esc(cand[0])}' loading='lazy'></a>"
                        "<div class='weak'>俞桥本四部丛刊影印页，供看刻本行款与字形；非医统本原件，"
                        "也不保证正落在这一句上。</div></details>")

        items.append({
            "id": f"PUA-{ord(c):X}",
            "tag": f"{n:02d} · {code} · {cnt[c]} 处",
            "listLabel": f"{n:02d}",
            "hint": (f"这个码位在正文出现 {cnt[c]} 处。下面把同一句在 <b>5 部书</b>里的写法并排给你，"
                     "医统本待判处标 【?】，其余四版是原文照录（含标点、繁简差异）。"
                     "<b>请自己对齐判出本字，填在下框</b>；判不了就选「判不了」，别猜。"),
            "stem": "",
            "bodyLabel": "待判码位与五版同句书证",
            "body": body,
            "bodyHtml": True,
            "ref": loc,
            "refHtml": True,
            "text": True,
            "oneChar": True,
            "placeholder": "填你判定的本字（一个汉字）",
            "options": [
                {"v": "定", "label": "能定（已在上框填字）"},
                {"v": "?", "label": "判不了，需查影印"},
            ],
        })

    for c, ch in TITLE_PUA.items():
        items.append(build_title_item(c, ch, len(items) + 1, cnt_all, segs, ev, pua_map))

    intro = (
        f"医统正脉本电子文本里有 <b>{len(pua_map)} 个 Unicode 私用区码位</b>，浏览器显示为方框，"
        f"全文合计 <b>{total_all} 处</b>（465 条分段正文内 {total_body} 处，"
        f"另 {total_all - total_body} 处在卷首题署等处）。"
        "旧版题面只给码位和一串带方框的上下文，人根本没法判。"
        "<br><b>这是派发包，本包不给答案。</b>这一版只把「对应的书本」配齐："
        "每题把同一句在 <b>五部书</b>里的原文并排（医统本待判处标 【?】），"
        "另给 A4 双栏核定表、五版全书原文、影印 PDF 两册与页图；"
        "只在卷首题署出现的 2 个码位另配俞桥本题署对校。"
        "<br>你要做的是：<b>自己对齐书证 → 在下框填一个本字 → 点「能定」</b>；"
        "判不了就选「判不了」并在备注写原因，别猜。填完点右上导出 JSON 交回。"
        "<div class='books'><b>包内自带的书</b>："
        "<a href='../数据/裁定表_A4_医统.md' target='_blank'>A4 双栏核定表（骨架／医统原文并排）</a> · "
        "<a href='../数据/医统正脉1601_全文.md' target='_blank'>医统本全文·原件</a> · "
        "<a href='../数据/卷首题署对校.md' target='_blank'>卷首题署对校</a> · "
        "<a href='../数据/各版原文/' target='_blank'>五版原文（数据/各版原文/）</a> · "
        "<a href='../数据/影印原书/' target='_blank'>俞桥本影印 PDF 两册</a> · "
        "<a href='../数据/书影/' target='_blank'>影印页图 10 张</a> · "
        "<a href='../数据/书影索引.md' target='_blank'>书影索引</a>。"
        "<br><span class='weak'>版本归属：影印 PDF 与页图按原交付著录为<b>俞桥本四部丛刊</b>；"
        "医统全文提要另有「四部丛刊景印明古今医统正脉本」之说，两者著录差异见"
        "<a href='../数据/卷首题署对校.md' target='_blank'>卷首题署对校</a>，本包不替派包方裁定。</span></div>"
    )

    cfg = {
        "key": "H02-yitong-pua-v3",
        "title": f"医统正脉本 · 私用区缺字判定（{len(items)} 码位 / {total_all} 处）",
        "subtitle": f"人工包 H02 · 配五版书证与原书影印 · 由接包人判定，共 {len(items)} 题",
        "export_name": "H02_医统缺字_交付.json",
        "text_label": "本字（填你判定的一个汉字）",
        "intro": intro,
        "items": items,
    }
    return cfg, pua_map, cnt


def write_side_assets(pua_map):
    """引擎推字结果只写进【引擎侧参考目录】，绝不进派发包。

    派发包给接包人的只有原始材料与书证；答案留在我方，用于交回后比对验收。
    """
    dd = os.path.join(H02, "数据")
    raw = open(os.path.join(dd, "医统正脉1601_全文.md"), encoding="utf-8").read()
    cnt_all = collections.Counter(c for c in raw if is_pua(c))
    fixed = "".join(pua_map.get(c, {}).get("char", c) if is_pua(c) else c for c in raw)
    assert not any(is_pua(c) for c in fixed), "仍有未释私用区码位，替换后计数不会归零"

    ref = os.path.join(B, "02_engine", "H02_参考")
    os.makedirs(ref, exist_ok=True)
    pairs = sorted(pua_map.items(), key=lambda x: ord(x[0]))
    payload = {
        "说明": "引擎推定值，未经人工确认；仅供派包方交回后比对验收。禁止放进派发包，禁止当作标准答案发给接包人。",
        "依据": "A4 双栏逐字对齐（正文 13 码位）+ 俞桥本四部丛刊卷首题署对校（2 码位）",
        "全文码位数": len(cnt_all), "全文出现": sum(cnt_all.values()),
        "映射": {f"U+{ord(c):05X}": v["char"] for c, v in pairs},
        "逐码位": [
            {"码位": f"U+{ord(c):05X}", "推定本字": v["char"], "全文出现": cnt_all[c],
             "对齐命中": v["hit"],
             "依据": "题署对校" if v.get("src") == "卷首题署对校" else "A4 双栏",
             "候选票数": [{"字": k, "票数": n} for k, n in v["votes"]]}
            for c, v in pairs
        ],
    }
    json.dump(payload, open(os.path.join(ref, "H02_引擎参考_未确认.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    lines = [
        "# H02 · 引擎参考（未确认，不进派发包）",
        "",
        "> 本目录是**派包方内部验收参考**，不随 H02 分发。",
        "> 接包人交回 JSON 后，用这里的映射比对结论、跑全库替换、验私用区计数是否归零。",
        "> 若人工结论与引擎推定不一致，以人工结论为准并回查书证。",
        "",
        "| 码位 | 推定本字 | 全文出现 | 对齐命中 | 依据 |",
        "|---|---|---|---|---|",
    ]
    for c, v in pairs:
        basis = "题署对校" if v.get("src") == "卷首题署对校" else "A4 双栏"
        lines.append(f"| U+{ord(c):05X} | **{v['char']}** | {cnt_all[c]} | {v['hit']} | {basis} |")
    lines += [
        "",
        f"全文 {sum(cnt_all.values())} 处 / {len(cnt_all)} 码位；465 条分段正文内 1419 处 / 13 码位。",
        "",
        "```python",
        "PUA_MAP = {" + ", ".join(f'chr(0x{ord(c):X}): "{v["char"]}"' for c, v in pairs) + "}",
        "```",
        "",
    ]
    open(os.path.join(ref, "释字参考_未确认.md"), "w", encoding="utf-8").write("\n".join(lines))
    open(os.path.join(ref, "医统全文_引擎释字_未确认.md"), "w", encoding="utf-8").write(
        "> 引擎释字版，仅用于验证替换后私用区计数为 0；不进派发包。\n\n" + fixed)

    # 把上一版误放进派发包的答案文件清掉
    for name in ("医统正脉1601_全文_已释字.md", "释字对照表.md"):
        p = os.path.join(dd, name)
        if os.path.exists(p):
            os.remove(p)
            print("  移出派发包（改存引擎侧）:", name)


def write_scan_index():
    """书影索引：把篇 / 条号 / 影印册页锚点对应起来，方便接包人真去翻书。"""
    dd = os.path.join(H02, "数据")
    pkg = jload(os.path.join(PKG, "版本包_医统正脉1601", "交付", "版本包.json"))
    by_pian = {}
    for e in pkg["条目"]:
        by_pian.setdefault(e.get("篇", ""), []).append(e["条号"])
    order = [p["名"] for p in pkg["篇目"]]
    sd = os.path.join(dd, "书影")
    scans = sorted(f for f in os.listdir(sd) if f.lower().endswith(".png")) if os.path.isdir(sd) else []
    anchors = {}
    for f in scans:
        m = re.match(r"篇(\d+)_p(\d+)_册(\d+)", f)
        if m:
            anchors[int(m.group(1))] = (int(m.group(3)), int(m.group(2)), f)

    lines = [
        "# H02 · 原书与书影索引",
        "",
        "> **版本归属（先读这条）**",
        "> 本包内的影印 PDF 与页图，按原交付著录是 **《金匮要略方论》俞桥本／四部丛刊影印**；",
        "> 但医统全文 md 的提要自称「四部丛刊景印明古今医统正脉本」，两者著录存在出入，",
        "> 详见 `卷首题署对校.md`。本包不替派包方裁定这两册 PDF 的实际版本归属，",
        "> **若要以医统本影印原件为据，请先核实**。",
        "> 影印在此只作字体、行款、异体字与题署对校的旁证。",
        "> **本包不给答案**，本字由接包人按书证自行判定；",
        "> 若仍要翻影印核对，按下面的篇→册页锚点翻。",
        "",
        "## 一、包内自带的书",
        "",
        "| 类别 | 文件 | 说明 |",
        "|---|---|---|",
        "| 医统本原文（原件） | `数据/医统正脉1601_全文.md` | 含私用区方框，一字未动 |",
        "| 双栏核定表 | `数据/裁定表_A4_医统.md` | 骨架原文／医统本原文并排，最直接的逐字对读材料 |",
        "| 题署对校 | `数据/卷首题署对校.md` | 2 个只在卷首题署出现的码位，两边题署原文并列（无答案） |",
        "| 五版原文 | `数据/各版原文/*.md` | 赵开美1599／邓珍1340／医统1601／俞桥四部丛刊／人卫1964 |",
        "| 影印原书 | `数据/影印原书/*.pdf` | 四部丛刊影印，第 1、2 册 |",
        "| 影印页图 | `数据/书影/*.png` | 10 张，原交付「体例行与著录」凭据图 |",
        "",
        "## 二、篇 → 条号 → 影印页锚点",
        "",
        "题面里每条都写了「条 N」和篇名；用这张表找到该篇在影印本里的已知页锚点，",
        "再前后翻即可。页锚点是原交付抽样拍摄的篇首/篇末页，**不保证正落在这一句上**。",
        "",
        "| 篇序 | 篇名 | 骨架条号 | 影印册/页锚点 | 页图 |",
        "|---|---|---|---|---|",
    ]
    for k, name in enumerate(order, 1):
        ns = by_pian.get(name, [])
        rng = f"{min(ns)}–{max(ns)}" if ns else "—"
        a = anchors.get(k)
        if a:
            ap = f"册{a[0]} p{a[1]}"
            af = f"`{a[2]}`"
        else:
            # 就近给一个已知锚点
            near = min(anchors, key=lambda x: abs(x - k)) if anchors else None
            ap = f"就近：册{anchors[near][0]} p{anchors[near][1]}（篇{near:02d}）" if near else "—"
            af = "—"
        lines.append(f"| {k:02d} | {name} | {rng} | {ap} | {af} |")
    lines += [
        "",
        "## 三、为什么不给医统本影印原件",
        "",
        "27 号结构交付与本地底本库中，医统正脉 1601 只有「影印底本之电子文本转录」，",
        "没有单独确认过的扫描页图；`金匮要略/交付/task_2_1/底本/` 里两册 PDF 的交付著录为俞桥本。",
        "医统全文提要却写着「四部丛刊景印明古今医统正脉本」，著录有出入（见 `卷首题署对校.md`）。",
        "因此本包不虚构「医统本影印页图」，只把确实存在的书放进来、把差异写清楚。",
        "",
        "若需要医统本影印原件，请向派包方索取（明·万历二十九年周氏《古今医统正脉全书》本",
        "《金匮要略方论》卷上/中/下扫描件）；拿到后可按本索引的篇→条号体系补页锚点。",
        "",
        "## 四、翻书时看什么",
        "",
        "1. 先在核定台里看**五版同句并排书证**，自己对齐医统本 【?】 位置，判出本字。",
        "2. 逐字对读 `裁定表_A4_医统.md` 的「骨架原文／本版原文」双栏，核对同一句。",
        "3. 存疑时翻影印页图看刻工字形与异体；简体排印本是转写，不是异文。",
        "4. 判不了就选「判不了」并写原因，**不要猜**。",
        "",
    ]
    open(os.path.join(dd, "书影索引.md"), "w", encoding="utf-8").write("\n".join(lines))


def main():
    cfg, m, cnt = build_h02_config()
    p = os.path.join(H02, "工具", "H02_配置.json")
    json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"H02 配置 {len(cfg['items'])} 题 -> {p}")
    write_side_assets(m)
    write_scan_index()
    print("已写出 全文_已释字.md / 释字对照表.md / 卷首题署对校.md / 书影索引.md")
    for it in cfg["items"]:
        print(" ", it["tag"])


if __name__ == "__main__":
    main()
