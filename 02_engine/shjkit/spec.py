#!/usr/bin/env python3
"""版本接入规格(spec.json)—— 每个新版本一份,驱动全流程。

**这是分包的接口契约。** 新增一个版本 = 写一份 spec.json + 提供转录 md,
**不改动引擎任何一行代码**。

字段说明:

  版本名        显示名,例 "桂林古本"
  文件          转录件路径(相对版本包根目录),例 "版本正文/09_桂林古本伤寒杂病论.md"
  正文起点      该版正文的起始标志行原文;null = 该选集起始即正文
                (用于切掉序/凡例/目录/校注说明等前置材料)
  篇目标记      该版篇目标题的识别正则列表(行首匹配);空 = 无篇级层
  收录范围      "此版无"的判定依据:
                  kind  选集未收 / 本版仅残卷 / 原书残损 / 体例不同 / 此版无此篇
                  evid  原文依据(必须引自该版原文,不得转述推断)
                  start 仅 kind=选集未收 时用:条号小于此值者不在选集内
  校记锚点      true = 该版校记中含「同《宋本伤寒论》第X条」式硬锚点,优先采用
  编号形式      该版自身是否带条号:
                  无    — 靠文字对应(默认)
                  逐位汉字 — 该版条号与宋本同为逐位汉字写法
                  阿拉伯 — 该版用 1,2,3 阿拉伯数字
  切条策略      auto / 行段 / 逐行
                  auto  由引擎按篇目标记与行结构自动判定(默认)
                  行段  以空行分段为一条
                  逐行  一行一证(方药行并入前条)
"""
import json
import os
import re

SPEC_NAME = "spec.json"

# 合法的「此版无」原因枚举(与引擎内置一致,不得自创)
REASONS = [
    "选集未收",    # 该本收录范围自某篇起,前此诸篇不收
    "本版仅残卷",  # 该版正文自称残卷
    "原书残损",    # 该版自陈虫蛀残缺
    "体例不同",    # 该版以他种体例编排,条不构成对应单元
    "此版无此篇",  # 该版篇目中确无此篇
    "暂未匹配",    # 全文检索未见对应文字,留待人工复核
]

REQUIRED = ["版本名", "文件", "收录范围"]


def validate(spec):
    """返回 (ok:bool, errors:list[str])。"""
    errs = []
    for k in REQUIRED:
        if k not in spec:
            errs.append(f"缺必填字段:{k}")
    cov = spec.get("收录范围") or {}
    kind = cov.get("kind")
    if kind and kind not in REASONS:
        errs.append(f"收录范围.kind 非法:{kind}(合法值:{','.join(REASONS)})")
    if kind and not cov.get("evid"):
        errs.append("收录范围.evid 不能为空:必须引原文依据")
    for i, p in enumerate(spec.get("篇目标记") or []):
        try:
            re.compile(p)
        except re.error as e:
            errs.append(f"篇目标记[{i}] 正则非法:{e}")
    return (not errs), errs


def load(pkg_dir):
    path = os.path.join(pkg_dir, SPEC_NAME)
    with open(path, encoding="utf-8") as fh:
        spec = json.load(fh)
    ok, errs = validate(spec)
    if not ok:
        raise ValueError(f"spec.json 校验失败:\n  - " + "\n  - ".join(errs))
    return spec


def save(pkg_dir, spec):
    ok, errs = validate(spec)
    if not ok:
        raise ValueError("spec.json 校验失败:\n  - " + "\n  - ".join(errs))
    path = os.path.join(pkg_dir, SPEC_NAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=1)
    return path


def template(版本名, 文件, **kw):
    """生成一份最小可用的 spec。"""
    spec = {
        "版本名": 版本名,
        "文件": 文件,
        "正文起点": None,
        "篇目标记": [],
        "收录范围": {"kind": "暂未匹配", "evid": "待补:引该版原文说明其收录范围"},
        "校记锚点": False,
        "编号形式": "无",
        "切条策略": "auto",
    }
    spec.update(kw)
    return spec
