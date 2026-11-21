#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 36_派发包_剩余工序 下的三个「核定台」配置（H01 / H02 / L01）。

配置只是 HTML 的输入，真正的题面数据从总装产出与版本包里取，不另造。
"""
import collections
import json
import os
import re
import sys

B = "/Users/levi/Documents/医/共创/伤寒杂病论"
OUT = os.path.join(B, "36_派发包_剩余工序")
JG = os.path.join(B, "35_总装产出_金匮_v0.1.0")
PKG = os.path.join(B, "04_packages", "版本包_金匮基线_v2")
SK = os.path.join(B, "01_skeleton", "金匮条级骨架.json")


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def is_pua(c):
    o = ord(c)
    return (0xE000 <= o <= 0xF8FF) or (0xF0000 <= o <= 0xFFFFD) or (0x100000 <= o <= 0x10FFFD)


# ── H01 待核校 115 条 ───────────────────────────────────────────────
# 每格附「翻原书」链接：包内自带的影印册、该篇页图、本版全书、段级核定表。
# 只给材料与定位，不给结论。锚点由 attach_books.py 生成。
ENG_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ANCHORS = os.path.join(ENG_DIR, "book_anchors.json")

VER_MD = {
    "赵开美本1599": "01_赵开美本1599.md",
    "邓珍本1340": "02_邓珍本1340.md",
    "医统正脉1601": "03_医统正脉1601.md",
    "俞桥本四部丛刊": "04_俞桥本四部丛刊.md",
    "人卫排印本1964": "05_人卫排印本1964.md",
}
VER_RULE = {
    "俞桥本四部丛刊": "逐条核定表_2_5_A3.md",
    "医统正脉1601": "逐条核定表_2_5_A4.md",
}


def _book_links(no, ver, anchors):
    a = next((x for x in anchors if x["起"] <= no <= x["止"]), anchors[0])
    pdf = f"四部丛刊影印俞桥本_金匮要略方论_第{a['册']}册_ZJLib.pdf"
    links = [
        f"<a href='../数据/影印原书/{html_esc(pdf)}' target='_blank'>"
        f"影印第{a['册']}册（篇{a['篇序']:02d} 锚点 {html_esc(a['锚点'])}）</a>",
    ]
    if a["页图"]:
        links.append(f"<a href='../数据/书影/{html_esc(a['页图'])}' target='_blank'>该篇页图</a>")
    md = VER_MD.get(ver)
    if md:
        links.append(f"<a href='../数据/各版原文/{html_esc(md)}' target='_blank'>本版全书原文</a>")
    rule = VER_RULE.get(ver)
    if rule:
        links.append(f"<a href='../数据/段级核定表/{html_esc(rule)}' target='_blank'>段级双栏核定表</a>")
    else:
        links.append("<a href='../数据/段级核定表/A10_条级参照系.json' target='_blank'>条级参照系</a>")
    for juan in ("卷上", "卷中", "卷下"):
        links.append(f"<a href='../数据/原书全文_维基文库/"
                     f"维基文库_四部丛刊本_金匮要略方论_{juan}.htm' target='_blank'>俞桥本{juan}</a>")
    links.append("<a href='../数据/原书索引.md' target='_blank'>篇→册页索引</a>")
    return ("<div class='loc' style='margin-top:8px;border-top:1px dashed #d8d0c0;"
            "padding-top:8px'><b>翻原书（包内自带，不必另找）</b>：" + " · ".join(links)
            + "<br><span style='color:#8a8272'>库内影印为俞桥本四部丛刊（同书异版）；"
              "本版若无影印原件，以本版全书原文＋核定表为准。</span></div>")


def h01():
    d = jload(os.path.join(JG, "viewer_data.json"))
    by_n = {it["n"]: it for it in d["items"]}
    anchors = jload(BOOK_ANCHORS) if os.path.exists(BOOK_ANCHORS) else []
    review = d["review"]
    # review 里有「同条 × 同版」的多段登记（共 6 组），旧版 id 只用 条号+版本，
    # 结果 115 格只有 104 个唯一 id：核定台状态串题、导出 JSON 必被自检拦下。
    # 重复组按段页 pN 展开 id，并在标签里写明第 k/N 格。
    total = collections.Counter(f"T{r['n']:04d}-{r['v']}" for r in review)
    seen = collections.Counter()
    items = []
    for r in review:
        it = by_n.get(r["n"], {})
        cell = (it.get("v") or {}).get(r["v"], {})
        base = f"T{r['n']:04d}-{r['v']}"
        seen[base] += 1
        k, n_all = seen[base], total[base]
        multi = n_all > 1
        tag = f"条 {r['n']} · {r['v']}" + (f" · {k}/{n_all}（p{r.get('pg','')}）" if multi else "")
        ref = (f"骨架条 {r['n']}，篇：{it.get('pian','')}。"
               f"引擎置信：{cell.get('cf','')}。若判「无」，请留意是否只是标点/异体字差异。")
        if anchors:
            ref = html_esc(ref) + _book_links(r["n"], r["v"], anchors)
        items.append({
            "id": f"{base}#p{r.get('pg','0')}" if multi else base,
            "tag": tag,
            "hint": f"{r['v']} · 引擎判 {r.get('st','')} · p{r.get('pg','')}。"
                    f"请对照骨架原文，判这一格是「确有（文字可对上）」还是「本版无／仅残句」。"
                    + (f"<b>同条同版共 {n_all} 格（不同段页），这是第 {k} 格，请按本格文字单独判。</b>"
                       if multi else ""),
            "stem": it.get("s", ""),
            "bodyLabel": r["v"] + "（引擎取到的文字）",
            "body": cell.get("t") or cell.get("d") or r.get("t") or "",
            "ref": ref,
            "refHtml": bool(anchors),
            "options": [
                {"v": "有", "label": "确有（文字对得上）"},
                {"v": "无", "label": "本版无此条", "warn": True},
                {"v": "残", "label": "仅残句/错行", "warn": True},
                {"v": "?", "label": "判不了，留给人复核"},
            ],
        })
    return {
        "key": "H01-jg-review",
        "title": "金匮 · 待核校逐条核定（115 格）",
        "subtitle": "人工包 H01 · 4 版 × 低置信/残缺格，逐格定性",
        "export_name": "H01_待核校核定_交付.json",
        "intro": "左侧是本批 115 格（条 × 版本）。每格给出<b>骨架原文</b>与<b>引擎取到的文字</b>，"
                 "你只需判三件事：文字对得上（确有）／本版没有／只残了一句。"
                 "<b>判定要用的书全在包里</b>：每格「依据」下面有翻原书的链接（影印册、该篇页图、"
                 "本版全书、段级核定表），按条号查 `数据/原书索引.md` 即可定位。"
                 "判完点右上「导出交付 JSON」交回。<b>结果自动存在本机浏览器</b>，中途关页面不会丢。",
        "items": items,
    }


# ── H02 医统私用区缺字 13 个（v2 书证版）────────────────────────────
# 旧题面只给码位 + 带方框的上下文，人认不出来；现改由 A4 双栏逐字对齐
# 推出本字，题面给「可读本字 + 五版同句并排书证」。实现见 h02_proofs.py。
def h02():
    from h02_proofs import build_h02_config, write_side_assets, write_scan_index
    cfg, m, cnt = build_h02_config()
    write_side_assets(m)
    write_scan_index()
    return cfg


def html_esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── L01 邓珍 150 条无独立文 ─────────────────────────────────────────
def l01():
    sk = {x["no"]: x for x in jload(SK)["条目"]}
    p = jload(os.path.join(PKG, "版本包_邓珍本1340", "交付", "版本包.json"))
    md = {}
    raw = open(os.path.join(B, "05_texts", "版本正文_金匮", "02_邓珍本1340.md"),
               encoding="utf-8").read()
    UND = "（本版此条未检出）"
    blocks = re.split(r"<!--\s*p(\d+)\s*-->", raw)[1:]
    for i in range(0, len(blocks) - 1, 2):
        no = int(blocks[i])
        body = re.sub(r"^##[^\n]*\n", "", blocks[i + 1].strip()).strip()
        if body and body != UND:
            md[no] = body
    slots = sorted(md)
    items = []
    for e in p["条目"]:
        if e["状态"] != "无":
            continue
        no = e["条号"]
        first = (sk[no].get("句") or [{}])[0].get("源no") or 0
        prev = [s for s in slots if s < first]
        owner = prev[-1] if prev else None
        nxt = [s for s in slots if s > first]
        ctx = ""
        if owner:
            ctx += f"【前一条实文段 no{owner}】\n{md[owner][:700]}\n\n"
        if nxt:
            ctx += f"【后一条实文段 no{nxt[0]}】\n{md[nxt[0]][:400]}"
        pri = "未核实" if "未核实" in (e.get("原因") or "") else \
              ("并入前条" if "并入" in (e.get("原因") or "") else "裁定无")
        items.append({
            "id": f"D{no:04d}",
            "tag": f"条 {no} · {pri}",
            "hint": f"引擎结论：{e.get('原因','')}。请读下面邓珍原文，判断这条在邓珍里"
                    f"<b>有没有独立的一段文字</b>；若有，请把那段抄进下方的框（可只抄起止即可）。",
            "stem": sk[no]["原文"],
            "bodyLabel": "邓珍本原文（前后邻段）",
            "body": ctx or "（附近无实文段）",
            "ref": e.get("证据", ""),
            "text": True,
            "placeholder": "若判「有」：把邓珍此条原文贴这里（一字不改，繁体/简体照录）",
            "options": [
                {"v": "并入", "label": "确实并入前条（本版未单列）"},
                {"v": "有", "label": "有独立文字（已贴在上框）"},
                {"v": "无", "label": "本版确无此条", "warn": True},
                {"v": "?", "label": "判不了"},
            ],
        })
    items.sort(key=lambda x: (0 if "未核实" in x["tag"] else 1, x["id"]))
    return {
        "key": "L01-dengzhen-split",
        "title": "邓珍本 · 150 条无独立文的复核与重切",
        "subtitle": "LLM/人工包 L01 · 邓珍全书 322 条 vs 骨架 465 条，分条更粗",
        "export_name": "L01_邓珍重切条_交付.json",
        "text_label": "邓珍此条原文（判「有」时必填）",
        "intro": "邓珍本全书 322 条，比骨架少 143 条，所以很多骨架条在邓珍里<b>并进了相邻一段</b>。"
                 "引擎已核出 104 条确在前条文字里（覆盖率已算），本批把 150 条全部列出，"
                 "<b>前 10 条是连归属都核实不出的</b>，请优先看。判「有」时必须贴原文，"
                 "不要只写「有」——回来要能直接入库。",
        "items": items,
    }


def main():
    for name, fn in [("H01", h01), ("H02", h02), ("L01", l01)]:
        cfg = fn()
        d = os.path.join(OUT, {"H01": "H01_待核校核定_人工",
                               "H02": "H02_医统缺字识别_人工",
                               "L01": "L01_邓珍重切条_LLM"}[name], "工具")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{name}_配置.json")
        json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(name, len(cfg["items"]), "题", p)


if __name__ == "__main__":
    main()
