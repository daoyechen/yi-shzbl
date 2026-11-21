#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正文层版本探测：对有文本层的件，读前若干页，抓取序跋/牌记/藏印等版本标识。
这是「同名异刻 / 版本待核」判定的硬证据来源。
"""
import json, os, re, sys
from pypdf import PdfReader

ROOT = "/Users/levi/Documents/医/共创/伤寒杂病论/_待验"
SCAN = "/tmp/shl_scan"

# 版本标识 → (谱系编号, 版本名, 形态描述)
STRONG = ["L9","L1","L3","L4","L5","A4","A2","D1","L10","C1","C2","B2","B3"]

MARKERS = [
    # 桂林古本系（光绪甲午 桂林左氏）
    (r"桂林左盛德|桂林左德|光绪二十年.*甲午|左盛德序", "L9", "桂林古本·光绪甲午左氏刊", "清·光绪二十年甲午(1894)桂林左盛德刊"),
    # 赵开美本（万历二十九年 仲景全书）
    (r"赵开美|万历二十九年|仲景全书.*赵", "L1", "赵开美本·仲景全书", "明·万历二十九年(1601)赵开美刻"),
    # 康平本
    (r"康平三年|康平本|丹波雅忠|和气朝臣", "L3", "康平本", "日本·康平三年(1060)丹波雅忠抄"),
    # 康治本
    (r"康治本|康治二年|康治", "L4", "康治本", "日本·康治二年(1141)"),
    # 高继冲本（淳化本）
    (r"高继冲|淳化.*本|淳化元年", "L5", "高继冲本·淳化本", "宋·淳化元年(990)高继冲刻"),
    # 成无己
    (r"成无己|皇统四年|明善堂", "L6", "成无己注本", "金·皇统四年(1144)"),
    # 医统正脉（吴勉学）
    (r"吴勉学|医统正脉|万历己丑", "A4", "医统正脉本", "明·万历十七年(1589)吴勉学刻"),
    # 邓珍本（元至正）
    (r"邓珍|金匮要略方论.*至正|至正.*金匮要略方论", "A2", "邓珍本", "元·至正十年(1350)"),
    # 和气氏本
    (r"和气保固|和气氏|再钞本|保固", "D1", "和气氏本", "日本·再钞本(1854)"),
    # 伤寒明理论（成无己撰）
    (r"明理论|明理药方论", "D2", "伤寒明理论", "金·成无己"),
    # 敦煌
    (r"敦煌|S\.202|P\.3287", "L10", "敦煌写本", "唐·敦煌写本"),
    # 长沙古本（湘古本）
    (r"何芸樵|长沙古本|湘古本", "C1", "长沙古本", "民国·1932何芸樵手写付印"),
    # 涪陵本
    (r"涪陵", "C2", "涪陵本", "近代"),
    # 邓珍本/脉经/千金/外台/医心方
    (r"王叔和|脉经", "L7", "脉经", "晋·王叔和"),
    (r"孙思邈|备急千金要方|千金要方", "L2", "千金要方", "唐·孙思邈"),
    (r"千金翼方", "B1", "千金翼方", "唐·孙思邈"),
    (r"王焘|外台秘要", "B2", "外台秘要", "唐·王焘"),
    (r"丹波康赖|医心方", "B3", "医心方", "日本·984 丹波康赖"),
]

def scan_pdf(path):
    out = {"markers": [], "head": "", "pages": 0}
    try:
        rd = PdfReader(path)
        out["pages"] = len(rd.pages)
        txt = ""
        for i in range(min(6, len(rd.pages))):
            try:
                txt += (rd.pages[i].extract_text() or "") + "\n"
            except Exception:
                pass
        out["head"] = txt[:4000]
        for pat, code, name, form in MARKERS:
            if re.search(pat, txt[:4000]):
                out["markers"].append([code, name, form if code in STRONG else "WEAK:" + form])
    except Exception as e:
        out["error"] = repr(e)
    return out

def scan_txt(path):
    out = {"markers": [], "head": ""}
    try:
        raw = open(path, "rb").read(6000)
        txt = ""
        for enc in ("utf-8", "gb18030", "big5"):
            try:
                txt = raw.decode(enc); break
            except Exception:
                continue
        out["head"] = txt[:2000]
        for pat, code, name, form in MARKERS:
            if re.search(pat, txt[:2000]):
                out["markers"].append([code, name, form if code in STRONG else "WEAK:" + form])
    except Exception as e:
        out["error"] = repr(e)
    return out

def main():
    rows = json.load(open(f"{SCAN}/classified.json", encoding="utf-8"))
    keep = [r for r in rows if r["verdict"] == "保留"]
    res = {}
    n = 0
    for r in keep:
        rel = r["rel"][2:]
        p = os.path.join(ROOT, rel)
        ext = r["ext"]
        if ext == ".pdf" and r.get("has_text"):
            d = scan_pdf(p)
        elif ext in (".txt", ".doc", ".docx"):
            d = scan_txt(p)
        else:
            continue
        if d.get("markers"):
            res[rel] = d
            n += 1
            print(f'{rel[:76]}')
            for code, name, form in d["markers"]:
                print(f'      → [{code}] {name} :: {form}')
    json.dump(res, open(f"{SCAN}/probe2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n命中版本标识 {n} 件 → {SCAN}/probe2.json")

if __name__ == "__main__":
    main()
