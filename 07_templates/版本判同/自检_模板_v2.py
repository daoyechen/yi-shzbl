#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本判同交付自检（模板 v2）。交付前跑一遍。

    python3 工具/自检.py 交付/判同.json

查八项，任一不过即退出码 1：
  1. JSON 可解析
  2. items 恰好 6 条，编号为 C6a-001..006，不重不漏
  3. 每条的必填字段都在，且无空值
  4. 判定值为四选一
  5. 载体形态为七选一
  6. 每条依据 ≥2 项，且每项有页号与观察
  7. 页号形如 pNNN，且该页在 数据/判读页/<编号>/ 里真实存在
  8. 依据里不许出现文件名（.pdf / .epub / .txt）
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)

REQUIRED = ["编号", "判定", "归属", "题名", "卷数", "撰注", "刊刻", "载体", "藏馆", "行款", "依据", "未决"]
VERDICTS = {"同版", "同系统异本", "另一版", "非本书版本", "无法判定"}
ASSIGN = {"L1版本栏", "L2注本", "参考书目"}
CARRIERS = {"影印(丛书)", "原件翻拍", "现代排印", "写本", "钞本", "稿本", "活字本"}
CODES = [f"C6a-{i:03d}" for i in range(1, 7)]   # 换包时改这里
PAGE_RE = re.compile(r"^p(\d{3})$")
FILE_RE = re.compile(r"\.(pdf|epub|txt|docx?|mobi)\b", re.I)


def fail(errs, msg):
    errs.append(msg)


def main():
    if len(sys.argv) < 2:
        print("用法: python3 工具/自检.py 交付/判同.json")
        return 2
    path = sys.argv[1]
    errs, warns = [], []

    if not os.path.exists(path):
        print(f"✗ 文件不存在: {path}")
        return 1
    try:
        d = json.load(open(path, encoding="utf-8-sig"))
    except Exception as e:
        print(f"✗ JSON 解析失败: {e}")
        return 1

    items = d.get("items") or []
    if len(items) != 6:
        fail(errs, f"条数应为 6，实为 {len(items)}")

    got = [x.get("编号") for x in items]
    if got != CODES:
        # 允许乱序但不允许缺重
        if sorted(got) != sorted(CODES):
            fail(errs, f"编号不齐或重复：{got}")
        else:
            warns.append("编号顺序与清单不同（可接受，但建议按序）")

    for it in items:
        code = it.get("编号", "?")
        for k in REQUIRED:
            if k not in it:
                fail(errs, f"{code} 缺字段 {k}")
            elif k != "依据" and (it[k] is None or str(it[k]).strip() == ""):
                fail(errs, f"{code} 字段 {k} 为空")
            elif k != "依据" and str(it[k]).strip() in ("—", "-", "?"):
                fail(errs, f"{code} 字段 {k} 是占位符，请写具体内容或「未得」")

        v = it.get("判定")
        if v and v not in VERDICTS:
            fail(errs, f"{code} 判定「{v}」不在允许值内：{sorted(VERDICTS)}")
        c = it.get("载体")
        if c and c not in CARRIERS:
            fail(errs, f"{code} 载体「{c}」不在允许值内：{sorted(CARRIERS)}")
        a = it.get("归属")
        if a and a not in ASSIGN:
            fail(errs, f"{code} 归属「{a}」不在允许值内：{sorted(ASSIGN)}")
        # 判定与归属必须配套：非本书版本不许进 L1
        if v == "非本书版本" and a == "L1版本栏":
            fail(errs, f"{code} 判「非本书版本」却归「L1版本栏」，矛盾")
        if a == "L1版本栏" and v in ("无法判定",):
            fail(errs, f"{code} 判「{v}」不该归 L1版本栏")

        ev = it.get("依据")
        if not isinstance(ev, list) or len(ev) < 2:
            fail(errs, f"{code} 依据不足 2 项")
            continue
        for j, e in enumerate(ev, 1):
            if not isinstance(e, dict):
                fail(errs, f"{code} 依据第{j}项格式不对")
                continue
            pg, ob = e.get("页", ""), e.get("观察到", "")
            if not pg:
                fail(errs, f"{code} 依据第{j}项缺页号")
                continue
            m = PAGE_RE.match(str(pg))
            if not m:
                fail(errs, f"{code} 页号「{pg}」格式应为 pNNN")
                continue
            page = f"p{m.group(1)}.jpg"
            pdir = os.path.join(PKG, "数据", "判读页", code)
            if os.path.isdir(pdir) and page not in os.listdir(pdir):
                fail(errs, f"{code} 页号 {pg} 在判读页里不存在")
            if not str(ob).strip():
                fail(errs, f"{code} 依据第{j}项「观察到」为空")
            if FILE_RE.search(str(ob)):
                fail(errs, f"{code} 依据第{j}项引用了文件名，必须改为看图的观察")

    print("=" * 52)
    if warns:
        for w in warns:
            print(f"⚠ {w}")
    if errs:
        print(f"✗ 自检未通过，共 {len(errs)} 处：")
        for e in errs:
            print(f"   · {e}")
        print("=" * 52)
        return 1
    print("✓ 自检通过：6 条齐、字段齐、依据可回溯、无文件名引用")
    print("=" * 52)
    return 0


if __name__ == "__main__":
    sys.exit(main())