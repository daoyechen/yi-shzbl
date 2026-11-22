#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登记「版本独有内容」缺口 —— 金匮「果實菜穀禁忌」篇。

背景（H03 回传验收时暴露）：
  骨架以赵开美本为准，而赵开美本本身只有 24 篇、无「果實菜穀禁忌」一篇。
  故该篇没有骨架槽位；`indep`（版本独有）又从未登记过它，于是全库查不到。
  实际状况：
    · 邓珍本1340 —— 渲染件 `版本正文_金匮/02_邓珍本1340.md` 段1439 存有该篇**果实部**
      （果子类 15 则 + 「食诸果中毒」方，259 字，原文自然收尾）；
      **菜穀部未收**（菜、穀、鹽、醬等）。这一段在版本包里被丢掉（条427 取的是「大豆濃煮汁」）。
    · 俞桥本四部丛刊 —— 库内只有影印 2 册（128+142 页，纯图像无文本层），未转录。
    · 人卫排印本1964 —— 转录件缺此篇，且无影印原件可补。
    · 医统正脉1601、赵开美本1599 —— 本无此篇，不登记。

本脚本做的事：
  1. 从渲染件精确取出邓珍那 259 字（不手抄，避免抄错）。
  2. 以「殘篇」名义写入 `indep["邓珍本1340"]`，**正文原样保留，缺失处只标注不补字**。
  3. 俞桥、人卫各登记一条「未收」占位，写明原因与补件条件 —— 免得后人以为「查无 = 本版没有」。
  4. 幂等：重复运行不会重复写入（按 id 判重）。

用法：
  python3 register_jg_gap.py --out 50_data/52_l1_assembly/jingui
  python3 register_jg_gap.py --out ... --dry
"""
import argparse
import json
import os
import re

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(B, "05_texts", "版本正文_金匮", "02_邓珍本1340.md")


def extract_dz_fragment():
    """从邓珍渲染件段1439 取出果實菜穀篇残段（原样，不改字）。"""
    lines = open(RENDER, encoding="utf-8").read().split("\n")
    start = None
    for i, l in enumerate(lines):
        if l.startswith("## 条 1439 "):
            start = i
            break
    if start is None:
        raise SystemExit("未找到「## 条 1439」——渲染件结构变了，先核对再跑")
    seg = []
    for l in lines[start + 1:]:
        if l.startswith("<!-- p"):
            break
        seg.append(l)
    txt = "\n".join(seg).strip()
    if "果子生食" not in txt:
        raise SystemExit(f"段1439 内容不含「果子生食」，实际为：{txt[:60]!r}")
    return txt


def build_entries():
    frag = extract_dz_fragment()
    dz = {
        "id": "邓珍-独-果實菜穀禁忌第二十五（殘篇）",
        "pg": "",
        "t": ("〔殘篇·僅存果實部〕「果實菜穀禁忌第二十五」"
              "——鄧珍本有此篇（第25篇），趙開美本骨架無此篇槽位，故不入主表。\n"
              f"{frag}\n"
              "〔以下菜穀部（菜類、穀類、鹽醬等）本庫未收，原件待補；此處不臆補一字〕"),
    }
    yq = {
        "id": "俞橋-独-果實菜穀禁忌（未收）",
        "pg": "",
        "t": ("〔未收〕俞橋本目錄有此篇（`缺篇對照.md` 記「菓實菜榖禁忌 ✓」），"
              "但本庫只有影印 2 冊（128+142 頁，純圖像無文本層），尚未轉錄。\n"
              "補件條件：對四部叢刊影印本人工目視轉錄（項目規矩不 OCR、不臆造）。"),
    }
    rw = {
        "id": "人衛-独-果實菜穀禁忌（未收·無原件）",
        "pg": "",
        "t": ("〔未收〕人衛排印本 `缺篇對照.md` 記此篇作「果實菜穀禁忌第二十四」，"
              "但本庫轉錄件缺此篇，且無該版影印原件可補。\n"
              "補件條件：先取得人衛 1964 排印本原件或掃描，方可轉錄。"),
    }
    return {"邓珍本1340": dz, "俞桥本四部丛刊": yq, "人卫排印本1964": rw}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(B, "50_data", "52_l1_assembly", "jingui"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    vp = os.path.join(a.out, "viewer_data.json")
    vd = json.load(open(vp, encoding="utf-8"))
    ents = build_entries()

    if not isinstance(vd.get("indep"), dict):
        vd["indep"] = {}

    added = []
    for ver, ent in ents.items():
        if ver not in vd["vers"]:
            print(f"  跳过 {ver}：不在本包版本列表")
            continue
        arr = vd["indep"].setdefault(ver, [])
        if any(x.get("id") == ent["id"] for x in arr):
            print(f"  {ver}: 已存在，跳过")
            continue
        arr.insert(0, ent)          # 放最前，便于一眼看到缺口
        added.append((ver, ent["id"]))

    for ver, i in added:
        print(f"  + {ver}：{i}")

    if not added:
        print("  无新增")
        return
    if a.dry:
        print("\n（dry-run，未写入）")
        return

    # 同步 stats.独有 —— 页面的完整性自检会比对 indep 项数与 stats[v].ind，
    # 不更新就会报「独有序 1 ≠ stats 独有 0」（第一次登记时正是被自检抓出来的）。
    for ver in vd["vers"]:
        n = len(vd["indep"].get(ver) or [])
        st = vd.get("stats", {}).get(ver)
        if st is not None:
            st["ind"] = n

    vd.setdefault("build_notes", {})
    if isinstance(vd["build_notes"], dict):
        vd["build_notes"]["indep_缺篇登记"] = (
            "已登记「果實菜穀禁忌」缺口：邓珍存果实部残篇（259 字，菜穀部未收），"
            "俞桥（仅影印未转录）、人卫（转录缺、无原件）各登记未收占位。"
            "骨架按赵开美本 24 篇、无此篇槽位，故不入主表。")
    json.dump(vd, open(vp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 复核
    vd2 = json.load(open(vp, encoding="utf-8"))
    for ver in ents:
        arr = (vd2.get("indep") or {}).get(ver) or []
        hit = [x for x in arr if "果實菜穀" in x.get("id", "") or "果實菜穀" in x.get("t", "")[:40]]
        print(f"  复核 {ver}: indep 共 {len(arr)} 项，本篇命中 {len(hit)}")


if __name__ == "__main__":
    main()