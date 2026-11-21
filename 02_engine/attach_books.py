#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 36_派发包_剩余工序 的六个包统一补齐「原版书籍」资源。

规则（用户反复强调）：每个派发包必须自包含，接包人不必再去别处找书。
H02 已经带了影印原书，其余五个包只有转录 md —— 本脚本按同一套口径补齐。

幂等：目标文件与源字节相同则跳过；不移动、不改写任何已有文件。
同时输出：
  - 每包 数据/原书索引.md（篇 → 条号 → 影印册页锚点 + 版本归属说明）
  - 引擎侧 book_anchors.json（供 mk_pkg_configs.py 的 H01 题面生成翻书链接）
"""
import json
import os
import re
import shutil

B = "/Users/levi/Documents/医/共创/伤寒杂病论"
ROOT = os.path.join(B, "36_派发包_剩余工序")
H02 = os.path.join(ROOT, "H02_医统缺字识别_人工")
ENG = os.path.join(B, "02_engine")

PKGS = [
    "H01_待核校核定_人工",
    "H02_医统缺字识别_人工",
    "M01_异文对齐_机械",
    "M02_方剂抽取_机械",
    "L01_邓珍重切条_LLM",
    "L02_俞桥补录_LLM",
]

SRC_BOOK = os.path.join(B, "金匮要略", "交付", "task_2_1", "底本")
SRC_TEXT = os.path.join(B, "05_texts", "版本正文_金匮")
SRC_RULE = os.path.join(B, "06_rulings")
SRC_PKG = os.path.join(B, "04_packages", "版本包_金匮基线_v2")

RULE_FILES = [
    "逐条核定表_2_5_A3.md",
    "逐条核定表_2_5_A4.md",
    "缺篇对照.md",
    "A10_条级参照系.json",
    "繁简映射.json",
]


def same(a, b):
    if not os.path.exists(b) or os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, "rb") as f1, open(b, "rb") as f2:
        return f1.read() == f2.read()


def ensure(src, dst):
    """复制一份资源；返回是否真的写了。"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if same(src, dst):
        return False
    shutil.copy2(src, dst)
    os.chmod(dst, 0o644)
    return True


def parse_anchors():
    """从 H02 书影索引的表格解析 篇序 → 条号范围 / 册 / 页 / 页图。"""
    p = os.path.join(H02, "数据", "书影索引.md")
    rows = []
    for ln in open(p, encoding="utf-8"):
        if not ln.startswith("|"):
            continue
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) < 5 or not c[0].isdigit():
            continue
        rng = re.findall(r"\d+", c[2])
        if len(rng) < 2:
            continue
        m = re.search(r"册([12])\s*p(\d+)", c[3])
        if not m:
            continue
        png = c[4].strip("`") if c[4] not in ("—", "-", "") else ""
        rows.append({
            "篇序": int(c[0]), "篇名": c[1],
            "起": int(rng[0]), "止": int(rng[1]),
            "册": int(m.group(1)), "页": int(m.group(2)),
            "锚点": c[3], "页图": png,
        })
    # 原交付索引表共 24 行：末行「篇24 · 405–465」已把篇25 的条号一并覆盖，
    # 不另造第 25 行锚点。条号定位用范围匹配，465 以内都能命中。
    assert len(rows) == 24, f"篇目锚点应为 24 行，实得 {len(rows)}"
    return rows


def index_md(pkg, rows):
    extra = ("\n> H02 另有一份 `书影索引.md`（针对医统本题署对校），可与本索引并用。\n"
             if pkg.startswith("H02") else "")
    lines = [
        f"# {pkg} · 原版书籍索引",
        "",
        "> **本包自包含**：判定要用的原书、影印、页图、全书原文都在 `数据/` 里，",
        "> 不需要去网上找版本，也不需要向派包方另要文件。" + extra,
        "",
        "## 一、版本归属（先读这条）",
        "",
        "- 包内两册影印 PDF 与 10 张页图，按原交付著录是 **《金匮要略方论》俞桥本／四部丛刊影印**。",
        "- 医统全文 md 的提要另自称「四部丛刊景印明古今医统正脉本」，与 PDF 著录有出入，",
        "  两者题署差异已在 H02 包的卷首题署对校材料中如实并列，**本包不替派包方裁定**。",
        "- 库内**只有这一套影印原件**。赵开美 1599、邓珍 1340、医统正脉 1601、人卫 1964",
        "  四版没有扫描页图，只有「影印底本之电子文本转录」全文（`各版原文/*.md`），",
        "  以及引擎取数用的版本包、段级核定表。此处不虚构不存在的影印件。",
        "- 影印可作同书异版的字体、行款、异体字旁证；判读以本版全文 + 段级核定表为主。",
        "",
        "## 二、包内自带的书",
        "",
        "| 类别 | 路径 | 内容 |",
        "|---|---|---|",
        "| 影印原书 | `数据/影印原书/*.pdf` | 四部丛刊影印，第 1、2 册 |",
        "| 影印页图 | `数据/书影/*.png` | 10 张，原交付抽样拍摄的篇首/篇末页 |",
        "| 原书电子全文 | `数据/原书全文_维基文库/*.htm` | 俞桥本四部丛刊全本：序、目录、卷上/中/下、全一页 |",
        "| 五版全文 | `数据/各版原文/*.md` | 赵开美1599／邓珍1340／医统1601／俞桥四部丛刊／人卫1964，全书 |",
        "| 段级核定表 | `数据/段级核定表/` | A3 俞桥 / A4 医统双栏逐条核定表、缺篇对照、A10 条级参照系、繁简映射 |",
        "| 版本包 | `数据/各版本包/*.json` | 五版逐条取数结果（引擎判「低置信/残句」的依据） |",
        "| 本索引 | `数据/原书索引.md` | 篇 → 条号 → 影印册页锚点 |",
        "",
        "## 三、篇 → 条号 → 影印册页锚点",
        "",
        "题面里每条都写了「条 N」；用这张表找到该篇在影印本里的已知页锚点，再前后翻。",
        "**页锚点是抽样拍摄的篇首/篇末页，不保证正落在这一句上。**",
        "",
        "| 篇序 | 篇名 | 骨架条号 | 影印册/页锚点 | 页图 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        png_cell = f"`{r['页图']}`" if r["页图"] else "—"
        lines.append(f"| {r['篇序']:02d} | {r['篇名']} | {r['起']}–{r['止']} | "
                     f"{r['锚点']} | {png_cell} |")
    lines += [
        "",
        "## 四、怎么翻",
        "",
        "1. 按题面「条 N」在上表定位篇序与影印册/页，打开对应的 `影印原书/` PDF 翻到该页附近。",
        "2. 该篇若有页图，先点 `书影/` 里的 png 看刻工字形与行款，比翻整册 PDF 快。",
        "3. 逐字对读 `各版原文/<本版>.md` 与 `段级核定表/` 里的双栏核定表。",
        "4. 俞桥系统还可以直接查 `原书全文_维基文库/` 的卷上/卷中/下全文。",
        "5. 影印与转录不一致时，**以包内转录全文与核定表为准**（影印是同书异版旁证）；",
        "   判不了就写「判不了」，不要猜。",
        "",
    ]
    return "\n".join(lines)


def main():
    rows = parse_anchors()
    json.dump(rows, open(os.path.join(ENG, "book_anchors.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 源资源清单：(源路径, 目标相对路径)
    res = []
    for f in sorted(os.listdir(os.path.join(H02, "数据", "影印原书"))):
        if f.lower().endswith(".pdf"):
            res.append((os.path.join(H02, "数据", "影印原书", f), os.path.join("影印原书", f)))
    for f in sorted(os.listdir(os.path.join(H02, "数据", "书影"))):
        if f.lower().endswith(".png"):
            res.append((os.path.join(H02, "数据", "书影", f), os.path.join("书影", f)))
    for f in sorted(os.listdir(SRC_BOOK)):
        if f.lower().endswith(".htm"):
            res.append((os.path.join(SRC_BOOK, f), os.path.join("原书全文_维基文库", f)))
    for f in sorted(os.listdir(SRC_TEXT)):
        if f.lower().endswith((".md", ".json")):
            res.append((os.path.join(SRC_TEXT, f), os.path.join("各版原文", f)))
    for f in RULE_FILES:
        res.append((os.path.join(SRC_RULE, f), os.path.join("段级核定表", f)))
    for d in sorted(os.listdir(SRC_PKG)):
        p = os.path.join(SRC_PKG, d, "交付", "版本包.json")
        if os.path.exists(p):
            res.append((p, os.path.join("各版本包", d + ".json")))

    print(f"统一资源 {len(res)} 件，六个包")
    for pkg in PKGS:
        base = os.path.join(ROOT, pkg, "数据")
        os.makedirs(base, exist_ok=True)
        n = 0
        for src, rel in res:
            if ensure(src, os.path.join(base, rel)):
                n += 1
        idx = os.path.join(base, "原书索引.md")
        txt = index_md(pkg, rows)
        if not os.path.exists(idx) or open(idx, encoding="utf-8").read() != txt:
            open(idx, "w", encoding="utf-8").write(txt)
            n += 1
        print(f"  {pkg}: 写入 {n} 件")
    print("book_anchors.json ->", os.path.join(ENG, "book_anchors.json"))


if __name__ == "__main__":
    main()
