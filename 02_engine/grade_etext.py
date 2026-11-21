#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电子文本准入分级（C5）。

目的不是校对，是**挡住「拿网络错字本当底本」**。
项目规矩：不 OCR、不臆造。所以这里只做机器能判的四项，判不了的写「需人工抽验」。

四个检测项：

1. **编码**：能否以 UTF-8 读通；不能则报实际编码（GBK/Big5），读不通即降级。
2. **HTML 残留**：`</div>` `<br>` `&nbsp;` 等网页抓取痕迹。有则说明是爬来的，不能当底本。
3. **繁简混用**：统计常见简繁对应字的混用率。超阈值打标——不检测就会把繁简差异当版本差异。
4. **底本声明**：首 600 字内是否写「底本／据某本／校注／版本」。
   无声明 = 说不清是哪一版 = 不能当底本。

分级：
  A 可作参照：有底本声明 + 无 HTML 残留 + 繁简一致
  B 需人工抽验：缺一项（有声明但混排，或繁简一致但无声明）
  C 不得当底本：无声明 + 有 HTML 残留或编码读不通

用法：
  python3 grade_etext.py            # 全量，写 JSON
  python3 grade_etext.py --limit 5  # 只跑前 5 件（调试）
"""
import argparse
import csv
import json
import os
import re
import zipfile

B = "/Users/levi/Documents/医/共创/伤寒杂病论"
LIST = os.path.join(B, "39_派发包_待验区/H04_待验书目登记_人工/数据/清单.csv")
OUT = os.path.join(B, "05_版本档案/C5_分级.json")

# 简繁对应样本（高频字，够做比例判断）
PAIRS = [
    ("温", "溫"), ("阴", "陰"), ("阳", "陽"), ("伤", "傷"), ("论", "論"),
    ("脉", "脈"), ("证", "證"), ("汤", "湯"), ("药", "藥"), ("发", "發"),
    ("热", "熱"), ("寒", "寒"), ("虚", "虛"), ("实", "實"), ("气", "氣"),
    ("无", "無"), ("为", "為"), ("这", "這"), ("经", "經"), ("风", "風"),
]
HTML_RE = re.compile(r"</?\s*(div|span|p|br|td|tr|table|a|li|ul|b|em|strong|h\d)\b|&nbsp;|&amp;|&#\d+;", re.I)
SRC_RE = re.compile(r"底本|據.{0,8}本|据.{0,8}本|校注|校點|校点|版本|影印|排印|整理本|參考本|参考本")


def read_text(path):
    """返回 (文本, 编码, 是否成功)"""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".txt":
            raw = open(path, "rb").read()
            for enc in ("utf-8-sig", "utf-8", "gb18030", "big5"):
                try:
                    return raw.decode(enc), enc, True
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", "ignore"), "未知(强制)", False
        if ext == ".epub":
            # epub 的正文本来就是 HTML 容器，必须先剥标签，
            # 否则「含 <div>」会把所有 epub 误判成网页残留。
            with zipfile.ZipFile(path) as z:
                parts = []
                for n in z.namelist():
                    if n.lower().endswith((".html", ".htm", ".xhtml")):
                        h = z.read(n).decode("utf-8", "ignore")
                        h = re.sub(r"<[^>]+>", " ", h)
                        parts.append(h)
                if parts:
                    return "\n".join(parts), "epub(已剥标签)", True
            return "", "epub(无正文)", False
        if ext == ".docx":
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            txt = re.sub(r"<[^>]+>", "", xml)
            return txt, "docx", True
    except Exception:
        return "", "读取失败", False
    return "", "不支持直读", False


def han_mix_ratio(t):
    """简繁混用率：两侧都出现即视为混用，返回 (简字比例, 混用对数)"""
    s = sum(t.count(a) for a, b in PAIRS if a != b)
    tr = sum(t.count(b) for a, b in PAIRS if a != b and a != b)
    both = sum(1 for a, b in PAIRS if a != b and a in t and b in t)
    total = s + tr
    if total == 0:
        return 0.0, 0
    return s / total, both


def grade(path):
    txt, enc, ok = read_text(path)
    rec = {"编码": enc, "可读": ok}
    if not ok and not txt:
        rec.update({"分级": "U", "理由": ["格式不支持直读（需另判或转格式后再评）"]})
        return rec

    head = txt[:600]
    body = txt[:200000]

    has_src = bool(SRC_RE.search(head))
    has_html = bool(HTML_RE.search(body))
    simp_ratio, both_pairs = han_mix_ratio(body)

    reasons = []
    if has_src:
        reasons.append("首段有底本/来源声明")
    else:
        reasons.append("首段无底本声明（说不清是哪一版）")
    if has_html:
        reasons.append("含 HTML/网页残留（爬取痕迹）")
    if both_pairs >= 4:
        reasons.append(f"简繁混用（{both_pairs} 组对应字并存，简字占 {simp_ratio:.0%}）")

    if not ok:
        g = "U"          # 编码读不通，判不了，不硬定 C
    elif not has_src and has_html:
        g = "C"
    elif has_src and not has_html and both_pairs < 4 and ok:
        g = "A"
    else:
        g = "B"

    rec.update({
        "分级": g,
        "理由": reasons,
        "字数": len(body),
        "简繁混用组数": both_pairs,
        "简字比例": round(simp_ratio, 3),
        "有底本声明": has_src,
        "有HTML残留": has_html,
        "首80字": re.sub(r"\s+", " ", head)[:80],
    })
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    rows = list(csv.DictReader(open(LIST, encoding="utf-8-sig")))
    c5 = [r for r in rows if r["类别"] == "C5"]
    if a.limit:
        c5 = c5[:a.limit]

    items = []
    for r in c5:
        rel = r["原相对路径"]
        path = os.path.join(B, rel) if os.path.isabs(rel) else os.path.join(B, rel)
        if not os.path.exists(path):
            p2 = os.path.join(B, "_待验", rel.split("_待验/")[-1])
            path = p2 if os.path.exists(p2) else path
        rec = {"编号": r["编号"], "文件名": r["文件名"], "字节": r["字节"]}
        if not os.path.exists(path):
            rec.update({"分级": "U", "理由": ["原件不在盘，无法评估"]})
        else:
            rec.update(grade(path))
        items.append(rec)

    from collections import Counter
    dist = Counter(x["分级"] for x in items)
    print(f"C5 分级：{len(items)} 件 → {dict(dist)}")

    json.dump({
        "生成": "2026-11-17",
        "口径": "机器可判四项（编码/HTML残留/简繁混用/底本声明）；判不了的写需人工抽验",
        "分级定义": {
            "A": "可作参照：有底本声明 + 无HTML残留 + 繁简一致 + 编码可读",
            "B": "需人工抽验：缺其中一项",
            "C": "不得当底本：无底本声明且有 HTML 残留（爬取件）",
            "U": "无法机器判定：格式不支持直读（PDF/doc/mobi）或编码读不通，需另判",
        },
        "统计": dict(dist),
        "items": items,
    }, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"已写 {OUT}")


if __name__ == "__main__":
    main()