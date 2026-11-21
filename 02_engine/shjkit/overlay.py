#!/usr/bin/env python3
"""人工裁定叠加层(引擎内模块)。

**为什么要有这一层**
引擎做自动对齐,承接人做逐条定性 —— 两者都要,顺序是「引擎跑主干,人工裁定按条号覆盖」。
但人工裁定原先直接写进 `交付/版本包.json`,而 `pkgbuild` 每次运行都会**覆盖**这个文件 ——
于是承接人一跑自检,人工裁定就被冲掉(H 包实测:114 条 → 82 条,是倒退)。

**新机制(三个文件各司其职)**
  交付/版本包.json      引擎产出,pkgbuild 写,可随时重跑覆盖
  交付/人工裁定.json    承接人填的裁定,**引擎绝不碰**
  交付/最终版本包.json  overlay 产物 = 引擎 + 人工裁定,verify 与总装读这个

兼容:包内没有 `人工裁定.json` 时,overlay 直接跳过,`最终版本包.json` = `版本包.json` 副本。
旧包零破坏。

**叠加规则(总装口径,2026-10-31 追认)**
  回传条目 状态=有                      → 全字段覆盖(人工裁定优先)
  回传条目 状态=无 且 原因≠暂未匹配      → 覆盖(有依据的「此版无」裁定)
  回传条目 状态=无 且 原因=暂未匹配      → **只是没查清,不是裁定结论**;
                                          若引擎自动匹配上了,保留引擎结果
  独有    引擎独有 + 人工独有,按 (页,文本) 去重后重排 ID
  方剂    引擎方剂 + 人工方剂,按名称去重
"""
import json
import os
import re
import shutil
import sys

__all__ = ["overlay_pkg", "load", "merge_entries", "merge_indep", "merge_fang",
           "sync_review"]


def load(p):
    return json.load(open(p, encoding="utf-8"))


def merge_entries(eng_items, ret_items, lo=None, hi=None):
    """按条号合并引擎条目与人工裁定条目。"""
    by_no = {}
    for r in ret_items:
        by_no.setdefault(r["条号"], r)
    out = []
    for e in eng_items:
        e = dict(e)
        no = e["条号"]
        in_range = (lo is None or no >= lo) and (hi is None or no <= hi)
        r = by_no.get(no)
        if r is not None and in_range:
            rstat = r.get("状态")
            rrsn = r.get("原因")
            if rstat == "有" or (rstat == "无" and rrsn != "暂未匹配"):
                for k, v in r.items():
                    if k != "条号":
                        e[k] = v
        out.append(e)
    return out


def merge_indep(eng, ret, vname):
    """合并独有序并重排 ID(两源 ID 都从 0001 编,直接合并必重复)。"""
    seen, out = set(), []
    for u in list(eng) + list(ret):
        k = (u.get("页"), (u.get("文本") or "").strip()[:60])
        if k in seen:
            continue
        seen.add(k)
        u = dict(u)
        u["iid"] = f"{vname}-独-{len(out)+1:04d}"
        out.append(u)
    return out


# 「伪目」约定:承接人核对后判定**不成立**的方名(上一轮引擎启发式抽取的
# 截断/粘连碎片,如「散三方寸匙纳汤」「枝当归牡丹皮桃仁枳实汤」)。
# 人工裁定里以 归属="伪目(已删)" 标出 —— 总装必须剔除,否则方剂总数虚高、
# 「本版独有几方」算错。2026-11-03 桂林古本包实测 26 个。
FAKE_FANG = "伪目(已删)"


def _norm_fang_name(n):
    """方名归一:去掉末尾「方」字后缀。

    引擎抽的方名不带「方」(「桂枝汤」),承接人转录时常带(「麻黄汤方」)。
    不归一会让同一首方在方剂对照表里被当成两首 —— 桂林古本 328 个人工方名
    全部带「方」字,与机器的 354 个无一能对上。
    归一后仍以「首见者」为准,冲突时保留两条并记名。
    """
    if not isinstance(n, str):
        return n
    n2 = re.sub(r"方$", "", n).strip()
    return n2 or n


def merge_fang(eng, ret):
    """合并方剂,**人工优先**。

    2026-11-03 修正:原先「引擎在前、人工在后」按名称去重,同名时**引擎的会留下**,
    人工修正(改组成、改页码)就被丢掉了 —— 唐本因此从 137 首掉到 110 首,是倒退。
    改为:人工的同名项**替换**引擎项;人工独有的追加在后。

    同批修正:
      ① 剔除 归属=="伪目(已删)" 的条目(承接人判定为不成立的方名)
      ② 方名归一(去末尾「方」),并把原名存进 `原名` 便于追溯
    """
    # 先收集「伪目」方名 —— 这是**按名否决**,不是按条删除:
    # 引擎侧同样存在这些垃圾方(如「三物小陷胸汤」的组成竟是文蛤散药味),
    # 若只删人工侧那条,引擎侧的会留下来,方剂总数照样虚高。
    fake_names = set()
    for f in ret:
        if f.get("归属") == FAKE_FANG:
            raw = f.get("方名") or f.get("名") or f.get("name")
            if isinstance(raw, str):
                fake_names.add(_norm_fang_name(raw))
    out, pos = [], {}
    for f in list(eng) + list(ret):
        raw = f.get("方名") or f.get("名") or f.get("name") or json.dumps(f, sort_keys=True)
        nm = _norm_fang_name(raw)
        if f.get("归属") == FAKE_FANG or nm in fake_names:
            continue                       # 伪目:不计入方剂表(引擎侧同样剔除)
        if nm in pos:
            out[pos[nm]] = f              # 后来的(含人工)覆盖先来的
        else:
            pos[nm] = len(out)
            out.append(f)
    # 记录原名,便于回溯人工写法
    for f in out:
        raw = f.get("方名") or f.get("名") or f.get("name")
        if isinstance(raw, str) and raw != _norm_fang_name(raw):
            f.setdefault("原名", raw)
    return out


def sync_review(pkg, items):
    """按叠加后的置信重写 `交付/待复核.md`(否则 verify 判「低置信未列入待复核」)。"""
    rows = []
    for e in items:
        if e.get("状态") != "有":
            continue
        cf = e.get("置信")
        if cf not in ("低置信", "中置信"):
            continue
        txt = (e.get("原文") or e.get("宋本") or "")
        if isinstance(txt, list):
            txt = " ".join(str(x) for x in txt)
        rows.append((e["条号"], cf, e.get("页") or "", str(txt)[:60]))
    L = ["# 待复核", "",
         f"> 人工裁定后仍为中置信 / 低置信的条目,共 **{len(rows)}** 条。", "",
         "| 条号 | 置信 | 页 | 摘要 |", "|---|---|---|---|"]
    for no, cf, pg, t in rows:
        L.append(f"| {no} | {cf} | {pg} | {t} |")
    L += ["", "---", "",
          "> 复核要点:① 与宋本核对是否确为同一条;② 差异是异体字/通假还是内容不同;",
          "> ③ 若确认是本版独有内容,请移入《本版独有.md》并给独立章节 ID。"]
    with open(f"{pkg}/交付/待复核.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return len(rows)


def overlay_pkg(pkg_dir, lo=None, hi=None, verbose=True):
    """把 `交付/人工裁定.json` 叠加到引擎产出上,写 `交付/最终版本包.json`。

    返回 (统计, 说明)。包内无人工裁定文件时,最终版 = 引擎版副本(说明里注明)。
    """
    eng_p = f"{pkg_dir}/交付/版本包.json"
    fin_p = f"{pkg_dir}/交付/最终版本包.json"
    hum_p = f"{pkg_dir}/交付/人工裁定.json"

    if not os.path.exists(eng_p):
        raise SystemExit(f"✗ 缺引擎产出 {eng_p} —— 先跑 pkgbuild")

    E = load(eng_p)
    if not os.path.exists(hum_p):
        shutil.copy2(eng_p, fin_p)
        if verbose:
            print("ℹ  没有《交付/人工裁定.json》—— 本轮无人工裁定,最终版 = 引擎版")
        return E.get("统计", {}), "无人工裁定(最终版 = 引擎版)"

    H = load(hum_p)
    items = merge_entries(E["条目"], H.get("条目", []), lo, hi)
    indep = merge_indep(E.get("独有", []), H.get("独有", []),
                        E.get("版本名") or "")
    fang = merge_fang(E.get("方剂", []) or [], H.get("方剂", []) or [])

    have = [e for e in items if e.get("状态") == "有"]
    hi_c = sum(1 for e in have if e.get("置信") in ("高置信", "校记锚点"))
    reasons = {}
    for e in items:
        if e.get("状态") == "无":
            reasons[e.get("原因", "—")] = reasons.get(e.get("原因", "—"), 0) + 1

    stat = dict(E.get("统计", {}))
    stat.update({"对上条数": len(have), "高置信": hi_c,
                 "独立内容": len(indep), "方剂数": len(fang)})
    stat.update(reasons)
    # ★ 待复核计数必须与叠加后的置信一致 —— 2026-11-03 修正:
    #   pkgbuild 的「待复核」是引擎层的值,叠加人工裁定后置信变了却没同步,
    #   出现「统计.待复核=64 而实际中低置信=38」的矛盾。
    n_review = sum(1 for e in have if e.get("置信") in ("低置信", "中置信"))
    stat["待复核"] = n_review

    out = dict(E)
    out.update({"条目": items, "独有": indep, "方剂": fang,
                "原因分布": reasons, "统计": stat,
                "_叠加说明": {
                    "人工裁定来源": "交付/人工裁定.json",
                    "采用人工裁定的条号范围": "全部" if lo is None else f"{lo}–{hi}",
                    "叠加日期": "2026-11-03",
                }})
    json.dump(out, open(fin_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sync_review(pkg_dir, items)

    if verbose:
        print(f"✅ 人工裁定已叠加:对上{len(have)} 高{hi_c} 独立{len(indep)} "
              f"方剂{len(fang)} 待复核{n_review}")
    return stat, "已叠加人工裁定"


def main():
    if len(sys.argv) < 2:
        print("用法: python3 -m shjkit.overlay <版本包目录> [条号下限] [条号上限]")
        return 2
    pkg = sys.argv[1].rstrip("/")
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else None
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else None
    overlay_pkg(pkg, lo, hi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
