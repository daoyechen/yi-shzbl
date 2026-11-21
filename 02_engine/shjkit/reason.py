#!/usr/bin/env python3
"""「此版无」原因分类 —— 每条判定必须有原文依据,不作推断。

原因枚举(与 spec.json 的 kind 字段一致,不得自创):
  选集未收   —— 该本收录范围自某篇起,前此诸篇不收(证据:该版起始卷次原文)
  本版仅残卷 —— 该版正文自称残卷(证据:篇名含「残卷」)
  原书残损   —— 该版自陈虫蛀残缺(证据:校记/凡例原文)
  体例不同   —— 该版以他种体例编排,条不构成对应单元(证据:该版篇目原文)
  此版无此篇 —— 该版篇目中确无此篇(证据:该版篇目清单)
  暂未匹配   —— 全文检索未见对应文字,留待人工复核
"""
import re

from . import spec as SP


def song_pian_base(pian):
    """宋本篇名去掉「第X」与「合X法」尾巴,取篇名主干用于跨版匹配。"""
    if not pian:
        return ""
    base = re.sub(r"第[一二三四五六七八九十百]+.*$", "", pian).strip()
    base = re.sub(r"\s*合.*$", "", base).strip()
    return base


def norm_pian(s):
    """篇名归一:去书名号、去「第X」、去括注、统一体例用字。"""
    if not s:
        return ""
    s = re.sub(r"^《[^》]*》", "", s)
    s = re.sub(r"第[一二三四五六七八九十百]+.*$", "", s)
    s = re.sub(r"\s*合[一二三四五六七八九十百]+法.*$", "", s)
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = s.replace("**", "").strip()
    s = s.replace("形证治", "脉证并治").replace("病形证", "病脉证并治")
    return s


def version_pians(spec, recs):
    """该版按篇目标记切块。返回 [{name, raw, page, text, key}]。"""
    pats = [re.compile(p) for p in (spec.get("篇目标记") or [])]
    if not pats:
        return []
    blocks, cur = [], None
    for r in recs:
        st = r["raw"]
        head = r["kind"] == "head"
        isp = head and any(p.match(st) for p in pats)
        if not head:
            for p in pats:
                if p.match(st) and len(st) < 40:
                    isp = True
                    break
        if isp:
            nm = norm_pian(st)
            if re.fullmatch(r"卷[一二三四五六七八九十百]*", nm) or nm in ("卷", "卷首前段"):
                if cur is not None:
                    cur["lines"].append(st)
                continue
            if cur is not None:
                blocks.append(cur)
            cur = {"name": nm, "raw": st, "page": r["page"], "lines": []}
            continue
        if cur is not None:
            if r["kind"] in ("text", "yao", "foot"):
                cur["lines"].append(st)
        else:
            cur = {"name": "(卷首前段)", "raw": "(卷首前段)", "page": r["page"], "lines": []}
    if cur is not None:
        blocks.append(cur)
    for b in blocks:
        b["text"] = "\n".join(b["lines"])
        b["key"] = re.sub(r"\s+", "", b["text"])
    return blocks


def classify(no, song_item, spec, v_pians):
    """返回 (原因, 证据)。全部取自原文。"""
    base = song_pian_base(song_item.get("pian") or "")
    cov = spec.get("收录范围") or {}
    kind = cov.get("kind")
    evid = cov.get("evid", "")

    hit = None
    for vn in (v_pians or {}):
        if vn == "(卷首前段)":
            continue
        if vn == base or (vn and base and (vn in base or base in vn)):
            hit = vn
            break

    if hit is None:
        if kind in ("本版仅残卷", "原书残损", "选集未收", "体例不同"):
            return kind, evid
        return "此版无此篇", f"本版所收篇目中无「{base}」;本版篇目清单见本包《体例说明》"

    if kind == "体例不同":
        return "暂未匹配", (f"本版有「{hit}」篇,但该篇以本版体例编排"
                            f"(见本包《体例说明》),未构成与本条对应的单元;待人工复核")
    if kind == "选集未收" and "start" in cov and no < cov["start"]:
        return "选集未收", evid
    if kind in ("原书残损", "本版仅残卷"):
        return kind, evid
    return "暂未匹配", (f"本版「{hit}」篇内未见与本条对应文字;"
                        f"全文检索无果,待人工复核")
