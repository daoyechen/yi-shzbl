#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公共骨架:**多骨架注册表**。

2026-11-05 改造(《金匮骨架契约》丙方案:双层结构)
--------------------------------------------------
原设计只有一个骨架(宋本《伤寒论》398 条),`398` 被硬编码进
skeleton.py / verify.py / assemble.py / htmlbuild.py / pkgbuild.py 五处。
现改为**注册表**驱动:

  - 骨架注册表 `00_公共地基/骨架/骨架注册表.json` 登记全部骨架
  - 每个骨架有自己的 **id / 编号空间 / 条号集合 / 是否分层**
  - **编号空间彼此独立** —— 伤寒 SH 与 金匮 JG 的 no 不是同一套数字,不可混用

两个骨架的结构差异(这正是「丙」方案的要点):

  ┌ 骨架 shanghan ── 顶层:条(398) ────────────── 子层:各版异文分段(既有语义)
  └ 骨架 jingui   ── 顶层:条(N)   ── 子层:句(词级单元,新字段 `句`)

注意两个「子层」语义**不同**,故字段名也不同:
  - 伤寒侧 `分段` = 某版一条内对应多个宋本条的**异文分段**(既有,不动)
  - 金匮侧 `句`   = 同一条内的**句级单元**(新),用于版本学下钻

**公共地基,任何分包不得修改**(硬约束)。发现骨架错误 → 提《争议与疑难清单》,
由总装裁决后统一改版并重发。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))       # 引擎/shjkit/
ENGINE = os.path.dirname(HERE)                          # 02_engine/
FOUND = os.path.dirname(ENGINE)                        # 项目根
REG_PATH = os.path.join(FOUND, "01_skeleton", "骨架注册表.json")
DEFAULT_SKEL = "shanghan"


def load_registry(path=REG_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def skel_spec(skel_id=None, registry=None):
    """取某骨架的登记项。"""
    reg = registry or load_registry()
    sid = skel_id or os.environ.get("SHJ_SKEL") or DEFAULT_SKEL
    for s in reg["骨架"]:
        if s["id"] == sid:
            return s
    raise KeyError(f"骨架 {sid} 未登记。已登记: {[s['id'] for s in reg['骨架']]}")


def skel_path(spec):
    p = spec["路径"]
    return p if os.path.isabs(p) else os.path.join(FOUND, p)


def load_skeleton(skel_id=None, path=None):
    """载入某骨架的条目列表。

    - 校验条号唯一
    - 校验条号集合与登记项一致(注册表写死的才查;未写死的按自身范围查)
    - **不再硬编码 1..398**
    """
    if path is None:
        spec = skel_spec(skel_id)
        path = skel_path(spec)
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    items = d["条目"] if isinstance(d, dict) else d

    nos = [i["no"] for i in items]
    assert len(nos) == len(set(nos)), "骨架条号有重复"

    spec = None
    try:
        spec = skel_spec(skel_id)
    except Exception:
        pass

    if spec and spec.get("条数"):
        assert len(items) == spec["条数"], \
            f"骨架条数 {len(items)} ≠ 登记 {spec['条数']}"
        if spec.get("允许跳号"):
            # 剔除误切条目后**保留原 no 不重映射**,故 no 可跳号(仅登记跳过数)
            assert min(nos) == 1, "骨架条号起点非 1"
            assert len(set(nos)) == len(nos), "骨架条号重复"
        else:
            assert min(nos) == 1 and max(nos) == len(items), "骨架条号越界或缺号"
    else:
        assert nos == list(range(min(nos), max(nos) + 1)), "骨架条号不连续"
    return items


def skeleton_nos(skel_id=None):
    """该骨架的合法条号集合。"""
    return {i["no"] for i in load_skeleton(skel_id)}


def n_items(skel_id=None):
    """骨架条数 —— 取代硬编码的 398。"""
    return len(load_skeleton(skel_id))


def build_index(items):
    """n-gram → 条序号 倒排索引。"""
    from collections import defaultdict
    from .textutil import ngrams
    idx = defaultdict(list)
    for i, it in enumerate(items):
        for g in ngrams(it["key"]):
            idx[g].append(i)
    return idx


def jingui_units(items):
    """《金匮》侧:从条级骨架取出句级单元(丙方案子层)。

    没有 `句` 字段的条目 → 返回空列表(该版未做句级细分)。
    """
    out = []
    for it in items:
        for s in it.get("句", []) or []:
            out.append((it["no"], s.get("seq"), s.get("原文", "")))
    return out


if __name__ == "__main__":
    reg = load_registry()
    print(f"骨架注册表 {reg.get('版本')} · 共 {len(reg['骨架'])} 个骨架")
    for s in reg["骨架"]:
        try:
            items = load_skeleton(s["id"])
            extra = ""
            if s.get("分层"):
                extra = f" · 句级单元 {len(jingui_units(items))} 个"
            print(f"  [{s['id']:<10}] {s['名称']}")
            print(f"      条数 {len(items)} · 编号空间 {s.get('编号空间')}"
                  f" · 顶层 {s.get('顶层')} · 分层 {s.get('分层', False)}{extra}")
        except Exception as e:
            print(f"  [{s['id']:<10}] {s['名称']} —— ⚠ 载入失败: {e}")
    from collections import Counter
    items = load_skeleton(DEFAULT_SKEL)
    print(f"\n默认骨架 {DEFAULT_SKEL}: {len(items)} 条,零缺号 ✅")
    for k, v in Counter(i["pian"] for i in items).items():
        print(f"  {v:4d}  {k}")
