#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按分包表打注本派发包。

用法：
    python3 07_templates/注本派发/打包.py            # dry-run，只报缺什么
    python3 07_templates/注本派发/打包.py --apply    # 真打包

每包结构：
    <id>/
    ├── 任务书.md
    ├── 数据/
    │   ├── <注本全文>.txt          转 UTF-8
    │   ├── 骨架_<侧>_<N>条.json    统一为 no/篇/原文
    │   └── 样例_notes.json         前 20 条，只看格式
    ├── 工具/自检_注本.py
    └── 交付/交付格式.md
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
while not os.path.isdir(os.path.join(ROOT, "00_base")) and ROOT != "/":
    ROOT = os.path.dirname(ROOT)
M = os.path.join(ROOT, "30_dispatch", "31_注释本")
TABLE = os.path.join(HERE, "分包表_20261122.csv")
NAS_TXT = os.path.join(ROOT, "10_material", "19_nas", "07_电子文本")
TPL = os.path.join(ROOT, "07_templates")
SKEL = os.path.join(ROOT, "01_skeleton")
NOTES = os.path.join(ROOT, "50_data", "51_notes")
ZIPTOOL = os.path.join(ROOT, "02_engine", "zip_utf8_flag.py")

SIDE = {"sh": ("宋本", 398, "宋本398条.json"), "jg": ("赵开美本", 465, "金匮条级骨架.json")}
SAMPLE = {"sh": "keqin", "jg": "huangyuanyu_jg"}
MEASURED = {
    "chenxiuyuan_jg": "我方实测：37,916 汉字 / 248 个 `<篇名>`。**短行（≤4 汉字）占 27%**，"
                      "原书夹注被拆成独立行插进正文流，需逐篇判断夹注归属、重排成整段。不可用脚本自动拼。"
                      "另有简转繁残留（`浓朴`→厚朴、`必 齿`→必齘齿缺字）。",
    "gaoxueshan_jg": "我方实测：153,401 汉字 / 23 个 `<篇名>`（按篇分组）。**短行占 2%，文字干净**。"
                     "篇内有 `\\x一条\\x`～`\\xN条\\x` 条次标记，但只覆盖约一半篇"
                     "（血痹虚劳、肺痿肺痈、胸痹、腹满、痰饮、水气、呕吐哕等有；"
                     "脏腑经络先后、百合狐惑、妇人三篇、杂疗、禽兽鱼虫没有）。"
                     "有标记的篇可直接按篇内序号对骨架；无标记的篇靠经文首句或 `\\x方名\\x` 对。",
    "suyuanji_sh": "我方实测：213,406 汉字 / 94 个 `<篇名>`（40 个不同门名，同门跨节重复标注，"
                   "最多「厥阴证治第二十一」11 次）。**体例**：每门先引经文一句，接钱潢按语"
                   "（如「中风证治第一」下引「太阳病。发热汗出。恶风脉缓者。名为中风」再逐句释）。"
                   "门次即钱潢原书二十二门，卷末附「三百九十七法一百一十三方辨论」「动气臆说」"
                   "「铢两升合古今不同辨论」「权量考」「大斗大两」「长沙无朱雀汤说」。"
                   "**篇名可当门类锚**：同门多节，按门内顺序对宋本条号比按篇题更快。"
                   "文本经我方核：作者钱潢、序称「天来先生」、篇目与卷末附录均与钱潢本合；"
                   "无 EPUB 残留（`gltd`／`OEBPS`／`body001`／`content.opf` 均 0 命中），无《金匮》杂疗方、果实菜谷内容。",
}


def han(s):
    return re.sub(r"[^\u4e00-\u9fff]", "", s)


def read_any(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), "utf-8(replace)"


def load_skel(side):
    vers, n_max, fn = SIDE[side]
    d = json.load(open(os.path.join(SKEL, fn), encoding="utf-8"))
    items = d.get("条目", d) if isinstance(d, dict) else d
    out = []
    for x in items:
        out.append({"no": int(x["no"]),
                    "篇": x.get("篇") or x.get("pian") or "",
                    "原文": x.get("原文") or x.get("body") or ""})
    return out, n_max


def build_one(r, apply):
    pk = r["id"]
    dirname = r["目录名"]
    side = r["侧"]
    vers, n_max, _ = SIDE[side]
    src = os.path.join(NAS_TXT, r["文件名"])
    if not os.path.exists(src):
        return "缺物料：%s" % r["文件名"]

    dst_dir = os.path.join(M, dirname)
    if apply:
        shutil.rmtree(dst_dir, ignore_errors=True)     # 重建，防上一轮残留混进包
        for sub in ("数据", "工具", "交付"):
            os.makedirs(os.path.join(dst_dir, sub), exist_ok=True)

        # 1) 正文转 UTF-8
        text, enc = read_any(src)
        outname = os.path.basename(r["文件名"]).rsplit(".", 1)[0] + ".txt"
        open(os.path.join(dst_dir, "数据", outname), "w", encoding="utf-8").write(text)

        # 2) 骨架
        sk, _ = load_skel(side)
        json.dump({"条目": sk}, open(os.path.join(dst_dir, "数据", "骨架_%s_%d条.json" % (side, n_max)), "w",
                                     encoding="utf-8"), ensure_ascii=False, indent=1)

        # 3) 样例
        s = json.load(open(os.path.join(NOTES, SAMPLE[side], "notes.json"), encoding="utf-8"))[:20]
        json.dump(s, open(os.path.join(dst_dir, "数据", "样例_notes.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

        # 4) 工具与格式
        shutil.copy2(os.path.join(TPL, "自检_注本.py"), os.path.join(dst_dir, "工具", "自检_注本.py"))
        shutil.copy2(os.path.join(TPL, "注本交付格式.md"), os.path.join(dst_dir, "交付", "交付格式.md"))

        # 5) 任务书
        tpl = open(os.path.join(TPL, "注本任务书_模板.md"), encoding="utf-8").read()
        rep = {
            "{{文件名}}": outname,
            "{{注本名}}": r["注本名"],
            "{{注者}}": r["注者"],
            "{{朝代}}": r["朝代"],
            "{{所注侧}}": "金匮" if side == "jg" else "伤寒",
            "{{N}}": str(n_max),
            "{{rho}}": r["rho"],
            "{{版本名}}": vers,
            "{{id}}": pk,
            "{{C5编号}}": r["C5编号"],
            "{{C5分级}}": r["C5分级"],
            "{{字节}}": r["字节"],
            "{{侧}}": side,
            "{{sh|jg}}": side,
            "{{实测}}": MEASURED.get(pk, "我方未实测。同一批来源，编码与标签格式同上；"
                                       "串行程度未知，**请先抽 3 篇看短行占比**，再决定用脚本还是人工。"),
        }
        for k, v in rep.items():
            tpl = tpl.replace(k, v)
        open(os.path.join(dst_dir, "任务书.md"), "w", encoding="utf-8").write(tpl)

        # 6) PACK_VERSION.md（哈希由承接人算，避免打包含自身哈希的循环）
        files_now = []
        for dp, _, fn in os.walk(dst_dir):
            for f in sorted(fn):
                q = os.path.join(dp, f)
                rel = os.path.relpath(q, dst_dir)
                if rel != "PACK_VERSION.md":
                    files_now.append(rel)
        ver = (
            "# PACK_VERSION\n\n"
            "- 派发包：%s_派发包.zip\n" % dirname +
            "- 生成时间：%s\n" % datetime.now().strftime("%Y-%m-%d %H:%M") +
            "- 包内文件：%d 个\n" % (len(files_now) + 1) +
            "- 派发包 SHA256：<在此填你算出的值，命令见下>\n"
            "- 收到日期：<YYYY-MM-DD>\n\n"
            "## 怎么填\n\n"
            "```bash\nshasum -a 256 %s_派发包.zip\n```\n\n" % dirname +
            "与我方在包外给的 `.sha256` 比对，一致即传输完整。\n\n"
            "## 包内文件\n\n" + "".join("- `%s`\n" % f for f in sorted(files_now + ["PACK_VERSION.md"]))
        )
        open(os.path.join(dst_dir, "PACK_VERSION.md"), "w", encoding="utf-8").write(ver)

    return "OK %s（%s，%s 字，%s）" % (dirname, r["文件名"], r["字数"], "已打包" if apply else "可打包")


def main():
    apply = "--apply" in sys.argv
    rows = list(csv.DictReader(open(TABLE, encoding="utf-8-sig")))
    print("%s：%d 部" % ("实打" if apply else "预检", len(rows)))
    ok, bad = [], []
    for r in rows:
        msg = build_one(r, apply)
        print("  " + msg)
        (ok if msg.startswith("OK") else bad).append(msg)
    print("\n可打 %d，有问题 %d" % (len(ok), len(bad)))

    if apply and ok:
        print("\n打 zip：")
        for r in rows:
            dn = r["目录名"]
            d = os.path.join(M, dn)
            if not os.path.isdir(d):
                continue
            z = os.path.join(M, "%s_派发包.zip" % dn)
            if os.path.exists(z):
                os.remove(z)
            p = subprocess.run([sys.executable, ZIPTOOL, z, M, dn],
                               capture_output=True, text=True)
            if p.returncode != 0 or not os.path.exists(z):
                print("  %-40s 打包失败 %s" % (os.path.basename(z), p.stderr[:60]))
                continue
            # 包内 manifest.json（对象格式，pack_check 可核）
            with zipfile.ZipFile(z) as zf:
                ents = []
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    data = zf.read(info)
                    ents.append({"path": info.filename,
                                 "bytes": len(data),
                                 "sha256": hashlib.sha256(data).hexdigest()})
            man = {"pack": os.path.basename(z),
                   "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "files": ents}
            tmp = os.path.join(M, "._manifest.tmp")
            json.dump(man, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            with zipfile.ZipFile(z, "a", zipfile.ZIP_DEFLATED) as zf:
                zf.write(tmp, "manifest.json")
            os.remove(tmp)
            # 外部 sha256
            h = hashlib.sha256(open(z, "rb").read()).hexdigest()
            open(z + ".sha256", "w").write("%s  %s\n" % (h, os.path.basename(z)))
            size = os.path.getsize(z) / 1e6
            print("  %-40s %6.2f MB  条目%d  ok" % (os.path.basename(z), size, len(ents) + 1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
