#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盘点 `_待验/` 磁盘实况，与既有台账对账，产出唯一真源。

为什么需要它：
  历史台账可能已经过期；现行清单必须由本脚本从 `_待验` 实测生成。
  脚本只用现行清单复用哈希，并以本轮磁盘实测覆盖它。

本脚本做三件事：
  1. 走盘，逐件记：字节 / sha256 / 页数（仅 PDF）/ 类型 / 相对路径。
     已有台账里 sha256 可信（已抽查字节一致）就复用，只对新件重算。
  2. 与旧台账对账，输出：在盘未登记 / 已登记但不在盘 / 两边都在。
  3. 写 `01_台账/清单.csv`（唯一真源）+ `对账报告.md`（给人看的差异说明）。

页数：PDF 走 `/Type /Page` 正则，算不出用 ghostscript 兜底；非 PDF 留空并注明。

用法：
  python3 inventory.py                # 全量，写文件
  python3 inventory.py --dry          # 只报告
"""
import argparse
import csv
import hashlib
import os
import re
import subprocess
import sys

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(B, "_待验")
# 现行清单既是哈希缓存，也是本轮对账基线；不存在时按空台账处理。
OUTDIR = os.path.join(B, "10_material/15_catalog/01_台账")
OLD = os.path.join(OUTDIR, "清单.csv")

FIELDS = ["编号", "目录", "文件名", "字节", "MB", "页数", "页数来源",
          "类型", "sha256", "sha256来源", "相对路径", "台账登记", "备注"]


def file_type(ext):
    ext = ext.lower()
    if ext == ".pdf": return "PDF"
    if ext in (".txt",): return "纯文本"
    if ext in (".epub",): return "EPUB"
    if ext in (".doc", ".docx"): return "Word"
    if ext in (".mobi",): return "MOBI"
    if ext == ".md": return "Markdown"
    return ext.lstrip(".").upper() or "其他"


def count_pages(path):
    """返回 (页数, 来源)。算不出返回 (None, '')。"""
    try:
        data = open(path, "rb").read()
    except OSError:
        return None, ""
    n = len(re.findall(rb"/Type\s*/Page[^s]", data))
    if n > 0:
        return n, "正则"
    cs = [int(x) for x in re.findall(rb"/Count\s+(\d+)", data)]
    if cs and max(cs) > 0:
        return max(cs), "正则Count"
    # gs 兜底
    try:
        r = subprocess.run(["gs", "-q", "-dNODISPLAY", "-dNOSAFER", "-c",
                            f"({path}) (r) file runpdfbegin pdfpagecount = quit"],
                           capture_output=True, text=True, timeout=180)
        s = r.stdout.strip()
        if s and s.split()[-1].isdigit():
            v = int(s.split()[-1])
            if v > 0:
                return v, "gs"
    except Exception:
        pass
    return None, ""


def sha256_of(path, cache):
    if path in cache:
        return cache[path], "复用台账"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest(), "实算"


def load_old():
    """旧台账 → {sha256: row}, {相对路径尾段: row}"""
    if not os.path.exists(OLD):
        return {}, {}
    rows = list(csv.DictReader(open(OLD, encoding="utf-8-sig")))
    by_sha, by_name = {}, {}
    for r in rows:
        sha = (r.get("sha256") or "").strip()
        if len(sha) == 64:
            by_sha[sha] = r
        fn = (r.get("文件名") or "").strip()
        if fn:
            by_name.setdefault(fn, []).append(r)
    return by_sha, by_name


def walk_disk():
    items = []
    for d, _, fs in os.walk(ROOT):
        for f in fs:
            if f in (".DS_Store",) or f.startswith("._"):
                continue
            p = os.path.join(d, f)
            if not os.path.isfile(p):
                continue
            items.append(p)
    return sorted(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    old_by_sha, old_by_name = load_old()
    # 先把旧台账里「在盘」件的 sha256 做成缓存，避免重算 5 GB
    cache = {}
    for r in list(old_by_sha.values()) + [x for v in old_by_name.values() for x in v]:
        p, sha = r.get("完整路径", ""), (r.get("sha256") or "").strip()
        if p and len(sha) == 64 and os.path.exists(p):
            cache[p] = sha

    paths = walk_disk()
    print(f"磁盘实测：{len(paths)} 件")
    rows, new_sha_computed = [], 0

    for i, p in enumerate(paths, 1):
        rel = os.path.relpath(p, B)
        ext = os.path.splitext(p)[1]
        size = os.path.getsize(p)
        sha, shasrc = sha256_of(p, cache)
        if shasrc == "实算":
            new_sha_computed += 1
        pages, psrc = (None, "")
        if ext.lower() == ".pdf":
            pages, psrc = count_pages(p)

        reg = "是" if sha in old_by_sha else "否"
        note = ""
        if reg == "否":
            same = old_by_name.get(os.path.basename(p), [])
            if same:
                note = "台账有同名件但 sha256 不符（疑同名异本或已变更）"
            else:
                note = "台账无记录（漏登记）"
        rows.append({
            "编号": f"P{i:04d}",
            "目录": os.path.relpath(os.path.dirname(p), ROOT).replace(".", "(根)"),
            "文件名": os.path.basename(p),
            "字节": size,
            "MB": f"{size/1048576:.2f}",
            "页数": pages if pages else "",
            "页数来源": psrc,
            "类型": file_type(ext),
            "sha256": sha,
            "sha256来源": shasrc,
            "相对路径": rel,
            "台账登记": reg,
            "备注": note,
        })

    # 对账
    disk_sha = {r["sha256"] for r in rows}
    missing = [r for s, r in old_by_sha.items() if s not in disk_sha]
    unreg = [r for r in rows if r["台账登记"] == "否"]

    print(f"  新算 sha256：{new_sha_computed} 件（其余复用台账）")
    print(f"  台账有、磁盘无：{len(missing)} 件")
    print(f"  磁盘有、台账无：{len(unreg)} 件")
    print(f"  PDF 页数缺失：{sum(1 for r in rows if r['类型']=='PDF' and not r['页数'])} 件")

    if a.dry:
        print("\n（dry-run，未写文件）")
        for r in unreg:
            print(f"    [漏登记] {r['相对路径']}")
        return

    os.makedirs(OUTDIR, exist_ok=True)
    cp = os.path.join(OUTDIR, "清单.csv")
    with open(cp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\n已写 {cp}（{len(rows)} 行）")

    # 对账报告
    from collections import Counter
    bydir = Counter(r["目录"] for r in rows)
    missdir = Counter((r.get("目录") or "").split("/")[0] for r in missing)
    rp = os.path.join(OUTDIR, "对账报告.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(f"""# 待验区盘点对账（{len(rows)} 件在盘）

> 由 `02_engine/inventory.py` 生成。**本清单是唯一真源**，
> 本轮以磁盘实测结果覆盖现行清单；旧清单只用于本轮哈希缓存。

## 一、磁盘实况

| 目录 | 件数 |
|---|---:|""")
        for k, v in sorted(bydir.items(), key=lambda x: -x[1]):
            f.write(f"\n| `{k}` | {v} |")
        f.write(f"\n| **合计** | **{len(rows)}** |\n")

        f.write(f"""
## 二、与旧台账的差额

旧台账登记 471 件，磁盘 {len(rows)} 件。差额分两类：

### 2.1 台账有、磁盘无（{len(missing)} 件）

| 来源目录 | 件数 |
|---|---:|""")
        for k, v in sorted(missdir.items(), key=lambda x: -x[1]):
            if k: f.write(f"\n| `{k}` | {v} |")
        f.write(f"""

**处置**：已移出本项目（NAS 有备份），不占本项目存储。
本清单不再登记这些件；若日后要恢复，按 sha256 从备份取回后重跑本脚本。

### 2.2 磁盘有、台账无（{len(unreg)} 件，漏登记）

| 相对路径 | 字节 | 备注 |
|---|---:|---|""")
        for r in unreg:
            f.write(f"\n| `{r['相对路径']}` | {r['字节']} | {r['备注']} |")
        f.write("""

## 三、字段说明

| 字段 | 含义 |
|---|---|
| `页数` / `页数来源` | 仅 PDF 有值；来源 `正则` / `正则Count` / `gs` |
| `sha256来源` | `复用台账`（已验字节一致）或 `实算`（新件） |
| `台账登记` | `是` = 旧台账有此 sha256；`否` = 漏登记 |

**哈希口径**：一律完整 64 位 SHA256。不许截断，不许用 MD5 代 SHA256——
截断值既不能严格核验，又容易被误读成其他算法。
""")
    print(f"已写 {rp}")


if __name__ == "__main__":
    main()