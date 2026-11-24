#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""伤寒杂病论 · 双站点索引编译器

两套站点，同一份 L1 骨架，区别只在「有没有注文」：

    gujia/    骨架版：各版原文逐条对照，不含任何注文
              index.html + data/{shanghan,jingui,zones,manifest}.json
    zhushi/   注释版：骨架版 + L2 注释本（41_注释本对比/*/notes.json）
              index.html + data/{shanghan,jingui,zones,manifest}.json
    index.html 根落地页（两个入口，纯静态，无数据）

两层不许串（AGENTS.md 铁律一）：
  · gujia 的数据**剥掉** L1 里历史遗留的 notes（372 条成无己注，属 L2 混写）。
    信息不丢——同一批注在 zhushi 里以 chengwuji 注本出现，且已补到 395 条。
  · zhushi 的注文只从 41_注释本对比/ 取，不回写 L1 源文件。源数据全程只读。

注文数据结构（写进 zones.json 的每个 zone）：

    "zhub": [{"id","name","targets","n","cover","status","base","source"}, ...]
    "zhu":  {"<骨架条号>": [{"b":注本序号, "t":正文, "pg":页码?, "seg":段号?, "attr":语气归属?}, ...]}

  b   = zhub 数组下标。注文的「所注版本」记在 zhub[b].targets，不逐条重复
        —— 实测 9 部注本内部 targets 完全一致，逐条存等于冗余 2682 次。
  n   = L1 骨架条号，绝不新建编号空间。
  顺序 = 按 ZHU_ORDER（成无己 → 柯琴 → 尤怡 → 黄元御 → 今人），不按文件名。

用法：
    python3 tools/build_index.py --check    # 只检查，有变化退出码 2
    python3 tools/build_index.py            # 有变化才编译；无变化跳过
    python3 tools/build_index.py --force    # 强制重编译
    python3 tools/build_index.py --site zhushi --force   # 只重编一个站
    python3 tools/build_index.py --json     # 机器可读输出

判定「是否更新」：源数据规范化 sha256、L2 注文 sha256、data 文件 sha、index.html sha，
任一不符 → 需要编译。源数据只读，本工具不改 34/38/41 任何文件。
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

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(B, "02_engine")
SH_SRC = os.path.join(B, "50_data", "52_l1_assembly", "shanghan", "viewer_data.json")
JG_SRC = os.path.join(B, "50_data", "52_l1_assembly", "jingui", "viewer_data.json")
L2 = os.path.join(B, "50_data", "51_notes")
LANDING = os.path.join(B, "90_out", "index.html")
BUILDER_VERSION = "2.0"

SITES = ("gujia", "zhushi")
SITE_DIR = {k: os.path.join(B, "90_out", k) for k in SITES}
TITLES = {
    "gujia": "《伤寒杂病论》多版本对照",
    "zhushi": "《伤寒杂病论》注释本对照",
}
ZONE_NAME = {"shanghan": "伤寒论", "jingui": "金匮要略"}

# 注本按「所注版本」落区。宋本 → SH，赵开美本 → JG。两个编号空间不许混。
ZONE_OF_TARGET = {"宋本": "shanghan", "赵开美本": "jingui"}

# 注本显示顺序：成无己(1144) → 柯琴(1674) → 尤怡(1729) → 黄元御(1750s) → 今人(2007-2010)。
# 新增注本在此登记；未登记者按 id 排在末尾（不静默丢弃）。
ZHU_ORDER = [
    "chengwuji", "keqin", "youyi",
    "huangyuanyu_sh", "huangyuanyu_jg",
    "huxishu", "haowanshan", "liyangbo", "nihaixia",
]


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


# ── L1：剥掉历史遗留的 L1/L2 混写 ───────────────────────────────────────────
def strip_l1(d):
    """viewer_data 的 notes 字段是 SH 侧 372 条成无己注，属 L2 数据混进 L1。

    gujia 不要注文，zhushi 的注文统一从 41_注释本对比 取（chengwuji 395 条，更全），
    两边都不该再读这个字段，否则同一条会出现「372 版」和「395 版」两套注，读者无从分辨。
    """
    d2 = copy.deepcopy(d)
    d2.pop("notes", None)
    return d2


# ── L2：读注本、校验、按骨架条号挂上 ─────────────────────────────────────────
def load_l2(expect):
    """返回 {zone: {"zhub": [...], "zhu": {...}, "errors": [...]}}

    expect = {"shanghan": 398, "jingui": 465}，用于校验条号是否落在骨架内。
    """
    errors = []
    found = {}
    for name in sorted(os.listdir(L2)):
        d = os.path.join(L2, name)
        mp, np_ = os.path.join(d, "manifest.json"), os.path.join(d, "notes.json")
        if not (os.path.isfile(mp) and os.path.isfile(np_)):
            continue
        mf, notes = jload(mp), jload(np_)
        if not notes:
            continue                      # _模板 之类，空库不登记
        targets = mf.get("targets") or []
        zone = ZONE_OF_TARGET.get(targets[0] if targets else "")
        if not zone:
            errors.append(f"{name}: targets={targets} 无法映射到 SH/JG（只认 宋本 / 赵开美本）")
            continue
        tiao = [x for x in notes if (x.get("scope") or "tiao") == "tiao"]
        biji = [x for x in notes if (x.get("scope") or "tiao") != "tiao"]
        bad = [x.get("n") for x in tiao if not isinstance(x.get("n"), int)
               or not (1 <= int(x["n"]) <= expect[zone])]
        if bad:
            errors.append(f"{name}: {len(bad)} 条条号越界或非整数（{bad[:6]}…），该区共 {expect[zone]} 条")
            continue
        bad_biji = [i + 1 for i, x in enumerate(biji)
                    if x.get("n") is not None or not (x.get("title") or "").strip()
                    or ((x.get("scope") or "") == "pian" and not (x.get("pian") or "").strip())]
        if bad_biji:
            errors.append(f"{name}: {len(bad_biji)} 篇笔记字段不全（n 须 null、title 必填、pian 须有篇名）")
            continue
        for x in notes:
            vs = x.get("versions") or []
            if vs and vs != targets:
                errors.append(f"{name}: 条 {x.get('n') or x.get('title')} 的 versions={vs} 与 manifest.targets={targets} 不一致")
                break
        found[name] = {"mf": mf, "notes": notes, "zone": zone, "targets": targets}

    order = [k for k in ZHU_ORDER if k in found] + \
            [k for k in sorted(found) if k not in ZHU_ORDER]
    out = {z: {"zhub": [], "zhu": {}, "biji": [], "errors": errors}
           for z in ("shanghan", "jingui")}
    for idx, name in enumerate(order):
        f = found[name]
        mf, zone = f["mf"], f["zone"]
        b = len(out[zone]["zhub"])
        tiao = [x for x in f["notes"] if (x.get("scope") or "tiao") == "tiao"]
        biji = [x for x in f["notes"] if (x.get("scope") or "tiao") != "tiao"]
        cov = sorted({int(x["n"]) for x in tiao})
        out[zone]["zhub"].append({
            "id": name,
            "name": mf.get("name") or name,
            "targets": f["targets"],
            "n": len(tiao),
            "biji": len(biji),
            "cover": mf.get("覆盖") or mf.get("覆盖率") or f"{len(cov)}/{expect[zone]}",
            "status": mf.get("status") or "",
            "base": mf.get("base") or "",
            "source": mf.get("source") or "",
        })
        for x in tiao:
            r = {"b": b, "t": x.get("text") or ""}
            if x.get("pg") is not None:
                r["pg"] = x["pg"]
            if x.get("seg"):
                r["seg"] = x["seg"]
            if x.get("attr"):
                r["attr"] = x["attr"]
            out[zone]["zhu"].setdefault(str(int(x["n"])), []).append(r)
        for x in biji:
            r = {"b": b, "t": x.get("text") or "",
                 "title": x.get("title") or "",
                 "scope": x.get("scope") or "pian"}
            if x.get("pian"):
                r["pian"] = x["pian"]
            if x.get("pg") is not None:
                r["pg"] = x["pg"]
            if x.get("seg"):
                r["seg"] = x["seg"]
            if x.get("attr"):
                r["attr"] = x["attr"]
            out[zone]["biji"].append(r)
    return out


def l2_digest(l2):
    """注文指纹：只取内容，不含 errors 字段。"""
    return digest({z: {"zhub": l2[z]["zhub"], "zhu": l2[z]["zhu"], "biji": l2[z]["biji"]}
                   for z in ("shanghan", "jingui")})


# ── 组包 ────────────────────────────────────────────────────────────────────
def zone_of(d, forced_name=None):
    d2 = copy.deepcopy(d)
    d2["nVers"] = len(d2.get("vers") or [])
    sid = (d2.get("skel") or {}).get("id") or "one"
    d2["baseLabel"] = d2.get("baseLabel") or ("宋本" if sid == "shanghan" else "赵开美本1599")
    nm = forced_name or ZONE_NAME.get(sid, sid)
    return {
        "id": sid.upper(),
        "name": nm,
        "title": f"《{nm}》多版本对照",
        "sub": f"{d2.get('expect')} 条 × {d2['nVers']} 版"
               + (f" · 注本 {len(d2['zhub'])} 部" if d2.get("zhub") else ""),
        "data": d2,
    }


def build_zones(packs, kind):
    zs = [zone_of(packs["shanghan"]), zone_of(packs["jingui"])]
    zs[0]["title"] = TITLES[kind]
    return zs


def make_html(out_path, title):
    """调 htmlbuild 生成内嵌版，再把内嵌数据换成 fetch 标记。

    先内嵌再剥离，是为了拿到唯一一份模板；htmlbuild 是模板的唯一定义处，
    这里不许复制粘贴一份 HTML 到本文件里（AGENTS.md 规矩 12）。
    """
    tmp = out_path + ".tmp.html"
    cmd = [sys.executable, "-m", "shjkit.htmlbuild", "--zones", f"{SH_SRC},{JG_SRC}", tmp]
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
    html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>",
                  html, count=1, flags=re.S)
    open(out_path, "w", encoding="utf-8").write(html)
    return out_path


def payloads():
    sh, jg = jload(SH_SRC), jload(JG_SRC)
    expect = {"shanghan": len(sh["items"]), "jingui": len(jg["items"])}
    l2 = load_l2(expect)
    errs = l2["shanghan"]["errors"] + l2["jingui"]["errors"]
    if errs:
        print("L2 注文校验未通过：", file=sys.stderr)
        for e in errs[:20]:
            print("  · " + e, file=sys.stderr)
        print("先修数据再编译。注文挂错条比少几部注本坏得多。", file=sys.stderr)
        sys.exit(1)

    gu = {"shanghan": strip_l1(sh), "jingui": strip_l1(jg)}
    zs = {}
    for z, src in (("shanghan", sh), ("jingui", jg)):
        d = strip_l1(src)
        d["zhub"] = l2[z]["zhub"]
        d["zhu"] = l2[z]["zhu"]
        d["biji"] = l2[z]["biji"]
        zs[z] = d
    return {"gujia": gu, "zhushi": zs}, l2


def manifest_of(kind, packs, l2):
    man = {
        "builder": f"tools/build_index.py v{BUILDER_VERSION}",
        "site": kind,
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "packages": {},
    }
    for k, src in (("shanghan", SH_SRC), ("jingui", JG_SRC)):
        d = packs[k]
        st = stat(d)
        p2 = os.path.join(SITE_DIR[kind], "data", f"{k}.json")
        man["packages"][k] = {
            "name": ZONE_NAME[k], "source": os.path.relpath(src, B), **st,
            "data": f"data/{k}.json", "data_sha256": fsha(p2),
            "data_bytes": os.path.getsize(p2),
            "注本": len(d.get("zhub") or []),
        }
    zpath = os.path.join(SITE_DIR[kind], "data", "zones.json")
    man["packages"]["heji"] = {
        "name": "伤寒杂病论", "zones": ["shanghan", "jingui"],
        "data": "data/zones.json", "data_sha256": fsha(zpath),
        "data_bytes": os.path.getsize(zpath),
    }
    idx = os.path.join(SITE_DIR[kind], "index.html")
    man["index"] = {"file": "index.html", "sha256": fsha(idx),
                    "bytes": os.path.getsize(idx), "mode": "fetch"}
    if kind == "zhushi":
        man["l2"] = {
            "source": "50_data/51_notes/*/{manifest,notes}.json",
            "sha256": l2_digest(l2),
            "注本数": sum(len(l2[z]["zhub"]) for z in ("shanghan", "jingui")),
            "注文条": sum(len(v) for z in ("shanghan", "jingui") for v in l2[z]["zhu"].values()),
            "笔记篇": sum(len(l2[z]["biji"]) for z in ("shanghan", "jingui")),
            "覆盖条": {z: len(l2[z]["zhu"]) for z in ("shanghan", "jingui")},
        }
    return man


def landing_html(mans):
    """根落地页。数字从各站 manifest 现取，不手写。"""
    def card(kind, label, desc, extra=""):
        m = mans.get(kind) or {}
        pk = m.get("packages") or {}
        sh, jg = pk.get("shanghan") or {}, pk.get("jingui") or {}
        nums = (f'条 {int(sh.get("条数",0))+int(jg.get("条数",0))}'
                f'（{sh.get("条数","?")} + {jg.get("条数","?")}）· '
                f'版 {int(sh.get("版本数",0))+int(jg.get("版本数",0))}'
                f'（{sh.get("版本数","?")} + {jg.get("版本数","?")}）')
        return f"""    <a class="card" href="{kind}/index.html">
      <div class="k">{label}</div>
      <div class="d">{desc}</div>
      <div class="n">{nums}{extra}</div>
      <div class="go">进入 →</div>
    </a>"""

    zs = (mans.get("zhushi") or {}).get("l2") or {}
    extra = (f'<br>注本 {zs.get("注本数","?")} 部 · 注文 {zs.get("注文条","?")} 条 · 笔记 {zs.get("笔记篇","?")} 篇'
             if zs else "")
    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>《伤寒杂病论》对照</title>
<style>
:root{{--paper:#f6f2ea;--panel:#fffdf8;--ink:#262219;--ink2:#5d564a;--ink3:#8d8577;
  --line:#ddd5c6;--line2:#c9bfa9;--zhu:#9c3524;--gold:#b07d1f;
  --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
  --serif:"Songti SC","STSong","Source Han Serif SC","Noto Serif CJK SC",serif;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--paper);color:var(--ink);font-family:var(--serif);
  min-height:100vh;display:flex;flex-direction:column;justify-content:center;
  align-items:center;padding:40px 20px}}
h1{{font-size:26px;letter-spacing:2px;font-weight:700}}
.sub{{font-family:var(--sans);font-size:12.5px;color:var(--ink3);margin:10px 0 34px;
  text-align:center;line-height:1.9}}
.cards{{display:flex;gap:18px;flex-wrap:wrap;justify-content:center;max-width:820px}}
.card{{display:block;width:340px;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;padding:22px 24px;text-decoration:none;color:inherit;
  transition:border-color .15s,transform .15s,box-shadow .15s}}
.card:hover{{border-color:var(--gold);transform:translateY(-2px);
  box-shadow:0 6px 20px rgba(0,0,0,.06)}}
.card .k{{font-size:19px;font-weight:700;letter-spacing:1px;color:var(--zhu)}}
.card .d{{font-size:14px;color:var(--ink2);margin-top:8px;line-height:1.8}}
.card .n{{font-family:var(--sans);font-size:11.5px;color:var(--ink3);margin-top:14px;line-height:1.9}}
.card .go{{font-family:var(--sans);font-size:12px;color:var(--gold);margin-top:12px}}
footer{{font-family:var(--sans);font-size:11px;color:var(--ink3);margin-top:36px;text-align:center;
  line-height:1.9}}
a.plain{{color:var(--ink2)}}
</style>
</head>
<body>
  <h1>《伤寒杂病论》对照</h1>
  <div class="sub">两套独立编号空间：SH《伤寒论》398 条 / JG《金匮要略》465 条，<br>
    同号不对应；顶部切换，两边都是同一条文的多版本并列。</div>
  <div class="cards">
{card("gujia", "骨架版", "各版原文逐条对照。异文处用黄底高亮标出，只放原文，不放注文。")}
{card("zhushi", "注释本", "在骨架版之上叠加历代注本注文，按骨架条号对位，与原文并列。", extra)}
  </div>
  <footer>数据由 <code>tools/build_index.py</code> 生成，勿手改。<br>
    需通过 http(s) 访问，<code>file://</code> 下浏览器拒绝 fetch 数据。</footer>
</body>
</html>
"""


# ── 编译 / 判定 ─────────────────────────────────────────────────────────────
def build_site(kind, packs, l2):
    site = SITE_DIR[kind]
    data = os.path.join(site, "data")
    os.makedirs(data, exist_ok=True)
    for k in ("shanghan", "jingui"):
        json.dump(packs[k], open(os.path.join(data, f"{k}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
    zones = build_zones(packs, kind)
    json.dump(zones, open(os.path.join(data, "zones.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    make_html(os.path.join(site, "index.html"), TITLES[kind])
    man = manifest_of(kind, packs, l2)
    json.dump(man, open(os.path.join(data, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return man


def site_state(kind, packs, l2):
    """返回 (need, detail)。need = 源/数据/页面任一与 manifest 不符。"""
    mpath = os.path.join(SITE_DIR[kind], "data", "manifest.json")
    old = jload(mpath) if os.path.exists(mpath) else None
    det = {"kind": kind, "old": old is not None, "reasons": []}
    if old is None:
        det["reasons"].append("无 manifest")
        return True, det
    for k in ("shanghan", "jingui"):
        cur = stat(packs[k])["sha256"]
        rec = (old.get("packages") or {}).get(k) or {}
        if cur != rec.get("sha256"):
            det["reasons"].append(f"{k} 源数据变")
        df = os.path.join(SITE_DIR[kind], "data", f"{k}.json")
        if not os.path.exists(df) or fsha(df) != rec.get("data_sha256"):
            det["reasons"].append(f"{k}.json 缺或变")
    for f, key in (("zones.json", "heji"), ("manifest.json", None)):
        if key is None:
            continue
        p = os.path.join(SITE_DIR[kind], "data", f)
        if not os.path.exists(p) or fsha(p) != ((old.get("packages") or {}).get(key) or {}).get("data_sha256"):
            det["reasons"].append("zones.json 缺或变")
    ip = os.path.join(SITE_DIR[kind], "index.html")
    if not os.path.exists(ip) or fsha(ip) != ((old.get("index") or {}).get("sha256")):
        det["reasons"].append("index.html 缺或变")
    if kind == "zhushi" and l2_digest(l2) != ((old.get("l2") or {}).get("sha256")):
        det["reasons"].append("L2 注文变")
    return bool(det["reasons"]), det


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查，不写文件；需编译时退出码 2")
    ap.add_argument("--force", action="store_true", help="强制重编译")
    ap.add_argument("--site", choices=list(SITES) + ["all"], default="all")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    a = ap.parse_args()

    for p in (SH_SRC, JG_SRC):
        if not os.path.exists(p):
            print(f"缺少源数据：{p}", file=sys.stderr)
            return 1

    packs, l2 = payloads()
    kinds = list(SITES) if a.site == "all" else [a.site]

    todo, rows = [], []
    for kind in kinds:
        need, det = site_state(kind, packs[kind], l2)
        rows.append({"site": kind, "need": need, "reasons": det["reasons"]})
        if need:
            todo.append(kind)

    if a.json:
        print(json.dumps({"need_build": todo, "sites": rows}, ensure_ascii=False, indent=1))
    else:
        print(f"{'站点':<8} {'条数':>5} {'版本':>4} {'注本':>4} {'注文':>6}  状态")
        for r in rows:
            kind = r["site"]
            p = packs[kind]
            ng = len(p["shanghan"].get("zhub") or []) + len(p["jingui"].get("zhub") or [])
            nz = sum(len(v) for z in ("shanghan", "jingui")
                     for v in (p[z].get("zhu") or {}).values())
            st = ("★ 需重编译（" + "、".join(r["reasons"]) + "）") if r["need"] else "未变"
            print(f"{kind:<8} {len(p['shanghan']['items'])+len(p['jingui']['items']):>5} "
                  f"{len(p['shanghan']['vers'])+len(p['jingui']['vers']):>4} {ng:>4} {nz:>6}  {st}")
        print()
        print("结论：" + ("强制重编译" if a.force
                        else (f"需要编译 {todo}" if todo else "已是最新，无需编译")))

    if a.check:
        return 2 if todo else 0
    if not todo and not a.force:
        return 0

    mans = {}
    for kind in (kinds if a.force else todo):
        man = build_site(kind, packs[kind], l2)
        mans[kind] = man
        print(f"已编译 {kind}/index.html {man['index']['bytes']/1024:.1f} KB"
              f" · data/zones.json {man['packages']['heji']['data_bytes']/1048576:.1f} MB"
              + (f" · 注本 {man['l2']['注本数']} 部 / 注文 {man['l2']['注文条']} 条 / 笔记 {man['l2'].get('笔记篇',0)} 篇"
                 if kind == "zhushi" else ""))

    # 落地页：数字取两站 manifest（新编的用内存里的，没重编的读盘）
    for kind in SITES:
        if kind not in mans:
            p = os.path.join(SITE_DIR[kind], "data", "manifest.json")
            if os.path.exists(p):
                mans[kind] = jload(p)
    if len(mans) == len(SITES):
        open(LANDING, "w", encoding="utf-8").write(landing_html(mans))
        print(f"已编译 index.html（落地页）{os.path.getsize(LANDING)/1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
