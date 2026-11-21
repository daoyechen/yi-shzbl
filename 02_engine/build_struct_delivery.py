#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结构数据交付打包器 —— 按「伤寒论 / 金匮要略 / 伤寒杂病论」三分法重组

原则：
  · 只放结构化数据与转录正文（md/json），**不放影印 PDF 底本**（底本另出专包）
  · 每包带文件清单 + 逐文件 SHA256
  · 不覆盖旧包（另起版本化文件名）

用法：python3 build_struct_delivery.py --out <输出目录> [--with-pdf]
"""
import argparse
import hashlib
import os
import shutil
import zipfile

OUT = "/workspace/output/并行分包/27_结构数据交付_v1.0"
SRC1 = "/workspace/work/packtest/金匮要略_第一包_伤寒论数据"
SRC2 = "/workspace/work/packtest/金匮要略_第二包_金匮要略数据"
SRC3 = "/workspace/work/packtest/金匮要略_第三包_总合"
BASE = "/workspace/output/并行分包/00_公共地基"
RET25 = "/workspace/work/ret25/pkg25_r2.zip"
RET22 = "/workspace/attachments/4febf2255afd68f5/第五批_任务2_2_O_总书形态底本收集.zip"
RET21 = "/workspace/work/lpkg/pk/pkg_L/task_2_1"
JINGUI = "/workspace/output/并行分包/03_总装产出_v0.12.0"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cp(src, dst):
    if not os.path.exists(src):
        print("  ⚠ 缺 %s" % src)
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return True


def cpz(zpath, inner, dst):
    """从 zip 内取一个文件到 dst"""
    with zipfile.ZipFile(zpath) as z:
        if inner not in z.namelist():
            print("  ⚠ 缺 %s :: %s" % (os.path.basename(zpath), inner))
            return False
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as w:
            w.write(z.read(inner))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    root = args.out
    if os.path.exists(root):
        shutil.rmtree(root)
    os.makedirs(root)

    # ───────── 01 伤寒论 ─────────
    d = os.path.join(root, "01_伤寒论")
    os.makedirs(d, exist_ok=True)
    cp(os.path.join(BASE, "骨架/宋本398条.json"), os.path.join(d, "骨架/宋本398条.json"))
    for f in sorted(os.listdir(JINGUI)):
        if f == "viewer_data.json":
            continue
        cp(os.path.join(JINGUI, f), os.path.join(d, "结构", f))
    cp(os.path.join(JINGUI, "viewer_data.json"), os.path.join(d, "结构/viewer_data.json"))
    # 各版原文（9 版）
    for ver, fname in [("唐本", "06_唐本伤寒论.md"), ("康平本", "03_康平本伤寒论.md"),
                       ("康治本", "02_康治本伤寒论.md"), ("敦煌本", "01_敦煌本伤寒论(残卷).md"),
                       ("桂林古本", "01_桂林古本伤寒杂病论.md"), ("注解伤寒论", "08_注解伤寒论_十卷全本.md"),
                       ("脉经本", "10_脉经全十卷.md"), ("金匮玉函经", "04_金匮玉函经.md"),
                       ("高继冲本", "05_高继冲本伤寒论.md")]:
        s = os.path.join(SRC1, "基线_11版/版本包_%s/版本正文/%s" % (ver, fname))
        cp(s, os.path.join(d, "各版原文/%s_%s" % (ver, fname)))
    # 注文（注解本 372 条）
    for f in ["注文对照.md", "注文索引.md"]:
        cp(os.path.join(SRC1, "基线_11版/版本包_注解伤寒论/交付", f),
           os.path.join(d, "注文/%s" % f))
    cp(os.path.join(SRC1, "基线_11版/版本包_注解伤寒论/_工作/注文单元.json"),
       os.path.join(d, "注文/注文单元.json"))

    # ───────── 02 金匮要略 ─────────
    d = os.path.join(root, "02_金匮要略")
    os.makedirs(d, exist_ok=True)
    cp(os.path.join(BASE, "骨架/金匮条级骨架.json"), os.path.join(d, "骨架/金匮条级骨架_465条.json"))
    cp(os.path.join(BASE, "骨架/金匮句级骨架_1388.json"), os.path.join(d, "骨架/金匮句级骨架_1316段.json"))
    cp(os.path.join(BASE, "骨架/骨架注册表.json"), os.path.join(d, "骨架/骨架注册表.json"))
    # 2_6 交付件
    for f in ["A10_条级参照系.json", "A10_条级参照系.md", "A4_体例行逐篇登记.md",
              "条界裁定.json", "金匮条级骨架.json", "争议与疑难清单.md", "核对记录.md"]:
        cp(os.path.join("/workspace/work/r26b/pkg_J/交付", f), os.path.join(d, "参照系与裁定", f))
    # 2_6 对照成果
    for f in ["逐条核定表.md", "锚点表.md", "篇级对照.md", "缺篇对照.md", "繁简映射.json",
              "版本对照.md", "切条规则说明.md", "清单.md"]:
        cp(os.path.join("/workspace/work/r26b/pkg_J/对照", f), os.path.join(d, "结构", f))
    # 2_6 五版正文
    for f in ["人卫排印本1964.md", "俞桥本四部丛刊.md", "医统正脉1601.md", "赵开美本1599.md", "邓珍本1340.md"]:
        cp(os.path.join("/workspace/work/r26b/pkg_J/版本正文", f), os.path.join(d, "各版原文", f))
    # 2_5 人工裁定与逐条核定
    for f in ["人工裁定_2_5.json", "人工裁定_2_5_汇总.json"]:
        cpz(RET25, "交付/" + f, os.path.join(d, "裁定", f))
    for f in ["逐条核定表_2_5_A3.md", "逐条核定表_2_5_A4.md"]:
        cpz(RET25, "交付/" + f, os.path.join(d, "裁定", f))
    cpz(RET25, "骨架/赵开美金匮骨架.json", os.path.join(d, "骨架/赵开美金匮骨架_2_5.json"))
    # 2_1 交付（体例行 25 篇全表 + 争议 + 底本著录）
    for f in ["体例行登记.md", "争议与疑难清单.md", "底本清单表.md", "底本著录.md", "获取日志.md"]:
        cp(os.path.join(RET21, "交付", f), os.path.join(d, "体例行与著录", f))
    for f in sorted(os.listdir(os.path.join(RET21, "图/体例行"))):
        cp(os.path.join(RET21, "图/体例行", f), os.path.join(d, "体例行与著录/凭据图", f))
    # A3-R1 电子文本底本（6 件 htm，小）
    for f in sorted(os.listdir(os.path.join(RET21, "底本"))):
        if f.lower().endswith(".htm"):
            cp(os.path.join(RET21, "底本", f), os.path.join(d, "底本_电子文本", f))

    # ───────── 03 伤寒杂病论 ─────────
    d = os.path.join(root, "03_伤寒杂病论")
    os.makedirs(d, exist_ok=True)
    with zipfile.ZipFile(RET22) as z:
        for n in z.namelist():
            if "/交付/" in n or "/分析件/" in n:
                rel = n.split("/", 1)[1]
                cpz(RET22, n, os.path.join(d, "总书形态", rel))
    # 总书形态底本清单（不放大件实体）
    for n in ["交付/底本清单表.md", "交付/底本著录.md", "交付/获取日志.md", "交付/争议与疑难清单.md"]:
        cpz(RET22, "第五批_任务2_2_O_总书形态底本收集/" + n,
           os.path.join(d, "总书形态", os.path.basename(n)))

    # ───────── 清单 + 哈希 ─────────
    rows = []
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            rows.append((os.path.relpath(p, root), os.path.getsize(p), sha256(p)))
    with open(os.path.join(root, "文件清单.tsv"), "w", encoding="utf-8") as w:
        w.write("路径\t字节\tSHA256\n")
        for r, s, h in rows:
            w.write("%s\t%d\t%s\n" % (r, s, h))
    print("✔ 结构数据已重组：%d 个文件" % len(rows))
    for top in sorted(os.listdir(root)):
        p = os.path.join(root, top)
        if os.path.isdir(p):
            n = sum(len(fs) for _, _, fs in os.walk(p))
            sz = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(p) for f in fs)
            print("   %-16s %4d 文件  %8.1f MB" % (top, n, sz / 1048576))
    return root


if __name__ == "__main__":
    main()
