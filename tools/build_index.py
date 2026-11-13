#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""伤寒杂病论 · 三包索引编译器

把三个数据包编译成 GitHub Pages 可直接 fetch 的站点：

    index.html            只含模板（约 50 KB），数据靠 fetch('data/zones.json')
    data/shanghan.json    伤寒论       398 条 × 9 版
    data/jingui.json      金匮要略     465 条 × 4 版
    data/zones.json       伤寒杂病论   双区合并（index.html 用这个）
    data/manifest.json    三包 sha256 / 统计 / 生成时间（判断是否更新就看它）

用法：
    python3 tools/build_index.py --check    # 只检查，有变化退出码 2
    python3 tools/build_index.py            # 有变化才编译；无变化跳过
    python3 tools/build_index.py --force    # 强制重编译
    python3 tools/build_index.py --json     # 机器可读输出

判定「是否更新」：源 viewer_data 的规范化 sha256、data 文件 sha、index.html sha
三者任一不符 → 需要编译。源数据只读，本工具不改 34/38 任何文件。
"""
import argparse
import copy
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(B, "00_公共地基", "引擎")
SH = os.path.join(B, "34_总装产出_v0.12.0", "viewer_data.json")
JG = os.path.join(B, "38_总装产出_金匮_v0.2.0", "viewer_data.json")
DATA = os.path.join(B, "data")
INDEX = os.path.join(B, "index.html")
MANIFEST = os.path.join(DATA, "manifest.json")
BUILDER_VERSION = "1.0"


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def digest(obj):
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def fsha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def stat(d):
    return {
        "条数": len(d.get("items") or []),
        "版本数": len(d.get("vers") or []),
        "review": len(d.get("review") or []),
        "异文条": sum(1 for it in d.get("items") or []
                   if any("【" in (c.get("d") or "") for c in (it.get("v") or {}).values())),
        "sha256": digest(d),
    }


def zone_of(d, forced_name=None):
    d2 = copy.deepcopy(d)
    d2["nVers"] = len(d2.get("vers") or [])
    sid = (d2.get("skel") or {}).get("id") or "one"
    d2["baseLabel"] = d2.get("baseLabel") or ("宋本" if sid == "shanghan" else "赵开美本1599")
    nm = forced_name or {"shanghan": "伤寒论", "jingui": "金匮要略"}.get(sid, sid)
    return {
        "id": sid.upper(),
        "name": nm,
        "title": f"《{nm}》多版本对照",
        "sub": f"{d2.get('expect')} 条 × {d2['nVers']} 版",
        "data": d2,
    }


def build_zones(sh, jg):
    zs = [zone_of(sh), zone_of(jg)]
    zs[0]["title"] = "《伤寒杂病论》多版本对照"
    return zs


def make_html(out_path):
    """调 htmlbuild 生成内嵌版，再把内嵌数据换成 fetch 标记。"""
    tmp = out_path + ".tmp.html"
    cmd = [sys.executable, "-m", "shjkit.htmlbuild", "--zones", f"{SH},{JG}", tmp]
    r = subprocess.run(cmd, cwd=ENGINE, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    html = open(tmp, encoding="utf-8").read()
    os.remove(tmp)
    html, n = re.subn(r"<script>window\.__SHJ_ZONES__ = .*?</script>",
                      "<script>window.__SHJ_FETCH__=1;</script>", html,
                      count=1, flags=re.S)
    if n != 1:
        raise RuntimeError("未能替换内嵌数据脚本，htmlbuild 模板可能变了")
    html = re.sub(r"<title>.*?</title>", "<title>《伤寒杂病论》多版本对照</title>",
                  html, count=1, flags=re.S)
    open(out_path, "w", encoding="utf-8").write(html)
    return out_path


def load_manifest():
    return jload(MANIFEST) if os.path.exists(MANIFEST) else None


def assess():
    """返回 (need, rows, payload)。payload 含三包源数据与统计。"""
    sh, jg = jload(SH), jload(JG)
    pkgs = {"shanghan": {"name": "伤寒论", "src": SH, "d": sh, "file": "shanghan.json"},
            "jingui": {"name": "金匮要略", "src": JG, "d": jg, "file": "jingui.json"}}
    old = load_manifest()
    changed = []
    rows = []
    for k, p in pkgs.items():
        st = stat(p["d"])
        oldsha = ((old or {}).get("packages", {}).get(k) or {}).get("sha256")
        df = os.path.join(DATA, p["file"])
        data_ok = os.path.exists(df) and fsha(df) == ((old or {}).get("packages", {}).get(k) or {}).get("data_sha256")
        ch = old is None or oldsha != st["sha256"] or not data_ok
        if ch:
            changed.append(k)
        rows.append({
            "key": k, "name": p["name"], **{x: st[x] for x in ("条数", "版本数", "review", "异文条")},
            "sha": st["sha256"][:12], "changed": ch, "data_ok": data_ok,
        })
    # 合并包
    zpath = os.path.join(DATA, "zones.json")
    z_ok = os.path.exists(zpath) and os.path.exists(MANIFEST) and \
        fsha(zpath) == ((old or {}).get("packages", {}).get("heji") or {}).get("data_sha256")
    i_ok = os.path.exists(INDEX) and os.path.exists(MANIFEST) and \
        fsha(INDEX) == ((old or {}).get("index") or {}).get("sha256")
    need = bool(changed) or not z_ok or not i_ok or old is None
    rows.append({"key": "heji", "name": "伤寒杂病论", "条数": "—", "版本数": "—",
                 "review": "—", "异文条": "—", "sha": "—",
                 "changed": not z_ok, "data_ok": z_ok})
    rows.append({"key": "index", "name": "index.html", "条数": "—", "版本数": "—",
                 "review": "—", "异文条": "—", "sha": (fsha(INDEX)[:12] if i_ok else "—"),
                 "changed": not i_ok, "data_ok": i_ok})
    return need, rows, {"sh": sh, "jg": jg, "pkgs": pkgs, "old": old}


def build(payload):
    os.makedirs(DATA, exist_ok=True)
    sh, jg, pkgs = payload["sh"], payload["jg"], payload["pkgs"]
    for k, p in pkgs.items():
        p2 = os.path.join(DATA, p["file"])
        json.dump(p["d"], open(p2, "w", encoding="utf-8"), ensure_ascii=False)
    zones = build_zones(sh, jg)
    zpath = os.path.join(DATA, "zones.json")
    json.dump(zones, open(zpath, "w", encoding="utf-8"), ensure_ascii=False)

    make_html(INDEX)

    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    man = {
        "builder": f"tools/build_index.py v{BUILDER_VERSION}",
        "generated": now,
        "packages": {},
        "index": {"file": "index.html", "sha256": fsha(INDEX),
                  "bytes": os.path.getsize(INDEX), "mode": "fetch"},
    }
    for k, p in pkgs.items():
        st = stat(p["d"])
        p2 = os.path.join(DATA, p["file"])
        man["packages"][k] = {
            "name": p["name"], "source": os.path.relpath(p["src"], B),
            **st,
            "data": "data/" + p["file"], "data_sha256": fsha(p2),
            "data_bytes": os.path.getsize(p2),
        }
    man["packages"]["heji"] = {
        "name": "伤寒杂病论", "zones": ["shanghan", "jingui"],
        "data": "data/zones.json", "data_sha256": fsha(zpath),
        "data_bytes": os.path.getsize(zpath),
    }
    json.dump(man, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return man


def print_table(rows, need):
    print(f"{'包':<10} {'条数':>6} {'版本':>4} {'review':>7} {'异文':>6}  {'sha':<12} 状态")
    for r in rows:
        st = "★ 需重编译" if r["changed"] else "未变"
        print(f"{r['name']:<10} {str(r['条数']):>6} {str(r['版本数']):>4} "
              f"{str(r['review']):>7} {str(r['异文条']):>6}  {r['sha']:<12} {st}")
    print()
    print("结论：" + ("需要编译（源数据/数据文件/页面任一变化）" if need else "已是最新，无需编译"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查，不写文件；需编译时退出码 2")
    ap.add_argument("--force", action="store_true", help="强制重编译")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    a = ap.parse_args()

    for p in (SH, JG):
        if not os.path.exists(p):
            print(f"缺少源数据：{p}", file=sys.stderr)
            return 1

    need, rows, payload = assess()
    if a.json:
        print(json.dumps({"need_build": need, "packages": rows}, ensure_ascii=False, indent=1))
    else:
        print_table(rows, need)

    if a.check:
        return 2 if need else 0
    if not need and not a.force:
        return 0

    man = build(payload)
    if a.json:
        print(json.dumps({"built": True, "manifest": man}, ensure_ascii=False, indent=1))
    else:
        print(f"已编译：index.html {os.path.getsize(INDEX)/1024:.1f} KB（fetch 模式）")
        print(f"        data/zones.json {os.path.getsize(os.path.join(DATA,'zones.json'))/1048576:.1f} MB"
              f" / shanghan.json / jingui.json / manifest.json")
        print(f"        index sha256 {man['index']['sha256'][:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
