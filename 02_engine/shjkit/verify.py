#!/usr/bin/env python3
"""版本包校验器 —— DoD 自检的机器部分。

**硬检查**(不过即 FAIL):
  1. spec.json 存在且合法
  2. 转录件存在,含 `<!-- pN -->` 页锚
  3. 交付件齐全(7 件)
  4. 版本包.json 结构完整,条号 1..398 无缺
  5. 「此版无」条目必须有原因(合法枚举)与证据(非空)
  6. 独有序 ID 格式合规,无重复
  7. 低置信条目已列入待复核
  8. **记号一致性**:重文号写法不混用(々/〻)
  9. **重文号不孤立**:`々` 前面必须有字(否则是误用)

**警告**(不阻塞,但打印出来,总装会看):
  W1. 引号内出现孤立拉丁串(疑为残卷记号误写,须在争议清单备案)
  W2. 正文圈码与页脚注编号不对应

退出码 0 = 全过;1 = 有 FAIL。
"""
import json
import os
import re
import sys
from collections import Counter

from . import skeleton as SK
from . import spec as SP

DELIVERABLES = ["版本对照.md", "本版独有.md", "锚点表.md",
                "待复核.md", "体例说明.md", "方剂表.md", "版本包.json"]

MARK = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
CJK = r"㐀-䶿一-鿿〇"          # 汉字
BOX = "□"                        # 缺字标记


# ---------- 记号检查 ----------

def _line_marks(recs):
    """正文圈码(行内标记)与页脚注编号(行首)。

    脚注行首可能统摄多个圈码(如「①、②、③:此三条均不见…」),须全部提取。
    """
    txt, foot = {}, {}
    for r in recs:
        raw = r["raw"]
        if r["kind"] in ("text", "yao", "head"):
            for ch in MARK:
                if ch in raw:
                    txt.setdefault(r["page"], set()).add(ch)
        elif r["kind"] == "foot":
            m = re.match(rf"^([{MARK}](?:[、,][{MARK}])*)", raw)
            if m:
                for ch in m.group(1):
                    if ch in MARK:
                        foot.setdefault(r["page"], set()).add(ch)
    return txt, foot


def check_marks(txt):
    """记号一致性检查。返回 (硬错列表, 警告列表)。

    只扫**正文**(第一个 `---` 之后),且剔除行内代码块(`...`)——
    说明文字里提到「々」不是记号用法,不该误报。
    """
    errs, warns = [], []
    raw = txt.split("---", 1)[-1] if "---" in txt else txt
    raw = re.sub(r"`[^`]*`", "", raw)      # 去行内代码
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)   # 去页锚注释

    # A1 々 / 〻 混用
    has_zh = "々" in raw
    has_v = "〻" in raw
    if has_zh and has_v:
        errs.append(f"重文号写法混用:同时出现 々({raw.count('々')}) 与 〻({raw.count('〻')});"
                    f"全项目只准一种(规范见 `规范/记号规范.md`)")

    # A2 孤立 々:前面不是汉字、也不是缺字标记 □
    for m in re.finditer(r"々", raw):
        i = m.start()
        prev = raw[i - 1] if i > 0 else ""
        if not (re.match(f"[{CJK}{BOX}]", prev or " ")):
            line = raw[:i].count("\n") + 1
            ctx = raw[max(0, i - 14):i + 4].replace("\n", " ")
            errs.append(f"孤立重文号 々(正文第 {line} 行,前文「…{ctx}」):"
                        f"重文号必须重复前一个字,前面无字即为误用 —— "
                        f"常见成因是把「单字省写符号」误判为重文号")

    # W1 引号内的孤立拉丁串(疑为残卷记号误写)
    for m in re.finditer(r"[“「]([^”」]{1,12})[”」]", raw):
        g = m.group(1)
        if re.search(r"[A-Za-z]", g) and not re.search(r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹḿ]", g):
            line = raw[:m.start()].count("\n") + 1
            warns.append(f"引号内含拉丁串「{g.strip()}」(第 {line} 行):"
                         f"疑为残卷记号被排印成拉丁字母形 —— "
                         f"须在《争议与疑难清单.md》备案并说明性质(重文号 / 单字省写)")
    return errs, warns


def check_marks_vs_feet(recs):
    """正文圈码 ↔ 页脚注编号(跨页容差 ±1)。返回警告列表。"""
    txt, foot = _line_marks(recs)
    warns = []
    pages = set(txt) | set(foot)
    for p in sorted(pages):
        near_foot = foot.get(p, set()) | foot.get(p - 1, set()) | foot.get(p + 1, set())
        near_txt = txt.get(p, set()) | txt.get(p - 1, set()) | txt.get(p + 1, set())
        for ch in sorted(txt.get(p, set()) - near_foot):
            warns.append(f"正文圈码 {ch}(p{p})无对应页脚注")
        for ch in sorted(foot.get(p, set()) - near_txt):
            warns.append(f"页脚注 {ch}(p{p})在正文圈码中无对应")
    return warns


# ---------- 主检查 ----------

def check(pkg_dir):
    rows = []
    warns = []

    def add(name, ok, detail):
        rows.append((name, "✅" if ok else "❌", detail))

    def warn(detail):
        warns.append(detail)

    # 1 spec
    sp_path = os.path.join(pkg_dir, "spec.json")
    if not os.path.exists(sp_path):
        add("spec.json 存在", False, "缺 spec.json")
        return rows, warns
    with open(sp_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    ok, errs = SP.validate(spec)
    add("spec.json 合法", ok, "; ".join(errs) if errs else
        f"版本名={spec.get('版本名')},原因枚举={spec.get('收录范围', {}).get('kind')}")

    # 2 转录件
    src = os.path.join(pkg_dir, spec["文件"])
    if not os.path.exists(src):
        add("转录件存在", False, f"缺 {spec['文件']}")
        return rows, warns
    txt = open(src, encoding="utf-8").read()
    pages = re.findall(r"<!-- p(\d+) -->", txt)
    add("转录件含页锚", bool(pages), f"{len(pages)} 个 `<!-- pN -->` 页锚,"
        f"页 {min(map(int, pages)) if pages else '-'}–{max(map(int, pages)) if pages else '-'}")

    # 3 交付件
    miss = [d for d in DELIVERABLES if not os.path.exists(os.path.join(pkg_dir, "交付", d))]
    add("交付件齐全", not miss, f"缺 {miss}" if miss else f"{len(DELIVERABLES)}/7 齐")

    # 4-7 需要最终版本包.json(人工裁定叠加后);没有则退回 版本包.json
    pj = os.path.join(pkg_dir, "交付", "最终版本包.json")
    if not os.path.exists(pj):
        pj = os.path.join(pkg_dir, "交付", "版本包.json")
    if not os.path.exists(pj):
        add("版本包.json 存在", False, "缺 版本包.json")
        return rows, warns
    with open(pj, encoding="utf-8") as fh:
        d = json.load(fh)
    entries = d.get("条目", [])
    nos = [e["条号"] for e in entries]
    add(f"条号 1..{SK.n_items()} 齐全", set(nos) == set(range(1, SK.n_items() + 1)),
        f"{len(nos)} 条,缺 {sorted(set(range(1, 399)) - set(nos))[:8]}")

    bad_reason = [e["条号"] for e in entries
                  if e["状态"] == "无" and e.get("原因") not in SP.REASONS]
    add("「此版无」原因合法", not bad_reason, f"非法 {bad_reason[:8]}" if bad_reason else "全合法")

    no_evid = [e["条号"] for e in entries
               if e["状态"] == "无" and not (e.get("证据") or "").strip()]
    add("「此版无」均有证据", not no_evid, f"缺证据 {no_evid[:8]}" if no_evid else "全有")

    iids = [u["iid"] for u in d.get("独有", []) if u.get("iid")]
    bad_iid = [i for i in iids if not re.fullmatch(r".+-独-\d{4}", i)]
    dup = [i for i, c in Counter(iids).items() if c > 1]
    add("独有序 ID 合规", not bad_iid and not dup,
        f"{len(iids)} 个,格式异常 {bad_iid[:5]}" if bad_iid else
        (f"{len(iids)} 个,重复 {len(dup)} 个(如 {dup[:3]})" if dup else f"{len(iids)} 个,无重复"))

    low = [e["条号"] for e in entries
           if e["状态"] == "有" and e.get("置信") == "低置信"]
    rp = os.path.join(pkg_dir, "交付", "待复核.md")
    rtxt = open(rp, encoding="utf-8").read() if os.path.exists(rp) else ""
    missing_rev = [n for n in low if f"| {n} |" not in rtxt]
    add("低置信已列入待复核", not missing_rev,
        f"未列 {missing_rev[:8]}" if missing_rev else f"{len(low)} 条低置信全列入")

    # 7b 篇目标题覆盖:转录件里的每一篇都必须在产出里有落点
    # (防止 spec「正文起点」把整篇挡在正文之外 —— 桂林古本曾因此丢掉 12 篇)
    try:
        from . import align as AL
        from . import reason as RS
        recs0 = AL.version_lines(src)
        vp0 = RS.version_pians(spec, recs0)
        in_file = []
        raw_of = {}
        for p_ in vp0:
            nm = p_.get("name")
            if nm and nm != "(卷首前段)" and nm not in in_file:
                in_file.append(nm)
                raw_of[nm] = p_.get("raw") or nm
        in_pack = set()
        for p_ in (d.get("篇目") or []):
            nm = p_.get("名") or p_.get("name")
            if nm:
                in_pack.add(nm)
                # ★ 归一化后再比 —— 2026-11-03 修正:
                #   in_file 里的名是 norm_pian 归一过的(金匮本「辨太阳病形证治上第三」
                #   → 「辨太阳病脉证并治上」),而产出篇目用原文名,直接比会假阳性。
                #   金匮本基线因此被误判为 11/12。
                in_pack.add(RS.norm_pian(nm))
        lost_pian = [nm for nm in in_file if nm not in in_pack]
        # 独有序里出现该篇名的也算有落点。
        # ★ 用**原文篇题**去独有序里找 —— 归一化后的名在原文里不存在
        #   (原文是「形证治上第三」,归一后是「脉证并治上」)。
        #   目录行若在「正文起点」之前,内容进 front 独立单元,原文自然出现在独有序里。
        if lost_pian:
            alltxt = json.dumps(d.get("独有", []), ensure_ascii=False)
            lost_pian = [nm for nm in lost_pian
                         if nm not in alltxt and raw_of.get(nm, nm) not in alltxt]
        add("篇目标题均有落点", not lost_pian,
            f"转录件 {len(in_file)} 篇,产出覆盖 {len(in_file)-len(lost_pian)} 篇"
            + (f";漏: {lost_pian[:6]}" if lost_pian else ""))
    except Exception as e:
        warn(f"篇目标题覆盖检查未执行:{e}")

    # 8-9 记号一致性
    merrs, mwarns = check_marks(txt)
    mix = [e for e in merrs if "混用" in e]
    add("重文号写法不混用", not mix, mix[0] if mix else "々/〻 未混用")
    iso = [e for e in merrs if "孤立" in e]
    add("重文号不孤立", not iso,
        (f"{len(iso)} 处孤立:" + "; ".join(iso[:4])) if iso else "无孤立 々")
    warns += mwarns

    # W2 圈码 ↔ 脚注
    try:
        from . import align as AL
        recs = AL.version_lines(src)
        warns += check_marks_vs_feet(recs)
    except Exception as e:            # 不因附加检查失败而阻塞交付
        warn(f"圈码↔脚注检查未执行:{e}")

    st = d.get("统计", {})
    add("统计字段齐全", all(k in st for k in ("对上条数", "独立内容", "方剂数", "待复核")),
        json.dumps(st, ensure_ascii=False))
    return rows, warns


def main():
    pkg = sys.argv[1]
    rows, warns = check(pkg)
    print(f"=== DoD 自检:{pkg}")
    for name, mark, detail in rows:
        print(f"  {mark} {name}: {detail}")
    if warns:
        print(f"\n  ⚠️ 警告 {len(warns)} 项(不阻塞交付,但总装会看):")
        for w in warns:
            print(f"     - {w}")
    fail = [r for r in rows if r[1] == "❌"]
    print(f"\n{len(rows) - len(fail)}/{len(rows)} 通过"
          + (f",{len(warns)} 项警告" if warns else ""))
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
