#!/usr/bin/env python3
"""生成自包含的单文件 HTML 对照浏览器(数据内嵌,离线可用)。

用法:
    python3 -m shjkit.htmlbuild <viewer_data.json> [输出.html]
"""
import json

import sys

from . import skeleton as SK

argv = sys.argv[1:]
SPLIT = "--split" in argv
argv = [a for a in argv if a != "--split"]
SKEL_ID = None
for _flag in ("--骨架", "--skel"):
    if _flag in argv:
        _i = argv.index(_flag)
        SKEL_ID = argv[_i + 1]
        del argv[_i:_i + 2]

_sk = SK.skel_spec(SKEL_ID)
SKEL_NAME = _sk.get('名称', '宋本《伤寒论》398 条')
SKEL_KIND = ('条级顶层 + 条内' + (_sk.get('子层') or '句') + '级下钻层') \
    if _sk.get('分层') else '条级顶层,子层为各版异文分段'

ZONES_ARG = None
for _flag in ("--zones", "--zone"):
    if _flag in argv:
        _i = argv.index(_flag)
        ZONES_ARG = argv[_i + 1]
        del argv[_i:_i + 2]
        break

DATA_PATH = argv[0] if len(argv) > 0 else "/workspace/work/viewer_data.json"
DST = argv[1] if len(argv) > 1 else "/workspace/output/结构化对照/对照浏览器.html"

if ZONES_ARG:
    # 双区模式下位置参数只有一个:输出文件
    DST = argv[0] if len(argv) > 0 else DST
    # 双区:SH(伤寒论) + JG(金匮要略),两个独立编号空间,顶部切换
    _zones = []
    for _p in [x for x in ZONES_ARG.split(",") if x]:
        _d = json.load(open(_p, encoding="utf-8"))
        _d["nVers"] = len(_d.get("vers") or [])
        _sid = (_d.get("skel") or {}).get("id") or "one"
        _d["baseLabel"] = _d.get("baseLabel") or ("宋本" if _sid == "shanghan" else "赵开美本1599")
        _nm = {"shanghan": "伤寒论", "jingui": "金匮要略"}.get(_sid, _sid)
        _zones.append({
            "id": _sid.upper(), "name": _nm,
            "title": "《" + _nm + "》多版本对照",
            "sub": f"{_d.get('expect')} 条 × {_d['nVers']} 版",
            "data": _d,
        })
    DATA = json.dumps(_zones[0]["data"], ensure_ascii=False)
    ZONES_JSON = json.dumps(_zones, ensure_ascii=False).replace("</", "<\\/")
    DATA_TAG = ('<script>window.__SHJ_ZONES__ = ' + ZONES_JSON + ';</script>')
    SKEL_NAME = _zones[0]["data"]["skel"].get("名称", "")
    TITLE = _zones[0]["title"]
else:
    DATA = open(DATA_PATH, encoding="utf-8").read()
    DATA_TAG = None
    TITLE = "《伤寒论》多版本对照"

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --paper:#f6f2ea; --panel:#fffdf8; --ink:#262219; --ink2:#5d564a; --ink3:#8d8577;
  --line:#ddd5c6; --line2:#c9bfa9; --zhu:#9c3524; --qing:#2c5a5f; --gold:#b07d1f;
  --mark:#fbe6bf; --mark2:#f6d79a; --hl:#fff4d6; --ok:#3f6b3f; --warn:#a2621b;
  --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
  --serif:"Songti SC","STSong","Source Han Serif SC","Noto Serif CJK SC",serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:var(--paper);color:var(--ink);font-family:var(--serif);font-size:15px;line-height:1.75;
  -webkit-font-smoothing:antialiased}
button,input,select{font-family:var(--sans);font-size:13px;color:var(--ink)}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:#cdc4b2;border-radius:5px}
::-webkit-scrollbar-track{background:transparent}

header{position:sticky;top:0;z-index:40;background:linear-gradient(180deg,#fffdf8 0%,#f9f5ec 100%);
  border-bottom:1.5px solid var(--line2);box-shadow:0 1px 6px rgba(0,0,0,.05)}
.hd{display:flex;align-items:center;gap:18px;padding:11px 20px}
/* 顶部双区切换:SH 伤寒论 / JG 金匮要略(两个独立编号空间,不是同一本书的两半) */
.zsw{display:flex;gap:0;border:1px solid var(--line2);border-radius:7px;overflow:hidden;
  background:#fff;flex:none}
.zsw button{border:none;background:none;padding:6px 13px;cursor:pointer;font-family:var(--sans);
  font-size:12.5px;color:var(--ink2);letter-spacing:.3px;white-space:nowrap}
.zsw button+button{border-left:1px solid var(--line)}
.zsw button.on{background:var(--zhu);color:#fff;font-weight:600}
.zsw button:not(.on):hover{background:#f6f1e6;color:var(--ink)}
.title{font-size:19px;font-weight:700;letter-spacing:1px;white-space:nowrap}
.title small{font-family:var(--sans);font-size:11px;font-weight:400;color:var(--ink3);letter-spacing:0;margin-left:8px}
.search{flex:1;max-width:420px;position:relative}
.search input{width:100%;padding:7px 30px 7px 32px;border:1px solid var(--line2);border-radius:6px;
  background:#fff;outline:none}
.search input:focus{border-color:var(--gold);box-shadow:0 0 0 3px rgba(176,125,31,.12)}
.search .ic{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--ink3);font-size:13px}
.search .clr{position:absolute;right:8px;top:50%;transform:translateY(-50%);cursor:pointer;color:var(--ink3);
  border:none;background:none;font-size:14px;display:none}
.tabs{display:flex;gap:2px;padding:0 20px}
.tab{border:none;background:none;padding:8px 15px;cursor:pointer;color:var(--ink2);
  border-bottom:2.5px solid transparent;font-size:14px;font-family:var(--serif)}
.tab:hover{color:var(--ink)}
.tab.on{color:var(--zhu);border-bottom-color:var(--zhu);font-weight:700}
.tab .cnt{font-family:var(--sans);font-size:10px;color:var(--ink3);margin-left:4px}

.stat{display:flex;gap:0;padding:9px 20px;border-top:1px solid var(--line);font-family:var(--sans);
  font-size:11.5px;color:var(--ink2);overflow-x:auto;white-space:nowrap}
.stat b{color:var(--ink);font-weight:600}
.stat .u{margin-right:16px;cursor:pointer;padding:2px 6px;border-radius:4px;border:1px solid transparent}
.stat .u:hover{background:#efe8da;border-color:var(--line2)}
.stat .u.on{background:var(--hl);border-color:var(--gold);color:var(--zhu)}

.wrap{display:flex;height:calc(100vh - 118px);align-items:stretch}
aside{width:290px;flex:none;border-right:1px solid var(--line2);overflow-y:auto;background:var(--panel)}
aside .grp{border-bottom:1px solid var(--line)}
aside .gh{padding:8px 13px;font-size:12.5px;font-weight:700;color:var(--zhu);cursor:pointer;
  display:flex;justify-content:space-between;align-items:center;background:#f1ead9;position:sticky;top:0;z-index:2}
aside .gh:hover{background:#ebe1cc}
aside .gh .c{font-family:var(--sans);font-size:10px;color:var(--ink3);font-weight:400}
.it{padding:5px 13px 5px 15px;cursor:pointer;font-size:13px;border-left:3px solid transparent;
  display:flex;justify-content:space-between;gap:6px;align-items:baseline}
.it:hover{background:#f3eee2}
.it.on{background:var(--hl);border-left-color:var(--zhu);font-weight:700}
.it .n{font-family:var(--sans);font-size:11px;color:var(--ink3);min-width:30px}
.it .t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;font-weight:400}
.it.on .t{font-weight:700}
.dots{display:flex;gap:2px;flex:none}
.dot{width:6px;height:6px;border-radius:50%;background:#cfc6b4}
.dot.d{background:var(--gold)}
.dot.a{background:var(--zhu)}

main{flex:1;overflow-y:auto;padding:0 0 60px}
.view{display:none}
.view.on{display:block}
.bar{position:sticky;top:0;z-index:30;background:rgba(246,242,234,.94);backdrop-filter:blur(6px);
  padding:9px 22px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;
  font-family:var(--sans);font-size:12px;color:var(--ink2);flex-wrap:wrap}
.bar select,.bar button{border:1px solid var(--line2);background:#fff;padding:4px 9px;border-radius:5px;cursor:pointer}
.bar button:hover,.bar select:hover{border-color:var(--gold)}
.bar .sp{flex:1}
/* 宽表在窄屏会撑破布局：统一外包一层横向滚动容器 */
.tscroll{max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}
.bar .cb{display:flex;align-items:center;gap:4px;cursor:pointer;user-select:none}
/* 筛选抽屉：默认收起，点「筛选」展开；和看法、计数同一行，不另占一屏 */
.bar .fbox{display:none;flex:1 0 100%;gap:10px;align-items:center;flex-wrap:wrap;
  padding-top:7px;margin-top:1px;border-top:1px dashed var(--line2)}
.bar .fbox.open{display:flex}
.fbtn{border:1px solid var(--line2);background:#fff;padding:4px 10px;border-radius:5px;cursor:pointer;
  font-family:var(--sans);font-size:12px;color:var(--ink2)}
.fbtn.on{background:var(--hl);border-color:var(--gold);color:var(--zhu)}
.chip{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--line2);background:#fff;
  border-radius:10px;padding:1px 8px;font-family:var(--sans);font-size:11.5px;color:var(--ink2)}
.chip b{color:var(--zhu);cursor:pointer}
/* 篇首「本篇笔记」入口：不占正文，给一条可点的窄条 */
.notelink{display:flex;align-items:center;gap:8px;margin:0 0 12px;padding:6px 11px;
  border:1px dashed var(--line2);border-radius:7px;background:#fbf7ee;cursor:pointer;
  font-family:var(--sans);font-size:12px;color:var(--ink2)}
.notelink b{color:var(--zhu)}
.notelink:hover{border-color:var(--gold);background:#f7f0df}
/* 笔记页：按篇分组，卡片比条注略窄 */
.bgroup{margin:18px 0 6px;padding:5px 0 4px;border-bottom:1px solid var(--line);
  font-family:var(--sans);font-size:12px;font-weight:700;color:var(--zhu);letter-spacing:.5px}
.bgroup .c{color:var(--ink3);font-weight:400;margin-left:6px}
.card.biji{border-left:3px solid var(--gold)}
.card.biji .ch .vn{font-size:14px}
.card.biji .cb2{font-size:14px;line-height:1.9}
.wrap2{padding:16px 22px}

.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;margin-bottom:14px;overflow:hidden}
.card .ch{padding:8px 15px;background:#f1ead9;border-bottom:1px solid var(--line);display:flex;
  align-items:center;gap:10px;font-size:13px}
.card .ch .vn{font-weight:700;font-size:14.5px;letter-spacing:.5px}
.card .ch .tag{font-family:var(--sans);font-size:10.5px;padding:1.5px 7px;border-radius:9px;
  border:1px solid;white-space:nowrap}
.t-anch{color:var(--zhu);border-color:#d9b0a8;background:#fbeeeb}
.t-hi{color:var(--ok);border-color:#b6cfb6;background:#eff6ef}
.t-mid{color:var(--warn);border-color:#dcc79a;background:#fbf3e0}
.t-low{color:#7d7666;border-color:var(--line2);background:#f3efe5}
.t-none{color:var(--ink3);border-color:var(--line2);background:#f3efe5}
.t-zhu{color:var(--gold);border-color:#dcc79a;background:#fbf3e0}
.card .cb2{padding:12px 16px;font-size:15px;line-height:1.95;white-space:pre-wrap;word-break:break-word}
/* L2 注文卡（41_注释本对比）：金线区分「注」与「原文」，长文默认折到 10.5 行。
   折叠只靠 max-height，不接管滚动——展开后与原卡片同一套排版，不再套内层滚动容器。 */
.card.zhu{border-left:3px solid var(--gold)}
.card.zhu .ch{background:#f6efdf}
.card.zhu .ch .vn{font-size:13.5px}
/* 折叠高度取整行数（1.9em × 6），否则会切在半行上 */
.card.zhu .ztxt{font-size:14.5px;line-height:1.9;max-height:calc(1.9em * 6);overflow:hidden;position:relative}
.card.zhu.short .ztxt{max-height:none}
.card.zhu.open .ztxt{max-height:none}
.card.zhu .ztxt::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2.4em;
  background:linear-gradient(180deg,rgba(255,253,248,0) 0%,var(--panel) 90%);pointer-events:none}
.card.zhu.short .ztxt::after,.card.zhu.open .ztxt::after{display:none}
/* 展开按钮：居中小胶囊。原来是通栏细条，看着像分隔线不像按钮。 */
.card.zhu .zmore,.card.biji .zmore{display:block;margin:0 auto 12px;border:1px solid var(--line2);
  border-radius:15px;background:#fff;padding:3px 16px;font-size:12px;line-height:1.7;color:var(--zhu);
  cursor:pointer;text-align:center;font-family:var(--sans);box-shadow:0 1px 2px rgba(38,34,25,.05)}
.card.zhu .zmore:hover,.card.biji .zmore:hover{border-color:var(--gold);background:#fbf7ee;color:var(--ink)}
/* 展开后按钮在末尾很远，卡头给一个「收起」 */
.card .zclose{display:none;margin-left:auto;flex:none;border:1px solid var(--line2);background:#fff;
  border-radius:12px;padding:1px 10px;font-family:var(--sans);font-size:11.5px;color:var(--zhu);cursor:pointer}
.card.open .zclose{display:inline-block}
.card.open .zclose:hover{border-color:var(--gold);background:#fbf7ee}
.card.zhu.short .zmore,.card.biji.short .zmore{display:none}
.card.zhu .zhh{color:var(--zhu);font-weight:700}
.base .cb2{background:#fdfaf3}
.base{border-color:#d9c9a8}
.base .ch{background:#f3e6d2}
.base .ch .vn{color:var(--zhu)}
/* 底本吸顶：单列/双列/三列都吸；选定主注本时，注本卡接在底本下面一起吸。
   两者合计不超过 45vh（全览同样），超出部分在内层滚，下面留一半给对照。 */
#detail.stick .card.base{position:sticky;top:var(--stick-top,40px);z-index:22;
  box-shadow:0 4px 14px rgba(38,34,25,.12);max-height:min(42vh,420px);
  display:flex;flex-direction:column}
#detail.stick .card.base .ch{flex:0 0 auto}
#detail.stick .card.base .cb2{overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain}
#detail .card.base.pick{border-color:var(--gold)}
#detail .card.base.miss .cb2{color:var(--ink3);font-size:14px}
#detail .card.base .ch{flex-wrap:nowrap}
#detail .card.base .ch .pg{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#detail .card.base .ch .basesel{flex:none;margin-left:auto;max-width:48%;border:1px solid var(--line2);
  background:#fff;border-radius:5px;padding:2px 6px;font-family:var(--sans);font-size:12px;
  color:var(--ink);cursor:pointer}
#detail .usebase{margin-left:10px;border:1px solid var(--line2);background:#fff;border-radius:5px;
  padding:2px 8px;cursor:pointer;font-family:var(--sans);font-size:12px;color:var(--zhu)}
.card.zhu.mainz{border-left-color:var(--zhu);box-shadow:0 0 0 1px #e6cbc4 inset}
#detail.haszmain.stick .card.base{max-height:min(18vh,180px)}
#detail.stick .zmainstick{position:sticky;top:calc(var(--stick-top,40px) + var(--base-h,0px) + 14px);
  z-index:21;max-height:calc(45vh - var(--base-h,0px) - 24px);overflow-y:auto;overflow-x:hidden;
  overscroll-behavior:contain;margin-bottom:14px;background:var(--paper)}
#detail .zmainstick .card{margin:0}
#detail .zmainstick .card + .card{margin-top:10px}
#detail .zmainstick .card:first-child .ch{position:sticky;top:0;z-index:2}
/* 全览：坞是拿来跟下面各版对照的，不能铺平。注文不折叠，改为坞内滚，
   总高仍 45/50vh，下半个屏幕留给原文各版与其他注本。 */
#detail.allmode .zmainstick .card .ztxt{max-height:none}
#detail.allmode .zmainstick .card .ztxt::after{display:none}
#detail.allmode .zmainstick .card .zmore{display:none}
#detail.allmode .zmainstick .card .zclose{display:none}
/* 点「展开全文」后，吸顶坞退成普通区块，注文铺开到页面里读；
   否则坞只有 40/55vh，展开还是在那个小窗口里滚，等于没展开。 */
#detail.expandz .zmainstick{position:static!important;max-height:none!important;
  overflow:visible!important;top:auto!important;box-shadow:none}
#detail.expandz .zmainstick .card .ztxt{max-height:none}
#detail.expandz .zmainstick .card .ztxt::after{display:none}
/* .card 的 overflow:hidden 会把 sticky 卡头锁死，展开时放开 */
#detail.expandz .zmainstick .card{overflow:visible}
/* 展开后卡头仍吸顶，让「收起」常驻可达 */
#detail.expandz .zmainstick .card:first-child .ch{position:sticky;top:var(--stick-top,40px);z-index:3}
/* 展开读注文时底本不必再占顶部，否则一直挡着 */
#detail.expandz .card.base{position:static!important}
@media(max-width:820px){#detail.stick .card.base{max-height:min(34vh,300px)}
  /* 底本卡高度取整行：卡头 55 + 正文 2 行 58 + 内边距 24 ≈ 138，避免切在半行上；
     剩下的 260px 正好放「注文卡头 + 6 行 + 展开按钮」。 */
  #detail.haszmain.stick .card.base{max-height:min(17vh,138px)}
  /* 手机坞放到 55vh、底本压到 16vh，给注文留出「卡头＋6 行＋展开按钮」的整块高度；
     否则 40vh 时按钮会被挤出可视区。 */
  #detail.stick .zmainstick{max-height:calc(50vh - var(--base-h,0px) - 24px)}
  /* 手机全览：坞内只有 260px 左右，全文塞进去要滚十几屏。
     这里恢复折叠 6 行 + 「展开全文」，点开铺平读完，卡头「收起」再回 50% 吸顶对照。 */
  #detail.allmode .zmainstick .card .ztxt{max-height:calc(1.9em * 6)}
  #detail.allmode .zmainstick .card.open .ztxt{max-height:none}
  #detail.allmode .zmainstick .card .zmore{display:block}
  #detail.allmode .zmainstick .card .zmore::after{content:" · 铺开读"}
  #detail.allmode .zmainstick .card.open .zclose{display:inline-block}
  #detail .card.base .ch .pg{display:none}}
@media(max-width:600px){.fab{display:none!important}}
mark{background:var(--mark);color:#6b3d05;padding:.5px 1px;border-radius:2px;
  box-shadow:0 1px 0 #d9a441 inset;font-weight:600}
.pg{font-family:var(--sans);font-size:10.5px;color:var(--ink3)}
.evid{font-family:var(--sans);font-size:12px;color:var(--ink2);background:#f5f1e7;
  padding:7px 11px;border-left:3px solid var(--line2);margin-top:8px;line-height:1.7}
.evid b{color:var(--ink)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top;min-width:76px}
th{white-space:nowrap}
th{background:#f1ead9;font-family:var(--sans);font-size:11.5px;color:var(--ink2);position:sticky;top:0}
tr:nth-child(even) td{background:#fcfaf4}
td.has{color:var(--ink)}td.no{color:#c4bcaa;text-align:center}
td:first-child{min-width:150px}
.zc{font-size:11.5px;color:var(--ink2);font-family:var(--sans)}
.hint{font-family:var(--sans);font-size:12px;color:var(--ink3);padding:14px 22px}
.kv{font-family:var(--sans);font-size:12px;color:var(--ink2)}
.kv b{color:var(--ink)}
.pill{display:inline-block;font-family:var(--sans);font-size:10.5px;padding:1px 7px;border-radius:9px;
  border:1px solid var(--line2);margin:0 4px 4px 0;background:#fff}
.pill.on{background:var(--hl);border-color:var(--gold);color:var(--zhu)}
.srch{color:var(--zhu);font-weight:700}
.empty{padding:40px;text-align:center;color:var(--ink3);font-family:var(--sans);font-size:13px}
/* 完整性提示：不占布局，浮在顶部；正常 3 秒后淡出，异常常驻。
   曾用 sticky，会长期占据一行高度（手机上尤其碍事）。 */
.integrity{position:fixed;left:50%;top:64px;transform:translate(-50%,0);z-index:98;
  padding:8px 16px;font-size:13px;line-height:1.5;border-radius:8px;
  max-width:calc(100vw - 24px);background:#eef7ee;color:#1f5c2a;border:1px solid #9fd0aa;
  font-weight:600;font-family:var(--sans);box-shadow:0 3px 14px rgba(0,0,0,.14);
  pointer-events:none;opacity:1;transition:opacity .45s ease,transform .45s ease}
.integrity.hide{opacity:0;transform:translate(-50%,-14px)}
.integrity.bad{background:#fdeaea;color:#8a1f1f;border-color:#e3a3a3;pointer-events:auto}
#toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#2b2620;color:#f6f2ea;
  padding:9px 18px;border-radius:20px;font-family:var(--sans);font-size:12.5px;opacity:0;
  pointer-events:none;transition:opacity .22s;z-index:99}
#toast.on{opacity:1}
kbd{font-family:var(--sans);font-size:10px;background:#efe8da;border:1px solid var(--line2);
  border-radius:3px;padding:1px 4px;color:var(--ink2)}
/* ── 手机竖屏（2026-11-13）──
   原来只在窄屏把侧栏从 290px 缩到 210px，手机上仍然是「左目录 + 右正文」两栏，
   正文被挤成一条窄缝且无法收起。这里改为：侧栏变抽屉，正文占满，目录按钮开关。 */
.hd .menu{display:none}
#mask{display:none}
.dhd{display:none}          /* 抽屉头只在手机端出现 */          /* 抽屉头只在手机端出现 */
@media(max-width:900px){aside{width:210px}}
@media(max-width:820px){
  body{font-size:16px;padding-top:52px}
  /* 顶栏：☰ | 伤寒 金匮 | 🔍 —— 固定，不随内容滚走 */
  header{position:fixed;top:0;left:0;right:0;z-index:60}
  .hd{gap:8px;padding:8px 10px;flex-wrap:nowrap;height:52px}
  .hd .menu{display:inline-flex;align-items:center;justify-content:center;width:36px;height:34px;
    border:1px solid var(--line2);border-radius:7px;background:#fff;font-size:17px;cursor:pointer;
    flex:none;line-height:1}
  .zsw{order:1;margin-left:4px;flex:0 1 auto;min-width:0}
  .zsw button{padding:6px 10px;font-size:13px}
  /* 标题在移动版整体让位：区切换已经说明是哪本书 */
  .title{display:none}
  .hd .kb{display:none}
  /* 搜索：默认收起，点 🔍 才展开 */
  .hd .srchbtn{order:3;display:inline-flex;align-items:center;justify-content:center;
    width:36px;height:34px;flex:none;margin-left:auto;border:1px solid var(--line2);
    border-radius:7px;background:#fff;font-size:16px;cursor:pointer;line-height:1}
  .search{order:4;display:none;flex:1 1 100%;max-width:none;min-width:0}
  .search.open{display:block}
  /* tab 行与统计条在移动版不再占位置：入口进抽屉 */
  .tabs{display:none}
  .stat{display:none}
  /* 手机：丢到下方，别压住导航条与筛选抽屉 */
  .integrity{top:auto;bottom:calc(70px + env(safe-area-inset-bottom,0px));max-width:calc(100vw - 28px)}
  .integrity.hide{transform:translate(-50%,14px)}
  aside{position:fixed;left:0;top:0;bottom:0;width:84vw;max-width:340px;height:100vh;height:100dvh;
    transform:translateX(-101%);transition:transform .22s ease;z-index:70;
    box-shadow:2px 0 16px rgba(0,0,0,.2);border-right:1px solid var(--line2)}
  aside.open{transform:none}
  #mask.on{display:block;position:fixed;inset:0;background:rgba(0,0,0,.38);z-index:65}
  .bar{position:static;padding:8px 12px;gap:8px}
  .bar .kv{display:none}
  .wrap2{padding:12px}
  .card{margin-bottom:12px;border-radius:8px}
  .card .ch{padding:7px 12px;flex-wrap:wrap;gap:6px}
  .card .cb2{padding:11px 13px;font-size:16px;line-height:1.95}
  .it{padding:9px 14px;font-size:14.5px}
  .tscroll table{white-space:nowrap;font-size:13px}
  .tscroll th,.tscroll td{padding:6px 8px}
  aside .gh{padding:10px 13px}
  .dhd{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;
    background:#f1ead9;border-bottom:1px solid var(--line2);font-family:var(--sans);
    font-size:13px;font-weight:700;color:var(--zhu);position:sticky;top:0;z-index:3}
  .dhd button{border:none;background:none;font-size:17px;color:var(--ink2);cursor:pointer;
    padding:2px 8px;line-height:1}
}
/* 小屏手机：标题让位给 ☰ 与区切换（区名本身已经说明是哪本书） */
@media(max-width:520px){
  .title{display:none}
}

/* ══════════ 移动版专用组件（桌面不显示）══════════ */
/* 用 :where() 把优先级降到 0，避免覆盖上面的 @media(max-width:820px) 规则 */
:where(.hd) :where(.srchbtn){display:none}
:where(.colwrap){display:none}      /* 分栏选择器只在移动版出现 */
:where(.dnav){display:none}         /* 抽屉内「视图」入口 */
:where(.navbar){display:none}       /* 条导航条（第几条 + 上/下 + 设置） */
/* 悬浮切换按钮：右下角，只切「单列 ⇄ 双列」，不占布局 */
:where(.fab){display:none}
.fab{position:fixed;right:14px;bottom:calc(16px + env(safe-area-inset-bottom,0px));
  width:46px;height:46px;border-radius:50%;border:1px solid var(--line2);background:#fff;
  color:var(--zhu);line-height:1;cursor:pointer;z-index:55;
  box-shadow:0 4px 14px rgba(0,0,0,.18);display:flex;align-items:center;justify-content:center;
  padding:0;-webkit-tap-highlight-color:transparent;transition:transform .12s ease}
.fab:active{transform:scale(.92)}
.fab.on{background:var(--zhu);color:#fff;border-color:var(--zhu)}
.navbar .navrow{display:flex;align-items:center;gap:6px;min-height:36px}
.navbar .navrow .nav-no{font-family:var(--sans);font-size:12.5px;color:var(--ink2);white-space:nowrap;flex:none}
.navbar .navrow .nav-no b{color:var(--zhu);font-size:14px}
/* 篇名：夹在「N/398 条」与上下箭头之间，纯 CSS 自适应。
   flex-basis:0 + min-width:0 = 「有多少用多少」：没余量时压到 0 宽、文字被裁掉，
   不占位、不挤压按钮、不换行；有余量时自动撑开，过长给省略号。
   注意：这里不能再放 .sp 弹簧，否则余量被它全吃掉，篇名永远是 0 宽。 */
.navbar .navrow .nav-pian{font-family:var(--serif);font-size:11.5px;color:var(--ink3);
  flex:1 1 0px;min-width:0;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;padding:0 4px}
.navbar .navrow .sp{flex:1}
.navbar .navbtn{display:inline-flex;align-items:center;justify-content:center;width:32px;height:30px;
  border:1px solid var(--line2);border-radius:6px;background:#fff;cursor:pointer;font-size:15px;
  line-height:1;flex:none;padding:0}
.navbar .navbtn:active{background:var(--hl)}
.navbar .navbtn:disabled{opacity:.35;cursor:default}
/* 设置行：默认隐藏，点 ⚙ 才开；一行不换行，超宽横向滚动 */
.navbar .setrow{display:none;gap:8px;align-items:center;overflow-x:auto;white-space:nowrap;
  padding:0 0 6px;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.navbar .setrow::-webkit-scrollbar{display:none}
.navbar .setrow.open{display:flex}
.navbar .setrow .cb{display:flex;align-items:center;gap:4px;cursor:pointer;user-select:none;
  font-family:var(--sans);font-size:12px;color:var(--ink2);flex:none}
.navbar .setrow select{border:1px solid var(--line2);background:#fff;padding:3px 6px;border-radius:5px;
  font-size:12px;flex:none}
.navbar .setrow .tag{font-family:var(--sans);font-size:11.5px;color:var(--ink3);flex:none}
.navbar .setrow.open{flex-wrap:wrap;white-space:normal;overflow:visible}
.navbar .setrow .fbox{display:none;flex:1 0 100%;flex-wrap:wrap;gap:8px;align-items:center;
  padding-top:6px;border-top:1px dashed var(--line2);white-space:normal}
.navbar .setrow .fbox.open{display:flex}
/* 多栏对比：JS 按高度动态分列的真瀑布流（.mflow）。
   为什么不用 CSS column-count：它是「先填满左列再填右列」，阅读顺序变纵向，
   版本对照要的是「同一行左右可比」，所以必须按高度贪心分配。 */
.pane .mflow{display:flex;gap:10px;align-items:flex-start}
.pane .mflow .mcol{flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:10px}
.pane .mflow .card{margin:0}
.pane .mflow .cb2{font-size:13px;line-height:1.85;padding:9px 10px}
.pane .mflow .ch{padding:6px 9px;gap:4px}
.pane .mflow .ch .vn{font-size:12.5px}
.pane .mflow .base{flex:0 0 100%}
.pane .multi2 .base,.pane .multi3 .base{flex:0 0 100%}

/* 左固定右滑：左列（底本）不滚，右列独立横向滑动对比各版。
   整块高度锁定在内容区可视范围内，只让右列滚，左列始终在眼前。 */
.pane .pinsplit{display:flex;gap:10px;align-items:stretch;
  height:100%;max-height:100%;overflow:hidden}
.pane .pinsplit .pinleft{flex:0 0 44%;max-width:44%;min-width:0;overflow:hidden;
  display:flex;flex-direction:column}
.pane .pinsplit .pinright{flex:1 1 0;min-width:0;overflow-y:auto;overflow-x:hidden;
  -webkit-overflow-scrolling:touch;display:flex;flex-direction:column;gap:10px;padding-right:2px}
.pane .pinsplit .card{margin:0}
.pane .pinsplit .cb2{font-size:13.5px;line-height:1.9;padding:9px 10px}
.pane .pinsplit .ch{padding:6px 9px;gap:4px}
.pane .pinsplit .ch .vn{font-size:12.5px}
.pane .pinsplit .pinhint{font-family:var(--sans);font-size:11px;color:var(--ink3);
  padding:4px 2px 6px;flex:none}

@media(max-width:820px){
  /* 内容区独立滚动：只在正文范围内上下滑，顶栏与导航条不动 */
  .wrap{display:flex;flex-direction:column;height:calc(100dvh - 52px);overflow:hidden;
    width:100%;max-width:100vw}
  main{flex:1;min-height:0;min-width:0;width:100%;overflow-y:auto;overflow-x:hidden;
    -webkit-overflow-scrolling:touch;padding-bottom:24px}
  .view{width:100%;min-width:0}
  .wrap2{padding:10px;width:100%;min-width:0}
  /* 左固定右滑模式：让 #detail 撑满 main 剩余高度，pinsplit 才能内部滚动 */
  .pane:has(.pinsplit){height:100%;max-height:100%;box-sizing:border-box;
    display:flex;flex-direction:column;padding-bottom:10px}
  .pane:has(.pinsplit) .pinsplit{flex:1;min-height:0}
  .card{max-width:100%;min-width:0}
  .card .cb2{overflow-wrap:anywhere;word-break:break-word}
  /* 导航条按钮收紧，避免溢出屏宽 */
  .navbar .navrow{gap:4px;padding-right:0}
  .navbar .navbtn{width:30px;height:28px;font-size:14px}
  /* 桌面筛选行整块隐藏：移动端用导航条里的设置行代替 */
  #v-cmp .bar{display:none}
  .navbar{display:block;position:sticky;top:0;z-index:25;background:rgba(246,242,234,.97);
    backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:5px 10px 0;
    font-family:var(--sans)}
  #v-fang .navbar,#v-pian .navbar,#v-indep .navbar,#v-review .navbar,#v-about .navbar,#v-stat .navbar{display:none}
  .dnav{display:block;border-bottom:1px solid var(--line2);background:#f7f2e6}
  .dnav .dt{font-family:var(--sans);font-size:11px;color:var(--ink3);padding:7px 14px 3px;letter-spacing:.5px}
  .dnav button{display:flex;width:100%;justify-content:space-between;align-items:center;
    border:none;background:none;padding:9px 14px;font-family:var(--serif);font-size:14.5px;
    color:var(--ink2);cursor:pointer;text-align:left}
  .dnav button .cnt2{font-family:var(--sans);font-size:11px;color:var(--ink3)}
  .dnav button.on{color:var(--zhu);font-weight:700;background:var(--hl)}
  .dnav button:hover{background:#efe8da}
  .fab{display:flex}
  .colwrap{display:inline-flex;align-items:center;gap:4px;flex:none}
  .colwrap .tag{font-family:var(--sans);font-size:11.5px;color:var(--ink3)}
  .colwrap select{border:1px solid var(--line2);background:#fff;padding:3px 6px;border-radius:5px;font-size:12px}
}
/* 首屏加载遮罩：数据未就绪时给明确提示，失败可重试 */
#boot{position:fixed;inset:0;z-index:9999;background:var(--paper);display:flex;align-items:center;
  justify-content:center;transition:opacity .22s ease}
#boot.off{opacity:0;pointer-events:none}
#boot .bootbox{text-align:center;font-family:var(--sans);color:var(--ink2);max-width:320px;padding:0 20px}
#boot .bootspin{width:26px;height:26px;margin:0 auto 12px;border:3px solid var(--line2);
  border-top-color:var(--zhu);border-radius:50%;animation:bootspin .8s linear infinite}
@keyframes bootspin{to{transform:rotate(360deg)}}
#boot #bootmsg{font-size:14px;line-height:1.65}
#boot #bootretry{margin-top:14px;padding:7px 20px;border:1px solid var(--line2);border-radius:6px;
  background:#fff;font-family:var(--sans);font-size:14px;color:var(--zhu);cursor:pointer}
#boot #bootretry:active{background:#f7f2e8}
#boot.err .bootspin{display:none}
#boot.err #bootmsg{color:var(--zhu)}
/* 句子定位：注文卡「定位」跳到骨架该句并短暂高亮 */
#detail .sent.hl{background:#ffe6a6;box-shadow:0 0 0 3px #ffe6a6;border-radius:3px;transition:background .3s}
#detail .card.zhu .locate{border:1px solid var(--line2);background:#fff;border-radius:5px;
  padding:1px 7px;font-family:var(--sans);font-size:11.5px;color:var(--zhu);cursor:pointer;flex:none}
#detail .card.zhu .locate:hover{background:#fdf6ea}
</style>
</head>
<body>
<div id="boot"><div class="bootbox"><div class="bootspin"></div>
  <div id="bootmsg">正在加载数据…</div>
  <button id="bootretry" type="button" hidden>重试</button></div></div>
<noscript><div style="padding:14px 20px;background:#fdeaea;color:#8c2f22;font-family:sans-serif;font-size:13px">
本页面需要启用 JavaScript 才能交互(数据已内嵌在文件内,无需联网)。若在预览窗格中打开,请先下载到本地再用浏览器打开。</div></noscript>
<header>
  <div class="hd">
    <button class="menu" id="menu" aria-label="目录" title="目录">☰</button>
    <div class="zsw" id="zsw" style="display:none"></div>
    <div class="title"><span id="ttl">__TITLE__</span><small>骨架:<span id="skn">__SKEL_NAME__</span></small></div>
    <div class="search" id="searchbox">
      <span class="ic">⌕</span>
      <input id="q" placeholder="搜条号 / 关键词(如:桂枝汤、营弱卫强、阴濡弱)…" autocomplete="off">
      <button class="clr" id="qclr" title="清空">✕</button>
    </div>
    <button class="srchbtn" id="srchbtn" aria-label="搜索" title="搜索">⌕</button>
    <div class="kb" style="font-family:var(--sans);font-size:11px;color:var(--ink3)">
      <kbd>j</kbd><kbd>k</kbd> 上下条 · <kbd>/</kbd> 搜索
    </div>
  </div>
  <div class="tabs" id="tabs">
    <button class="tab on" data-v="cmp">条文对照</button>
    <button class="tab" data-v="fang">方剂对照<span class="cnt" id="c-fang"></span></button>
    <button class="tab" data-v="biji">笔记<span class="cnt" id="c-biji"></span></button>
    <button class="tab" data-v="pian">篇级对照</button>
    <button class="tab" data-v="indep">独有序<span class="cnt" id="c-indep"></span></button>
    <button class="tab" data-v="review">待复核<span class="cnt" id="c-rev"></span></button>
    <button class="tab" data-v="about">体例说明</button>
    <button class="tab" data-v="stat">版本统计</button>
  </div>
  <div class="stat" id="stat"></div>
</header>
<div id="mask"></div>

<div class="wrap">
  <aside id="side">
    <div class="dhd"><span>目录</span><button id="dclose" aria-label="关闭目录">✕</button></div>
    <div class="dnav" id="dnav"></div>
    <div id="sidelist"></div>
  </aside>
  <main>
    <section class="view on" id="v-cmp">
      <div class="navbar" id="navbar">
        <div class="navrow">
          <span class="nav-no"><b id="nav-cur">-</b> / <span id="nav-all">465</span> 条</span>
          <span class="nav-pian" id="nav-pian"></span>
          <button class="navbtn" id="nav-up" aria-label="上一条" title="上一条">↑</button>
          <button class="navbtn" id="nav-dn" aria-label="下一条" title="下一条">↓</button>
          <button class="navbtn" id="nav-set" aria-label="筛选设置" title="筛选设置">⚙</button>
        </div>
        <div class="setrow" id="setrow">
          <label class="cb">看法 <select id="readsel2">
            <option value="zhu">读注</option><option value="yuan">原文</option><option value="all">全览</option>
          </select></label>
          <button class="fbtn" id="filterbtn2">筛选</button>
          <div class="fbox" id="fbox2">
            <label class="cb">差异 <select id="fDiffMode2">
              <option value="">全部</option><option value="diff">只看有异文</option><option value="same">只看全同</option>
            </select></label>
            <label class="cb" id="fZhuWrap2"><input type="checkbox" id="fZhu2"> 只看有注文</label>
            <label class="cb">版本 <select id="fVer3"></select></label>
            <label class="cb">状态 <select id="fSt2">
              <option value="">全部</option><option value="有">有</option>
              <option value="无">无</option><option value="anch">校记锚点</option>
              <option value="hi">高置信</option><option value="low">低置信</option>
            </select></label>
            <label class="cb">视图 <select id="colsel2">
              <option value="1">单列</option><option value="2">双列</option>
              <option value="3">三列</option><option value="pin">左固定右滑</option>
            </select></label>
            <button id="freset2">重置</button>
          </div>
          <span class="tag" id="set-note"></span>
        </div>
      </div>
      <div class="bar">
        <label class="cb">看法 <select id="readsel">
          <option value="zhu">读注</option><option value="yuan">原文</option><option value="all">全览</option>
        </select></label>
        <button class="fbtn" id="filterbtn">筛选</button>
        <div class="fbox" id="fbox">
          <label class="cb">差异 <select id="fDiffMode">
            <option value="">全部</option><option value="diff">只看有异文</option><option value="same">只看全同</option>
          </select></label>
          <label class="cb" id="fZhuWrap"><input type="checkbox" id="fZhu"> 只看有注文</label>
          <label class="cb" title="只选版本:只看该版有此条的条文">版本 <select id="fVer"></select></label>
          <label class="cb" title="需与版本筛选配合使用">状态 <select id="fSt">
            <option value="">全部</option><option value="有">有</option>
            <option value="无">无</option><option value="anch">校记锚点</option>
            <option value="hi">高置信</option><option value="low">低置信</option>
          </select></label>
          <label class="cb">视图 <select id="colsel">
            <option value="1">单列</option><option value="2">双列</option>
            <option value="3">三列</option><option value="pin">左固定右滑</option>
          </select></label>
          <button id="freset">重置</button>
        </div>
        <span class="sp"></span>
        <span id="cnt"></span>
        <span class="kv" style="color:var(--ink3)">← 点左侧条目看多版对照</span>
        <button id="copy">复制本条 Markdown</button>
      </div>
      <div class="wrap2 pane" id="detail"></div>
    </section>

    <section class="view" id="v-biji">
      <div class="bar">
        <label class="cb">注本 <select id="bijiSel"></select></label>
        <span class="chip" id="bijiPianChip" style="display:none"></span>
        <span class="sp"></span><span id="biji-cnt"></span>
      </div>
      <div class="wrap2" id="bijibox"></div>
    </section>

    <section class="view" id="v-fang">
      <div class="bar">
        <span class="cb"><input type="checkbox" id="fOnly"> 只看某版独有</span>
        <label class="cb">版本 <select id="fVer2"></select></label>
        <span class="sp"></span><span id="cnt2"></span>
      </div>
      <div class="wrap2"><div id="fangbox"></div></div>
    </section>

    <section class="view" id="v-pian">
      <div class="bar"><span class="sp"></span><span class="kv">无条号篇(辨脉法、平脉法、伤寒例、辨痉湿暍、可·不可发汗吐下等)以「篇」为对照单位</span></div>
      <div class="wrap2"><div id="pianbox"></div></div>
    </section>

    <section class="view" id="v-indep">
      <div class="bar"><span class="sp"></span><span class="kv">各版自有、而骨架无对应者;独立章节 ID</span></div>
      <div class="wrap2"><div id="indepbox"></div></div>
    </section>

    <section class="view" id="v-review">
      <div class="bar"><span class="sp"></span><span class="kv">低置信匹配与「暂未匹配」条目,建议人工过一遍</span></div>
      <div class="wrap2"><div id="revbox"></div></div>
    </section>

    <section class="view" id="v-about">
      <div class="wrap2"><div id="aboutbox"></div></div>
    </section>

    <section class="view" id="v-stat">
      <div class="wrap2"><div id="statbox"></div></div>
    </section>
  </main>
</div>
<div id="toast"></div>
<button id="fab" class="fab" aria-label="切换单列/双列" title="切换单列/双列">
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8">
    <rect x="3" y="4" width="7.5" height="16" rx="1.2"/><rect x="13.5" y="4" width="7.5" height="16" rx="1.2"/>
  </svg>
</button>

__DATA_TAG__
<script>
window.addEventListener('error', function(e){ try{ document.title = 'ERR:' + (e.message||''); }catch(x){} });
let D = null, VERS = [];
/* 数据装载:双区(SH/JG)或单区。双区时 ZONES=[{id,name,data}] */
let ZONES = (function(){
  if (window.__SHJ_ZONES__ && window.__SHJ_ZONES__.length) return window.__SHJ_ZONES__;
  let raw = '';
  if (window.__SHJ_DATA__) return [{id:'one', name:'', data: window.__SHJ_DATA__}];
  try { raw = document.getElementById('DATA').textContent; }
  catch(e){ return []; }
  try { return [{id:'one', name:'', data: JSON.parse(raw)}]; }
  catch(e){
    document.addEventListener('DOMContentLoaded', ()=>banner(
      '数据解析失败:' + e.message + '(内嵌 JSON 不完整或被截断)'));
    return [];
  }
})();
let ZI = 0;
D = (ZONES[ZI] && ZONES[ZI].data) || {};
VERS = D.vers || [];
const $ = s => document.querySelector(s);
const esc = s => (s==null?'':String(s)).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
// 【…】→ <mark>
const mk = s => esc(s).replace(/【([^】]*)】/g, '<mark>$1</mark>');
/* 骨架按句切 span：注文定位用；句子 ID = n:i，将来 L3 文本锚可直接复用 */
const mkSent = it => {
  const ss = it.sent;
  if (!ss || !ss.length) return mk(it.s);
  return ss.map((x, i) => `<span class="sent" data-n="${it.n}" data-i="${i}">${mk(x)}</span>`).join('');
};
/* 注文里的【解析】【按】是注本自身的体例标题，不是异文标记，不能套 <mark> 高亮 */
const ztxt = s => esc(s).replace(/【([^】]{1,14})】/g, '<b class="zhh">【$1】</b>');
const CF = {'校记锚点':'t-anch','高置信':'t-hi','中置信':'t-mid','低置信':'t-low'};
const BASE = () => D.baseLabel || '宋本';   // SH=宋本 / JG=赵开美本
const ZKEY = () => (D.skel && D.skel.id) || D.id || 'zone';
/* 主版本 / 主注本：按区分开记，刷新与切区都不丢。
   骨架版选原文版本；注释本选注本——两站的「为主」对象不同。 */
let basePick = '', zhuPick = '', viewMode = '1';
let readMode = 'all';                 // 读注 / 原文 / 全览（注释本默认全览，2026-11-28 用户定）
let diffMode = '', zhuOnly = true;    // 差异三态；读注默认只列有注文的条
let bijiPick = '', bijiPian = '';     // 笔记页：注本筛选、篇筛选
const isZhuSite = () => !!(D.zhub && D.zhub.length);
function loadPrefs(){
  try{
    basePick = localStorage.getItem('shj.base.' + ZKEY()) || '';
    const zs = localStorage.getItem('shj.zhu.' + ZKEY());
    const defZ = (D.zhub || []).find(b => b.id === 'nihaixia' || b.id === 'nihaixia_sh')
              || (D.zhub || [])[0];   // 默认倪海厦；两区各一本（JG nihaixia / SH nihaixia_sh）
    zhuPick = (zs === null) ? (defZ ? defZ.id : '') : zs;
    viewMode = localStorage.getItem('shj.view') || '1';
    readMode = localStorage.getItem('shj.read.' + ZKEY()) || 'all';
    diffMode = localStorage.getItem('shj.diff') || '';
    zhuOnly = localStorage.getItem('shj.zhuonly') !== '0';
  }catch(e){ basePick = ''; zhuPick = ''; viewMode = '1'; readMode = 'all'; diffMode = ''; zhuOnly = true; }
  if (basePick && !VERS.includes(basePick)) basePick = '';
  if (zhuPick && !(D.zhub || []).some(b => b.id === zhuPick)) zhuPick = '';
  const max = window.innerWidth >= 1000 ? 3 : (window.innerWidth >= 600 ? 2 : 1);
  if (!['1','2','3','pin'].includes(viewMode)) viewMode = '1';
  if (viewMode !== 'pin' && +viewMode > max) viewMode = '1';
  if (!isZhuSite()) readMode = 'yuan';
  if (!['zhu','yuan','all'].includes(readMode)) readMode = 'all';
}
function savePref(k, v){ try{ localStorage.setItem(k, v); }catch(e){} }
/* 吸顶起点＝当前固定工具条的高度：桌面取 .bar，手机取 .navbar（含展开的设置行）。 */
function syncStickTop(){
  const nav = $('#navbar');
  const bar = document.querySelector('#v-cmp .bar');
  const h = window.matchMedia('(max-width:820px)').matches
    ? (nav ? nav.offsetHeight : 0)
    : (bar ? bar.offsetHeight : 0);
  document.documentElement.style.setProperty('--stick-top', h + 'px');
}
/* 主注本吸顶接在底本下面：量底本实际高度，总高限 40vh。 */
function syncStickOffsets(){
  const pane = $('#detail'); if (!pane) return;
  const b = pane.querySelector('.card.base');
  const z = pane.querySelector('.zmainstick');
  if (!b || !z){ pane.style.removeProperty('--base-h'); return; }
  pane.style.setProperty('--base-h', Math.round(b.getBoundingClientRect().height) + 'px');
}
function setBase(v){
  basePick = v || '';
  savePref('shj.base.' + ZKEY(), basePick);
  if (cur){ const m = document.querySelector('main'); const y = m.scrollTop;
    select(cur.n); m.scrollTop = y; }
}
function setZhu(v){
  zhuPick = v || '';
  savePref('shj.zhu.' + ZKEY(), zhuPick);
  ['#zhuSel','#zhuSel2'].forEach(s => { const e = $(s); if (e) e.value = zhuPick; });
  fillSel();
  buildSide();
  if (cur){ const m = document.querySelector('main'); const y = m.scrollTop;
    select(cur.n); m.scrollTop = y; }
}
/* 视图状态单独存：不靠 select 的当前值——Safari 上偶发 change 已触发但值还没落到 DOM，
   先读 select 会把双列读成单列。FAB、设置行、切区都走这一个状态。 */
function setView(v){
  viewMode = v || '1';
  const max = window.innerWidth >= 1000 ? 3 : (window.innerWidth >= 600 ? 2 : 1);
  if (viewMode !== 'pin' && +viewMode > max) viewMode = '1';
  savePref('shj.view', viewMode);
  ['#colsel','#colsel2'].forEach(s => { const e = $(s); if (e) e.value = viewMode; });
  if (cur){ const m = document.querySelector('main'); const y = m.scrollTop;
    select(cur.n); m.scrollTop = y; }
}
function setRead(v){
  readMode = ['zhu','yuan','all'].includes(v) ? v : 'all';
  savePref('shj.read.' + ZKEY(), readMode);
  fillSel(); buildSide();
  if (cur) select(cur.n);
}
function setDiff(v){
  diffMode = ['diff','same'].includes(v) ? v : '';
  savePref('shj.diff', diffMode);
  ['#fDiffMode','#fDiffMode2'].forEach(s => { const e = $(s); if (e) e.value = diffMode; });
  buildSide();
}
function setZhuOnly(on){
  zhuOnly = !!on;
  savePref('shj.zhuonly', zhuOnly ? '1' : '0');
  ['#fZhu','#fZhu2'].forEach(s => { const e = $(s); if (e) e.checked = zhuOnly; });
  buildSide();
}
/* 吸顶卡头里的切换器：骨架版选原文版本，注释本选注本。 */
function baseSelHtml(){
  return '<select id="baseSel" class="basesel" aria-label="主版本">'
    + `<option value=""${basePick ? '' : ' selected'}>骨架（${esc(BASE())}）</option>`
    + VERS.filter(v => v !== '倪本').map(v => `<option value="${esc(v)}"${v === basePick ? ' selected' : ''}>${esc(v)}</option>`).join('')
    + '</select>';
}
function zhuSelHtml(){
  return '<select id="zhuSel" class="basesel" aria-label="主注本">'
    + `<option value=""${zhuPick ? '' : ' selected'}>全部注本</option>`
    + (D.zhub || []).map(b => `<option value="${esc(b.id)}"${b.id === zhuPick ? ' selected' : ''}>${esc(b.name || b.id)}</option>`).join('')
    + '</select>';
}
const pickSelHtml = () => isZhuSite()
  ? (readMode === 'yuan' ? '' : zhuSelHtml())
  : baseSelHtml();
let cur = null, curTab = 'cmp';
/* 条号 → 该条全部注文拼串。搜索要能搜到注文，但不能每次按键现拼 1 MB 字符串。 */
let ZHUHAY = {};

/* ---------- 侧栏:条目录 ---------- */
function diffVers(it){ return VERS.filter(v => it.v[v].ok && /【/.test(it.v[v].d||'')); }
/* 筛选谓词：buildSide 与 nav/compose 都从当前筛选控件现取，避免两套状态 */
function noteHay(n, onlyPick){
  const arr = (D.zhu && D.zhu[n]) || [];
  return arr.filter(r => {
    if (!onlyPick) return true;
    const b = (D.zhub || [])[r.b] || {};
    return b.id === zhuPick;
  }).map(r => r.t || '').join(' ');
}
function hasNote(n){
  const arr = (D.zhu && D.zhu[n]) || [];
  if (!zhuPick) return arr.length > 0;
  return arr.some(r => ((D.zhub || [])[r.b] || {}).id === zhuPick);
}
/* 筛选谓词：条注按当前注本判断；原文模式不注文。 */
function makeMatch(){
  const q = ($('#q') && $('#q').value || '').trim();
  const fv = ($('#fVer') && $('#fVer').value) || '';
  const fst = ($('#fSt') && $('#fSt').value) || '';
  const isZ = isZhuSite();
  const needNote = isZ && readMode === 'zhu' && (zhuOnly || !!zhuPick);
  return it => {
    if (diffMode === 'diff' && !diffVers(it).length) return false;
    if (diffMode === 'same' && diffVers(it).length) return false;
    if (needNote && !hasNote(it.n)) return false;
    const okState = c => {
      if (fst==='有') return c.ok;
      if (fst==='无') return !c.ok;
      if (fst==='anch') return c.cf==='校记锚点';
      if (fst==='hi') return ['高置信','校记锚点'].includes(c.cf);
      if (fst==='low') return ['低置信','中置信'].includes(c.cf);
      return true;
    };
    if (fv){
      const c = it.v[fv];
      if (fst){ if (!okState(c)) return false; }
      else if (!c.ok) return false;              // 只选版本 → 该版有此条者
    } else if (fst){
      if (!VERS.some(v => okState(it.v[v]))) return false;
    }
    if (q){
      const nh = isZ ? noteHay(it.n, readMode !== 'yuan' && !!zhuPick) : '';
      const hay = it.n+' '+it.s+' '+VERS.map(v=>it.v[v].ok?it.v[v].t:'').join(' ')
                  + ' ' + nh;
      if (!hay.includes(q)) return false;
    }
    return true;
  };
}

function buildSide(){
  const match = makeMatch();
  const groups = new Map();
  D.items.filter(match).forEach(it => {
    const k = it.pian || '(未分篇)';
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(it);
  });
  let h = '';
  for (const [g, arr] of groups){
    h += `<div class="grp"><div class="gh">
      <span>${esc(g.replace(/  +/g,' '))}</span><span class="c">${arr.length}</span></div><div>`;
    for (const it of arr){
      const dv = diffVers(it);
      const dots = VERS.map(v => {
        const c = it.v[v];
        if (!c.ok) return '<span class="dot"></span>';
        if (c.cf==='校记锚点') return '<span class="dot a"></span>';
        if (/【/.test(c.d||'')) return '<span class="dot d"></span>';
        return '<span class="dot"></span>';
      }).join('');
      const snip = (it.s||'').slice(0,18);
      h += `<div class="it ${it===cur?'on':''}" data-n="${it.n}"><span class="n">${it.n}</span>
        <span class="t">${esc(snip)}</span><span class="dots">${dots}</span></div>`;
    }
    h += '</div></div>';
  }
  $('#sidelist').innerHTML = h || '<div class="empty">无匹配条目</div>';
  markSide();
  $('#cnt').textContent = D.items.filter(match).length + ' / ' + D.items.length + ' 条';
  if (typeof syncFilters === 'function') syncFilters();
  if (typeof updateNav === 'function') updateNav();
}

/* ---------- 详情 ---------- */
function markSide(){
  document.querySelectorAll('#side .it').forEach(el =>
    el.classList.toggle('on', cur && +el.dataset.n === cur.n));
}
/* 瀑布流分列：卡片按顺序插入当前最矮的那一列。
   需要先入 DOM 再量高度，故逐个 append 后立即测 offsetHeight。 */
function flowCards(cards){
  const flow = $('#detail .mflow');
  if (!flow) return;
  const colsEl = [...flow.querySelectorAll('.mcol')];
  const heights = colsEl.map(() => 0);
  for (const html of cards){
    // 选当前最矮的列（等高时取靠左，保证顺序稳定）
    let k = 0;
    for (let i = 1; i < heights.length; i++) if (heights[i] < heights[k] - 0.5) k = i;
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    const node = tmp.firstElementChild;
    colsEl[k].appendChild(node);
    heights[k] += node.offsetHeight + 10;   // 10 = gap
  }
}

/* 左固定右滑：给 .pinsplit 算一个显式高度。
   纯 CSS 的 height:100% 在 #detail 没有确定高度时不会撑开，
   右栏卡片就会被父级裁掉（实测「脉浮头项强痛而恶寒」被切断）。
   这里按「可视高度 - 顶栏 - 导航条 - #detail 的纵向 padding」实算。 */
function fitPin(){
  const ps = $('#detail .pinsplit');
  if (!ps) return;
  const main = document.querySelector('main');
  if (!main) return;
  const nav = $('#navbar');
  const navH = (nav && getComputedStyle(nav).display !== 'none') ? nav.offsetHeight : 0;
  const padTop = parseFloat(getComputedStyle($('#detail')).paddingTop) || 0;
  const padBot = parseFloat(getComputedStyle($('#detail')).paddingBottom) || 0;
  const avail = main.clientHeight - navH - padTop - padBot - 4;
  ps.style.height = Math.max(240, avail) + 'px';
}

function select(n){
  const it = D.items.find(x => x.n === n);
  if (!it) return;
  cur = it;
  const pane = $('#detail');
  const zsite = isZhuSite();
  const zmode = zsite ? readMode : 'yuan';       // 骨架版固定原文；注释本按看法
  let mode = (zmode === 'zhu') ? '1' : (viewMode || '1');
  const max = window.innerWidth >= 1000 ? 3 : (window.innerWidth >= 600 ? 2 : 1);
  if (mode !== 'pin' && +mode > max) mode = '1';
  const cols = +mode || 1;
  // 底本卡：骨架版可选任一原文版本吸顶；注释本固定骨架，另选主注本。
  // 条号已在导航条显示，此处不再重复；页码(p419)是影印本页码，改由「体例说明」页解释。
  const bv = (!zsite && basePick) ? basePick : '';
  let baseH;
  if (bv){
    const bc = it.v[bv];
    if (bc && bc.ok){
      baseH = `<div class="card base pick"><div class="ch"><span class="vn">${esc(bv)}</span>
        <span class="tag t-hi">主版本</span>
        <span class="pg">异文基准：${esc(BASE())}</span>
        ${pickSelHtml()}</div>
        <div class="cb2">${mk(bc.t || '')}</div></div>`;
    }else{
      baseH = `<div class="card base miss"><div class="ch"><span class="vn">${esc(bv)}</span>
        <span class="tag t-none">此版无</span>
        <span class="pg">${esc(((bc && bc.rs) || '').slice(0, 40))}</span>
        ${pickSelHtml()}</div>
        <div class="cb2">此条无${esc(bv)}正文。${esc(((bc && bc.ev) || '').slice(0, 120))}
          <button class="usebase">改用骨架</button></div></div>`;
    }
  }else{
    baseH = `<div class="card base"><div class="ch"><span class="vn">${esc(BASE())}</span>
      <span class="pg">${esc(it.pian||'')}</span>
      ${pickSelHtml()}</div>
      <div class="cb2">${mkSent(it)}</div></div>`;
  }
  // 原文模式不列各版；读注模式只留骨架＋注本
  const verCards = [];
  if (zmode !== 'zhu'){
    if (bv){
      // 主版本不是骨架时，骨架仍要留在对照里——它是所有【】的基准
      verCards.push(`<div class="card"><div class="ch"><span class="vn">${esc(BASE())}</span>
        <span class="tag t-anch">骨架</span><span class="pg">对照基准</span></div>
        <div class="cb2">${mkSent(it)}</div></div>`);
    }
    for (const v of VERS){
      if (v === bv) continue;                    // 已作主版本吸顶，不再重复
      const c = it.v[v];
      if (c.ok){
        const tag = CF[c.cf] || 't-low';
        const seg = (c.d||c.t).split('\n');
        // 倪本是今人整理，多数与宋本逐字同；同文不重出，否则和吸顶的骨架看着像重复
        const same = (v === '倪本') &&
          (c.t||'').replace(/[^\u4e00-\u9fff]/g,'') === (it.s||'').replace(/[^\u4e00-\u9fff]/g,'');
        if (same){
          verCards.push(`<div class="card"><div class="ch"><span class="vn">${esc(v)}</span>
            <span class="tag ${tag}">${esc(c.cf)}</span><span class="pg">与骨架同文</span></div>
            <div class="cb2" style="color:var(--ink3);font-size:14px">本条倪本与宋本逐字相同，不重出。</div></div>`);
        }else{
          verCards.push(`<div class="card"><div class="ch"><span class="vn">${esc(v)}</span>
            <span class="tag ${tag}">${esc(c.cf)}</span></div>
            <div class="cb2">${seg.map(mk).join('<br>')}</div></div>`);
        }
      }else{
        verCards.push(`<div class="card"><div class="ch"><span class="vn" style="color:var(--ink3)">${esc(v)}</span>
          <span class="tag t-none">此版无</span><span class="pg">${esc(c.rs||'')}</span></div>
          <div class="cb2" style="color:var(--ink3);font-size:14px">依据:${esc(c.ev||'')}</div></div>`);
      }
    }
  }
  // ★ 注文(如成无己注)挂在条下 —— 2026-11-04；只在全览保留
  const legacy = [];
  if (zmode === 'all'){
    const nts = (D.notes && D.notes[it.n]) || null;
    if (nts){
      for (const vn of Object.keys(nts)){
        const paras = nts[vn].split('\n').filter(x => x.trim());
        legacy.push(`<div class="card" style="border-left:3px solid var(--gold)">
          <div class="ch"><span class="vn">${esc(vn)}·注文</span>
          <span class="pg">${paras.length} 段</span></div>
          <div class="cb2" style="font-size:14px;line-height:1.85">${
            paras.map(p => esc(p).replace(/^((注\d+·[^）]*)|（[^）]*）)$/,
              '<b style="color:var(--gold)">$1</b>')).join('<br>')}</div></div>`);
      }
    }
  }
  // ★ L2 注文（41_注释本对比，2026-11-17）
  //   zhu[n] = [{b:注本序号, t:正文, pg:页码, seg:段号, attr:说话人}]
  //   读注：只留选中注本；全览：主注本置顶、其余照列。
  const zmain = [], zother = [];
  if (zmode !== 'yuan'){
    const zl = (D.zhu && D.zhu[it.n]) || null;
    if (zl){
      // 同一注本在同一条的多段记录合并成一张卡，否则会渲染成好几张同名卡，看着像重复
      const groups = new Map();
      for (const r of zl){
        const b = (D.zhub || [])[r.b] || {};
        const key = b.id || ('b' + r.b);
        if (!groups.has(key)) groups.set(key, {b, rows: []});
        groups.get(key).rows.push(r);
      }
      for (const g of groups.values()){
        const b = g.b, rows = g.rows;
        const txt = rows.map(r => r.t || '').join('\n');
        const long = txt.length > 240 || txt.split('\n').length > 5;
        const meta = [];
        if (rows.length > 1) meta.push(rows.length + ' 段');
        else if (rows[0].seg) meta.push('第' + rows[0].seg + '段');
        // sent + 可选 sent_span（末句号）共同确定所注句区间
        const sentSet = new Set();
        for (const r of rows){
          if (r.sent == null) continue;
          const e2 = (r.sent_span != null && r.sent_span >= r.sent) ? r.sent_span : r.sent;
          for (let k = r.sent; k <= e2; k++) sentSet.add(k);
        }
        const sents = [...sentSet].sort((a,b)=>a-b);
        if (sents.length === 1) meta.push('第' + (sents[0] + 1) + '句');
        else if (sents.length > 1) meta.push('第' + (sents[0] + 1) + '–' + (sents[sents.length-1] + 1) + '句');
        // 同条多段可能各带不同 n_span（如讲二 14–22 与讲五单条 14），取最大末条号
        const sp0 = Math.max(...rows.map(r => (r.n_span != null && r.n_span > it.n) ? r.n_span : it.n));
        if (sp0 > it.n) meta.push('注 ' + it.n + '–' + sp0 + ' 条');
        const attrs = [...new Set(rows.map(r => r.attr).filter(Boolean))];
        if (attrs.length) meta.push(attrs.join('/'));
        const pgs = [...new Set(rows.map(r => r.pg).filter(v => v != null))];
        if (pgs.length) meta.push('p' + pgs.join(','));
        const isMain = !!(zhuPick && b.id === zhuPick);
        if (zmode === 'zhu' && zhuPick && !isMain) continue;   // 读注：其他注本不列
        const tgt = (b.targets || []).join('/');
        const html = `<div class="card zhu${long ? '' : ' short'}${isMain ? ' mainz' : ''}">
          <div class="ch"><span class="vn">${esc(b.name || b.id || '')}</span>
          <span class="tag t-zhu">注</span>
          ${isMain ? '<span class="tag t-hi">主注本</span>' : ''}
          ${tgt ? `<span class="pg">注${esc(tgt)}</span>` : ''}
          ${meta.length ? `<span class="pg">${esc(meta.join(' · '))}</span>` : ''}
          ${long ? `<span class="pg">${txt.length} 字</span>` : ''}
          ${sents.length ? `<button class="locate" data-n="${it.n}" data-sent="${sents[0]}" data-sent2="${sents[sents.length-1]}" title="定位到原文该句">定位</button>` : ''}
          ${long ? '<button class="zclose">收起</button>' : ''}</div>
          <div class="cb2 ztxt">${ztxt(txt)}</div>
          <button class="zmore">展开全文</button></div>`;
        (isMain ? zmain : zother).push(html);
      }
    }
  }
  let notice = '';
  if (zmode === 'zhu' && zhuPick && !zmain.length){
    const zb = (D.zhub || []).find(b => b.id === zhuPick) || {};
    notice = `<div class="card zhu miss"><div class="ch"><span class="vn">${esc(zb.name || zhuPick)}</span>
      <span class="tag t-none">此条无注</span></div>
      <div class="cb2" style="color:var(--ink3);font-size:14px">该注本此条无注文。
        <button class="nextzhu">跳到下一条有注</button></div></div>`;
  }
  // 篇首入口：本篇有笔记时给一条窄链，不把总论塞进条1
  let noteLink = '';
  if (zsite && zmode !== 'yuan'){
    const pn = (D.biji || []).filter(x => x.pian === it.pian).length;
    const first = D.items.find(x => x.pian === it.pian);
    if (pn && first && first.n === it.n){
      noteLink = `<div class="notelink" data-pian="${esc(it.pian)}">本篇笔记 <b>${pn}</b> 篇 · 点此查看 →</div>`;
    }
  }
  const tail = [...verCards, ...legacy, ...zother];
  const stickyZ = (zsite && zhuPick && zmain.length && mode !== 'pin' && zmode !== 'yuan')
    ? `<div class="zmainstick">${zmain.join('')}</div>` : '';
  pane.classList.toggle('stick', mode !== 'pin');   // 单列/双列/三列都吸顶；左固定右滑不吸
  pane.classList.toggle('haszmain', !!stickyZ);     // 底本+主注本合计限高 45vh
  pane.classList.toggle('allmode', zmode === 'all'); // 全览：坞内注文不折叠，留半屏给对照
  const fb = $('#fab');
  if (fb){ fb.classList.toggle('on', +mode > 1);
    fb.style.display = (zsite && zmode === 'zhu') ? 'none' : ''; }
  if (mode === 'pin'){
    // 左固定底本 + 右侧各版独立滚动（主注本仍排最前，但不做第二层吸顶）
    const pinCards = [noteLink, notice, ...(zsite && zhuPick && zmode !== 'yuan' ? zmain : []), ...tail].filter(Boolean);
    pane.innerHTML = `<div class="pinsplit"><div class="pinleft">${baseH}</div>`
      + `<div class="pinright" id="pinright">`
      + `<div class="pinhint">↑ 左为底本，右侧上下滑动看各版（${pinCards.length} 卡）</div>`
      + pinCards.join('') + '</div></div>';
    fitPin();
  } else if (cols > 1){
    // 瀑布流：底本与主注本置顶横跨，其余卡按「最短列优先」贪心分配
    pane.innerHTML = baseH + noteLink + stickyZ + `<div class="mflow" data-cols="${cols}">`
      + Array.from({length: cols}, () => '<div class="mcol"></div>').join('')
      + '</div>';
    flowCards([notice, ...tail].filter(Boolean));
  } else {
    pane.innerHTML = baseH + noteLink + stickyZ + notice + tail.join('');
  }
  syncStickTop();
  syncStickOffsets();
  requestAnimationFrame(syncStickOffsets);
  document.querySelector('main').scrollTop = 0;
  markSide();
  updateNav();
  // 深链:部分浏览器对 file:// 下的 replaceState 抛安全异常,须容错
  try { history.replaceState(null, '', '#' + it.n); }
  catch (e) { try { location.hash = it.n; } catch (e2) {} }
}

/* ---------- 移动版导航条：第 N / 465 条 + 上下 + 设置 ---------- */
function visList(){
  return [...document.querySelectorAll('#side .it')].map(x => +x.dataset.n);
}
function updateNav(){
  const tot = (D.expect || D.items.length);
  const elCur = $('#nav-cur'), elAll = $('#nav-all');
  if (elAll) elAll.textContent = tot;
  if (!elCur) return;
  elCur.textContent = cur ? cur.n : '-';
  // 篇名：纯 CSS 自适应（flex:1 1 0），这里只负责填文本。
  // 空间不足时 CSS 会把它压到 0 宽并裁掉文字，不占位、不换行。
  const ep = $('#nav-pian');
  if (ep){
    const txt = (cur && cur.pian || '').replace(/\s+/g, ' ').trim();
    ep.textContent = txt;
    ep.title = txt;              // 悬停可看全文
  }
  const vis = visList();
  const i = cur ? vis.indexOf(cur.n) : -1;
  const up = $('#nav-up'), dn = $('#nav-dn');
  if (up) up.disabled = (i <= 0);
  if (dn) dn.disabled = (i < 0 || i >= vis.length - 1);
}
function stepSel(d){
  const vis = visList();
  if (!vis.length) return;
  let i = cur ? vis.indexOf(cur.n) : -1;
  i = (i < 0) ? 0 : Math.min(vis.length - 1, Math.max(0, i + d));
  select(vis[i]);
  const el = document.querySelector(`#side .it[data-n="${vis[i]}"]`);
  if (el) el.scrollIntoView({block:'nearest'});
}

/* ---------- 统计条 + 版本统计页 ---------- */
function statRows(){
  const tot = D.items.length;
  const diff = D.items.filter(it => diffVers(it).length).length;
  const rows = [
    {a:'all', label:`骨架 <b>${tot}</b> 条（${esc(BASE())}）`},
    {a:'diff', label:`有异文 <b>${diff}</b> 条`},
  ];
  if (D.zhub && D.zhub.length){
    rows.push({a:'zhu', label:`有注文 <b>${Object.keys(D.zhu || {}).length}</b> 条 · 注本 <b>${D.zhub.length}</b> 部`});
    if ((D.biji || []).length) rows.push({a:'biji', label:`笔记 <b>${D.biji.length}</b> 篇（总论、篇级）`});
  }
  for (const v of VERS){
    const s = D.stats[v];
    rows.push({v, label:`${esc(v)}:对 <b>${s.hit}</b> · 高置信 <b>${s.hi}</b>`
      + (s.anc?` · 锚点 <b>${s.anc}</b>`:'') + ` · 独有 <b>${s.ind}</b>`});
  }
  return rows;
}
function buildStat(){
  const rows = statRows();
  $('#stat').innerHTML = rows.map(r =>
    r.v ? `<span class="u" data-v="${esc(r.v)}">${r.label}</span>`
        : `<span class="u" data-a="${r.a}">${r.label}</span>`).join('');
  bindStat($('#stat'));
  // 独立页面版（移动端入口在抽屉）
  const box = $('#statbox');
  if (box){
    box.innerHTML = '<div class="card"><div class="ch"><span class="vn">版本统计</span>'
      + '<span class="pg">点版本行可筛选</span></div><div class="cb2" style="font-size:14px">'
      + rows.map(r => `<div style="padding:5px 0">${r.label}</div>`).join('')
      + '</div></div>';
  }
}
function bindStat(root){
  root.querySelectorAll('.u[data-v]').forEach(el => el.onclick = () => {
    const v = el.dataset.v;
    $('#fVer').value = ($('#fVer').value === v) ? '' : v;
    buildSide();
  });
}

const ZERO_ROWS = [];   // 占位

/* ---------- 方剂 ---------- */
function buildFang(){
  const only = $('#fOnly').checked, v = $('#fVer2').value;
  const all = new Set();
  for (const vv of VERS) for (const k in D.fang[vv]) all.add(k);
  let rows = [...all].sort();
  if (v) rows = rows.filter(n => D.fang[v][n]);
  if (only && v) rows = rows.filter(n => Object.keys(D.fang).filter(x => D.fang[x][n]).length === 1);
  let h = `<table><thead><tr><th style="width:170px">方名</th>` +
    VERS.map(x => `<th>${esc(x)}</th>`).join('') + `</tr></thead><tbody>`;
  for (const n of rows){
    h += `<tr><td><b>${esc(n)}</b></td>`;
    for (const vv of VERS){
      const c = D.fang[vv][n];
      h += c ? `<td class="has"><span class="pg">p${c.pg}</span><div class="zc">${esc((c.zc||'').slice(0,120))}</div></td>`
             : `<td class="no">—</td>`;
    }
    h += '</tr>';
  }
  h += '</tbody></table>';
  let st = '<div style="margin:14px 0 6px;font-weight:700">各版方剂统计</div><div>';
  for (const vv of VERS){
    const s = D.fangStat[vv];
    st += `<div class="kv" style="margin-bottom:3px"><b>${esc(vv)}</b>:共 ${s.n} 方,该版独有 <b>${s.only.length}</b> 方
      ${s.only.length ? ' — ' + esc(s.only.slice(0,16).join('、')) : ''}</div>`;
  }
  $('#fangbox').innerHTML = h + st + '</div>';
  $('#cnt2').textContent = rows.length + ' 方';
}

/* ---------- 篇级 ---------- */
function buildPian(){
  // ① 底本无编号篇 × 各版 对照矩阵 —— 这是「真正无条号篇章」的归属字段。
  //    判据:该版篇目表有同名篇(取字数),或独有文本流出现过该篇标题行。
  //    金匮 24 篇全部编条号,本块无内容 → 整块略去(2026-11-13)
  const showSpian = (D.spian || []).length > 0;
  let h = '';
  if (showSpian){
    h += '<div class="card"><div class="ch"><span class="vn">宋本无编号篇 × 各版</span>' +
      '<span class="pg">' + D.spian.length + ' 篇</span></div>' +
      '<div class="cb2" style="font-size:13px;color:var(--ink3);margin-bottom:8px">' +
      '骨架之外,另有下列**整篇无条号**的篇。数字为该版此篇字数,「—」为该版无此篇。' +
      '</div>';
  }
  if (showSpian){
    h += '<div style="overflow-x:auto"><table><thead><tr><th style="width:22%">宋本无编号篇</th>' +
      VERS.map(v => `<th style="width:auto">${esc(v)}</th>`).join('') + '</tr></thead><tbody>';
    for (const x of D.spian){
      const row = (D.spianMap && D.spianMap[x.n]) || {};
      h += '<tr><td>' + esc(x.n) + '</td>' + VERS.map(v => {
        const n = row[v] || 0;
        return n ? '<td class="kv" style="color:var(--ink)">' + n + '</td>'
                 : '<td class="kv" style="color:var(--ink3)">—</td>';
      }).join('') + '</tr>';
    }
    h += '</tbody></table></div>';
  }
  if (showSpian) h += '</div>';

  // ② 各版篇目 → 归属字段
  for (const v of VERS){
    const rows = D.pian[v];
    const nS = rows.filter(x => x.s).length;
    const nSp = rows.filter(x => x.sp).length;
    const nOwn = rows.filter(x => x.own).length;
    // 匹配率过低 = 本版体例与宋本不同,篇名不构成对照轴
    const alien = (nS + nSp) < rows.length * 0.2;
    h += `<div class="card"><div class="ch"><span class="vn">${esc(v)}</span><span class="pg">${rows.length} 篇</span></div>`;
    if (alien){
      h += '<div class="cb2" style="font-size:13px;color:var(--zhu);margin-bottom:8px">' +
        '⚠ 本版体例与宋本不同(篇名不构成对照轴):宋本编号篇 ' + nS + ' / 无编号篇 ' + nSp +
        ' / 本版独有篇 ' + nOwn + '。此处「本版独有篇」指篇名在宋本无对应,**不等于**内容独有。' +
        '</div>';
    }
    h += '<table><thead><tr><th style="width:30%">本版篇</th><th style="width:34%">归属</th>' +
      '<th style="width:16%">匹配分</th><th>字数</th></tr></thead><tbody>';
    for (const x of rows){
      let attr;
      if (x.s)      attr = '<span style="color:var(--ok)">宋本编号篇</span> ' + esc(x.s);
      else if (x.sp) attr = '<span style="color:var(--gold)">宋本无编号篇</span> ' + esc(x.sp);
      else          attr = '<span style="color:var(--zhu)">本版独有篇</span>';
      h += `<tr><td>${esc(x.v)}</td><td>${attr}</td>` +
        `<td class="kv">${x.sc}</td><td class="kv">${x.len}</td></tr>`;
    }
    h += '</tbody></table></div>';
  }
  $('#pianbox').innerHTML = h;
}

/* ---------- 独有序 ---------- */
function buildIndep(){
  // 搜索框同样作用于独有序 —— 5100+ 项独有序内容承载了各版独有的篇目
  // (桂林古本六气主客/温病/六淫、注解本成无己注文等),搜不到等于没有。
  const q = $('#q').value.trim();
  let h = '';
  let shown = 0, total = 0;
  for (const v of VERS){
    const all = D.indep[v] || [];
    total += all.length;
    const arr = q ? all.filter(it => (it.t||'').includes(q) || (it.id||'').includes(q)) : all;
    shown += arr.length;
    if (q && !arr.length) continue;
    const tag = q ? `${arr.length} / ${all.length} 项` : `${all.length} 项`;
    h += `<div class="card"><div class="ch"><span class="vn">${esc(v)}</span><span class="pg">${tag}</span></div>
      <div class="cb2" style="font-size:13.5px;line-height:1.9">`;
    for (const it of arr) h += `<div style="margin-bottom:6px"><b style="font-family:var(--sans);font-size:11.5px;color:var(--zhu)">${esc(it.id)}</b> <span class="pg">p${it.pg}</span><br>${esc(it.t)}</div>`;
    h += '</div></div>';
  }
  if (!shown){
    h = `<div class="card"><div class="cb2" style="font-size:13.5px">独有序中无匹配「${esc(q)}」的内容。</div></div>`;
  } else if (q){
    h += `<div style="font-size:12.5px;color:var(--ink3);margin-top:8px">独有序匹配:${shown} / ${total} 项(其余 ${total-shown} 项被搜索词过滤)</div>`;
  }
  $('#indepbox').innerHTML = h;
}

/* ---------- 笔记：总论、篇级与专题，不绑条号 ---------- */
function pianOrder(){
  const m = new Map(); let i = 0;
  for (const it of D.items){ if (!m.has(it.pian)) m.set(it.pian, i++); }
  return m;
}
function buildBiji(){
  const box = $('#bijibox'); if (!box) return;
  let arr = (D.biji || []).slice();
  if (bijiPick) arr = arr.filter(x => (((D.zhub || [])[x.b] || {}).id === bijiPick));
  if (bijiPian) arr = arr.filter(x => x.pian === bijiPian);
  const order = pianOrder(), groups = new Map();
  for (const x of arr){
    const k = x.pian || '全书·读法';
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(x);
  }
  const keys = [...groups.keys()].sort((a, b) => {
    if (a === '全书·读法') return -1;
    if (b === '全书·读法') return 1;
    return (order.get(a) ?? 999) - (order.get(b) ?? 999);
  });
  let h = '';
  for (const k of keys){
    const list = groups.get(k);
    h += `<div class="bgroup">${esc(k.replace(/\s+/g,' '))}<span class="c">${list.length} 篇</span></div>`;
    for (const x of list){
      const b = (D.zhub || [])[x.b] || {};
      const txt = x.t || '';
      const long = txt.length > 240 || txt.split('\n').length > 5;
      const meta = [];
      if (x.scope === 'book') meta.push('全书');
      if (x.pg != null) meta.push('p' + x.pg);
      h += `<div class="card biji${long ? '' : ' short'}">
        <div class="ch"><span class="vn">${esc(x.title || '笔记')}</span>
        <span class="tag t-zhu">笔记</span>
        <span class="pg">${esc(b.name || b.id || '')}</span>
        ${meta.length ? `<span class="pg">${esc(meta.join(' · '))}</span>` : ''}
        ${long ? `<span class="pg">${txt.length} 字</span>` : ''}
        ${long ? '<button class="zclose">收起</button>' : ''}</div>
        <div class="cb2 ztxt">${ztxt(txt)}</div>
        ${long ? '<button class="zmore">展开全文</button>' : ''}</div>`;
    }
  }
  box.innerHTML = h || '<div class="empty">此筛选下没有笔记</div>';
  const bc = $('#biji-cnt'); if (bc) bc.textContent = arr.length + ' 篇';
  const cb = $('#c-biji'); if (cb) cb.textContent = (D.biji || []).length || '';
  wrapTables();
}
function openBiji(pian){
  bijiPian = pian || '';
  fillSel();
  const t = document.querySelector('#tabs .tab[data-v="biji"]');
  if (t) t.click();
  buildBiji();
}
function nextZhu(n){
  const arr = D.items.filter(it => hasNote(it.n)).map(it => it.n).sort((a,b) => a-b);
  const nx = arr.find(x => x > n);
  if (nx) select(nx); else toast('后面没有更多有注的条');
}

/* ---------- 待复核 ---------- */
function buildReview(){
  const h = `<table><thead><tr><th style="width:70px">条号</th><th style="width:120px">版本</th>
    <th style="width:110px">状态</th><th style="width:60px">页</th><th>摘要</th></tr></thead><tbody>` +
    D.review.map(r => `<tr><td><b>${r.n}</b></td><td>${esc(r.v)}</td><td>${esc(r.st)}</td>
      <td class="pg">${r.pg?'p'+r.pg:''}</td><td>${esc(r.t)}</td></tr>`).join('') + '</tbody></table>';
  $('#revbox').innerHTML = h;
}

/* ---------- 体例说明 ---------- */
function buildAbout(){
  const isSH = !(D.skel && D.skel.id === 'jingui');
  const kj = isSH
    ? `· <b>骨架</b>:__SKEL_NAME__(骨架性质:__SKEL_KIND__)
  依「每条只认期望的下一个编号」逐位校验切出,零缺号;仅条 154 的编号被 OCR 残损(--五四),已按位修复。<br>
· <b>对齐</b>:以内容比对为主(字符 n-gram 召回 + 短文本覆盖率排序),辅以位置单调性约束;
  编者校记所注「同《宋本伤寒论》第X条」优先采用(硬锚点)。<br>
· <b>此版无</b>:一律注明原因与原文依据,不以推测填补;理由分「选集未收 / 本版仅残卷 / 原书残损 / 体例不同 / 暂未匹配」。<br>
· <b>转录</b>:本对照基于影印扫描件的逐页转录,反映影印本字面,未作校订;异体字、通假字一仍其旧,正式引用请核对原页。`
    : `· <b>骨架</b>:赵开美本《金匮要略方论》(1599) 条级 465 条 / 24 篇,条内下钻 1316 段。骨架全编条号,故无「无编号篇」。<br>
· <b>取数</b>:四版各有出处 —— 人卫用条级参照系(A10),俞桥/医统用段级核定表(A3/A4),邓珍用渲染件定槽+人工裁定;
  不逐字相同者按覆盖率定高低置信,能取到几分就写几分,不补。<br>
· <b>此版无(四种)</b>:①本版分条较粗、并入前条 ②人工裁定确认本版无此条 ③本版无对应段 ④未核实(照实写「未核实」)。<br>
· <b>转录</b>:各版字面照录,不校订;医统本含私用区缺字字符,页面显示为方框,原件如此。`;
  let h = `<div class="card"><div class="ch"><span class="vn">口径</span></div><div class="cb2" style="font-size:14px">${kj}<br>
· <b>不臆造</b>:某版没有的条文只标「此版无」并给出依据;各版多出的内容给独立章节 ID,单列《版本独有内容》。</div></div>

<div class="card"><div class="ch"><span class="vn">字段说明</span></div><div class="cb2" style="font-size:14px;line-height:1.9">
<b>条号</b>（顶部「N / 总数 条」）—— 骨架条号，本书的统一坐标。${isSH?'宋本共 398 条。':'赵开美本共 465 条。'}<br>
<b>页码 pN</b> —— <b>该版本影印件自身的实体书页</b>，不是总页数、也不是条号。用于回查原书扫描件：
在影印本里翻到第 N 页，即可看到该条原文。<br>
&nbsp;&nbsp;· 底座（${esc(BASE())}）页码范围：${(()=>{const ps=D.items.map(x=>x.pg).filter(x=>x!=null); return ps.length?(Math.min(...ps)+'–'+Math.max(...ps)):'—';})()}<br>
&nbsp;&nbsp;· 各版页码范围：${VERS.map(v=>{const ps=D.items.map(x=>x.v[v]&&x.v[v].ok?x.v[v].pg:null).filter(x=>x!=null); return ps.length?`${esc(v)} ${Math.min(...ps)}–${Math.max(...ps)}`:'';}).filter(Boolean).join('；')}<br>
&nbsp;&nbsp;· 各版页数范围不同，是因为各版篇幅、分卷与扫描起讫不同，<b>同一页号在不同版本指向不同内容，不可跨版比较</b>。<br>
<b>篇名</b> —— 显示在顶部条号右侧，过长时省略；原件篇题多含「合一十六法 方一十四首」这类统计语，属原书体例，保留不删。
</div></div>`;
  // 各版体例佐证：没有数据就不出空卡片（金匮侧尚未登记 cover）
  if (Object.keys(D.cover || {}).length){
    h += '<div class="card"><div class="ch"><span class="vn">各版「此版无」主因与原文依据</span></div><div class="cb2" style="font-size:14px">';
    for (const v of VERS){
      const c = D.cover[v];
      if (!c) continue;
      h += `<div style="margin-bottom:9px"><b>${esc(v)}</b> —— ${esc(c.kind)}<br>
        <span class="kv">${esc(c.evid)}</span></div>`;
    }
    h += '</div></div>';
  }
  // 注释本（L2）：只报注本自身状况，不评价其说解
  if (D.zhub && D.zhub.length){
    h += `<div class="card"><div class="ch"><span class="vn">注释本</span>
      <span class="pg">${D.zhub.length} 部</span></div><div class="cb2" style="font-size:13.5px">
      <div class="kv" style="margin-bottom:9px">注文一律锚在骨架条号上，与各版原文并列，不改动原文；
      只记录注本说了什么，不判断其对不对。页码 pN 是注本自身的实体书页，未得则空。</div>
      <div class="tscroll"><table><thead><tr><th>注本</th><th>所注</th><th>条注</th>
      <th>笔记</th><th>覆盖</th><th>状态</th></tr></thead><tbody>`
      + D.zhub.map(b => `<tr><td><b>${esc(b.name)}</b>${b.base ? `<div class="kv" style="color:var(--ink3)">${esc(String(b.base).slice(0,60))}</div>` : ''}</td>
        <td class="kv">${esc((b.targets || []).join('、'))}</td>
        <td>${b.n != null ? b.n : ''}</td>
        <td>${b.biji != null ? b.biji : ''}</td>
        <td class="kv">${esc(b.cover || '')}</td>
        <td class="kv">${esc(b.status || '')}</td></tr>`).join('')
      + `</tbody></table></div></div></div>`;
  }
  h += `<div class="card"><div class="ch"><span class="vn">统计</span></div><div class="cb2" style="font-size:14px"><table>
    <thead><tr><th>版本</th><th>对上骨架条数</th><th>高置信</th><th>校记锚点</th><th>独立内容</th></tr></thead><tbody>`;
  for (const v of VERS){
    const s = D.stats[v];
    h += `<tr><td><b>${esc(v)}</b></td><td>${s.hit}</td><td>${s.hi}</td><td>${s.anc}</td><td>${s.ind}</td></tr>`;
  }
  h += '</tbody></table></div></div>';
  $('#aboutbox').innerHTML = h;
}

/* ---------- 交互 ---------- */
/* ---------- 运行时完整性自检 ----------
   数据若在生成/传输中被截断,页面必须**明确报出来**,而不是静默少一半。
   校验:条目数、版本数、每条各版格数、方剂/独有统计自洽、注文键合法、无编号篇非空。 */
let _integTimer = null;
function banner(msg, bad){
  let d = document.getElementById('integrity');
  if (!d){ d = document.createElement('div'); d.id = 'integrity';
    document.body.appendChild(d); }
  d.className = 'integrity' + (bad ? ' bad' : '');
  d.textContent = msg;
  d.style.display = 'block';
  d.classList.remove('hide');
  if (_integTimer){ clearTimeout(_integTimer); _integTimer = null; }
  // 正常通过：3 秒后淡出并移出布局；异常（bad）：常驻，必须让人看见
  if (!bad){
    _integTimer = setTimeout(() => {
      d.classList.add('hide');
      setTimeout(() => { if (d.classList.contains('hide')) d.style.display = 'none'; }, 500);
    }, 3000);
  }
}
function checkIntegrity(){
  const errs = [];
  if (!D || !D.items) { errs.push('viewer_data 未载入'); }
  else {
    if (D.items.length !== D.expect) errs.push('条目数 ' + D.items.length + ' ≠ ' + D.expect);
    const nv = (D.vers || []).length;
    // 版本数以数据自带为准(SH=9,JG=5);显式声明 nVers 时按其校验
    if (D.nVers && nv !== D.nVers) errs.push('对照版本数 ' + nv + ' ≠ ' + D.nVers);
    let badCell = 0, blank = 0;
    for (const it of D.items){
      const ks = Object.keys(it.v || {});
      if (ks.length !== nv) badCell++;
      for (const v of ks){
        const c = it.v[v];
        if (!c) { blank++; continue; }
        if (c.ok && !(c.d || c.t)) blank++;
      }
    }
    if (badCell) errs.push(badCell + ' 条的版本格数不符');
    if (blank)     errs.push(blank + ' 格内容为空');
    for (const v of (D.vers || [])){
      const st = (D.stats || {})[v];
      if (!st) { errs.push('缺 stats:' + v); continue; }
      const ind = ((D.indep || {})[v] || []).length;
      if (ind !== st.ind) errs.push(v + ' 独有序 ' + ind + ' ≠ stats ' + st.ind);
    }
    // 注文：条号必须落在骨架内，b 必须指向已登记注本，总数须与注本表声明一致
    if (D.zhu){
      const ns = new Set(D.items.map(x => x.n));
      const outside = Object.keys(D.zhu).map(Number).filter(n => !ns.has(n));
      if (outside.length) errs.push(outside.length + ' 个注文条号不在骨架内:' + outside.slice(0,5).join('、'));
      let badb = 0, cnt = 0;
      for (const k in D.zhu) for (const r of D.zhu[k]){ cnt++; if (!(D.zhub || [])[r.b]) badb++; }
      if (badb) errs.push(badb + ' 条注文指向未登记的注本');
      const declared = (D.zhub || []).reduce((a, b) => a + (b.n || 0), 0);
      if (declared && declared !== cnt) errs.push('注文实收 ' + cnt + ' 条 ≠ 注本表声明 ' + declared);
      D._zn = cnt;
    }
    // 笔记：b 必须指向已登记注本，标题必填，总数与注本表一致
    if (D.biji){
      let cnt = 0, badb = 0, notitle = 0;
      for (const r of D.biji){
        cnt++;
        if (!(D.zhub || [])[r.b]) badb++;
        if (!(r.title || '').trim()) notitle++;
      }
      if (badb) errs.push(badb + ' 篇笔记指向未登记的注本');
      if (notitle) errs.push(notitle + ' 篇笔记缺标题');
      const declaredB = (D.zhub || []).reduce((a, b) => a + (b.biji || 0), 0);
      if (declaredB && declaredB !== cnt) errs.push('笔记实收 ' + cnt + ' 篇 ≠ 注本表声明 ' + declaredB);
      D._bn = cnt;
    }
    // 底本无编号篇:非空 + 不混有编号篇 + 矩阵齐全
    // 金匮 24 篇全编条号,本字段本就为空,不该按「失真」报错
    const spian = D.spian || [];
    const needSpian = (D.skel && D.skel.id === 'shanghan');
    if (!spian.length && needSpian) errs.push('宋本无编号篇为空(篇级对照将失真)');
    else if (spian.length) {
      const numbered = new Set(D.numberedPian || []);
      const bad = spian.map(x => x.n).filter(n => numbered.has(n));
      if (bad.length) errs.push('无编号篇清单混入有编号篇 ' + bad.length + ' 个:' + bad.slice(0,3).join('、'));
      if (!D.spianMap) errs.push('缺 spianMap(无编号篇×各版矩阵)');
      else {
        const miss = spian.filter(x => !D.spianMap[x.n]).length;
        if (miss) errs.push('spianMap 缺 ' + miss + ' 行');
      }
    }
  }
  if (errs.length){ banner('⚠ 数据完整性自检未通过:' + errs.join(';'), true); return false; }
  banner('✓ 数据完整性自检通过:' + D.items.length + ' 条 × ' + (D.vers||[]).length +
         ' 版' + (D.spian.length ? ',无编号篇 ' + D.spian.length + ' 个' : '') +
         (D.zhub && D.zhub.length ? ',注本 ' + D.zhub.length + ' 部 / 注文 ' + (D._zn||0) + ' 条 / 笔记 ' + (D._bn||0) + ' 篇' : '') +
         (Object.keys(D.notes||{}).length ? ',L1 遗留注 ' + Object.keys(D.notes||{}).length + ' 条' : ''),
         false);
  return true;
}

function toast(t){ const e = $('#toast'); e.textContent = t; e.classList.add('on');
  setTimeout(()=>e.classList.remove('on'), 1600); }

function wrapTables(){
  document.querySelectorAll('main table').forEach(t=>{   // <main> 没有 id，别写 #main
    const p = t.parentElement;
    if (p && p.classList.contains('tscroll')) return;
    const d = document.createElement('div');
    d.className = 'tscroll';
    p.insertBefore(d, t); d.appendChild(t);
  });
}
function buildAll(){
  buildStat(); buildSide(); select(cur ? cur.n : D.items[0].n);
  buildFang(); buildPian(); buildBiji(); buildIndep(); buildReview(); buildAbout();
  wrapTables();
}
function fillSel(){
  const zsite = isZhuSite();
  const o1 = VERS.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
  $('#fVer').innerHTML = '<option value="">全部</option>' + o1;
  $('#fVer2').innerHTML = '<option value="">全部</option>' + o1;
  const f3 = $('#fVer3');
  if (f3) f3.innerHTML = '<option value="">全部</option>' + o1;
  // 看法：只有注释本站有意义；骨架版固定原文
  ['#readsel','#readsel2'].forEach(s => { const e = $(s);
    if (e){ e.value = readMode; const w = e.closest('label'); if (w) w.style.display = zsite ? 'flex' : 'none'; } });
  // 视图：读注固定单列，控件收起；原文/全览可用
  const wide = window.innerWidth >= 600, wider = window.innerWidth >= 1000;
  const opts = ['1', ...(wide ? ['2'] : []), ...(wider ? ['3'] : []), 'pin'];
  if (!opts.includes(viewMode)) viewMode = '1';
  ['#colsel','#colsel2'].forEach(s => { const e = $(s);
    if (!e) return;
    e.innerHTML = '<option value="1">单列</option>'
      + (wide ? '<option value="2">双列</option>' : '')
      + (wider ? '<option value="3">三列</option>' : '')
      + '<option value="pin">左固定右滑</option>';
    e.value = viewMode;
    const w = e.closest('label'); if (w) w.style.display = (zsite && readMode === 'zhu') ? 'none' : 'flex';
  });
  // 差异 / 只看有注文：状态回填
  ['#fDiffMode','#fDiffMode2'].forEach(s => { const e = $(s); if (e) e.value = diffMode; });
  ['#fZhu','#fZhu2'].forEach(s => { const e = $(s); if (e) e.checked = zhuOnly; });
  const showZ = zsite && readMode === 'zhu' && !zhuPick;
  ['#fZhuWrap','#fZhuWrap2'].forEach(s => { const e = $(s); if (e) e.style.display = showZ ? 'flex' : 'none'; });
  // 笔记页注本筛选
  const bs = $('#bijiSel');
  if (bs){
    const cnt = {};
    for (const x of (D.biji || [])) cnt[x.b] = (cnt[x.b] || 0) + 1;
    bs.innerHTML = '<option value="">全部笔记</option>'
      + (D.zhub || []).map((b, i) => cnt[i] ? `<option value="${esc(b.id)}">${esc(b.name || b.id)}（${cnt[i]}）</option>` : '').join('');
    bs.value = bijiPick;
  }
  const cb = $('#c-biji'); if (cb) cb.textContent = (D.biji || []).length || '';
  const bt = document.querySelector('#tabs .tab[data-v="biji"]');
  if (bt) bt.style.display = (D.biji || []).length ? '' : 'none';
  const chip = $('#bijiPianChip');
  if (chip){
    chip.style.display = bijiPian ? 'inline-flex' : 'none';
    chip.innerHTML = bijiPian ? `篇：${esc(bijiPian.replace(/\s+/g,' '))} <b data-clear-pian="1">✕</b>` : '';
  }
}
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
  document.querySelectorAll('.view').forEach(x => x.classList.remove('on'));
  t.classList.add('on'); curTab = t.dataset.v;
  $('#v-' + curTab).classList.add('on');
  if (curTab === 'cmp') buildSide();
  if (curTab === 'biji') buildBiji();
  document.querySelector('main').scrollTop = 0;
  syncStickTop();
  syncDnav();
});
/* 抽屉内「视图」入口（移动端 tab 行不显示，从这里进） */
function buildDnav(){
  const box = $('#dnav'); if (!box) return;
  const T = [...document.querySelectorAll('#tabs .tab')].filter(t => t.style.display !== 'none');
  box.innerHTML = '<div class="dt">视图</div>' + T.map(t => {
    const lbl = t.textContent.replace(/\s+/g,'');
    return `<button data-v="${t.dataset.v}">${esc(lbl)}</button>`;
  }).join('');
  box.querySelectorAll('button').forEach(b => b.onclick = () => {
    const t = document.querySelector(`#tabs .tab[data-v="${b.dataset.v}"]`);
    if (t) t.click();
    drawer(false);
  });
  syncDnav();
}
function syncDnav(){
  document.querySelectorAll('#dnav button').forEach(b =>
    b.classList.toggle('on', b.dataset.v === curTab));
}
/* ── 手机竖屏:目录抽屉 ──
   窄屏时侧栏默认移出屏外，点 ☰ 拉开、点遮罩/选项/Esc 收起。宽屏不受影响。 */
function drawer(open){
  const a = $('#side'); if (!a) return;
  a.classList.toggle('open', !!open);
  const m = $('#mask'); if (m) m.classList.toggle('on', !!open);
  if (open){                       // 拉开时把当前条滚到眼前，省得自己找
    const sel = a.querySelector('.it.on');
    // 留出抽屉头的高度，别让当前条被压在「目录/✕」下面
    if (sel) a.scrollTop = Math.max(0, sel.offsetTop - 70);
    else a.scrollTop = 0;
  }
}
const isNarrow = () => window.matchMedia('(max-width:820px)').matches;
$('#menu').onclick = () => drawer(!$('#side').classList.contains('open'));
$('#mask').onclick = () => drawer(false);
$('#dclose').onclick = () => drawer(false);

// 事件委托:绑定在容器上,侧栏重建后依然有效
$('#side').addEventListener('click', e => {
  const el = e.target.closest('.it');
  if (el) { select(+el.dataset.n); if (isNarrow()) drawer(false); return; }
  const gh = e.target.closest('.gh');
  if (gh) { const b = gh.nextElementSibling;
    b.style.display = (b.style.display === 'none') ? 'block' : 'none'; }
});
window.addEventListener('error', e => toast('出错了:' + e.message));
window.addEventListener('resize', () => {
  if ($('#detail .pinsplit')) fitPin();
  syncStickTop(); syncStickOffsets();
});
$('#q').oninput = () => { $('#qclr').style.display = $('#q').value ? 'block' : 'none'; buildSide(); buildIndep(); };
$('#qclr').onclick = () => { $('#q').value = ''; $('#qclr').style.display = 'none'; buildSide(); $('#q').focus(); };
$('#fVer').onchange = () => { const e=$('#fVer3'); if(e) e.value=$('#fVer').value; buildSide(); };
$('#fSt').onchange  = () => { const e=$('#fSt2');  if(e) e.value=$('#fSt').value;  buildSide(); };
$('#fVer3').onchange = () => { $('#fVer').value = $('#fVer3').value; buildSide(); };
$('#fSt2').onchange  = () => { $('#fSt').value  = $('#fSt2').value;  buildSide(); };
['#fZhu','#fZhu2'].forEach(s => { const e=$(s); if (e) e.onchange = () => setZhuOnly(e.checked); });
['#fDiffMode','#fDiffMode2'].forEach(s => { const e=$(s); if (e) e.onchange = () => setDiff(e.value); });
['#readsel','#readsel2'].forEach(s => { const e=$(s); if (e) e.onchange = () => setRead(e.value); });
function toggleFbox(id, btn){
  const b=$(id); if(!b) return;
  b.classList.toggle('open');
  const t=$(btn); if(t) t.classList.toggle('on', b.classList.contains('open'));
  syncStickTop();
}
$('#filterbtn').onclick = () => toggleFbox('#fbox','#filterbtn');
$('#filterbtn2').onclick = () => toggleFbox('#fbox2','#filterbtn2');
/* 悬浮按钮：单列 ⇄ 双列。走状态，不读 select 的当前值。 */
$('#fab').onclick = () => {
  const next = viewMode === '1' ? '2' : '1';
  setView(next);
  $('#fab').classList.toggle('on', viewMode !== '1');
  toast(viewMode === '1' ? '单列' : '双列对照');
};
$('#nav-set').onclick = () => {
  const r = $('#setrow');
  const open = !r.classList.contains('open');
  r.classList.toggle('open', open);
  $('#nav-set').style.background = open ? 'var(--hl)' : '#fff';
  syncStickTop(); syncStickOffsets();
};
function resetFilters(){
  setDiff('');
  setZhuOnly(true);
  $('#fVer').value = ''; $('#fSt').value = '';
  const a=$('#fVer3'); if(a) a.value='';
  const b=$('#fSt2'); if(b) b.value='';
  buildSide();
}
$('#freset').onclick = resetFilters;
$('#freset2').onclick = resetFilters;
$('#bijiSel').onchange = () => { bijiPick = $('#bijiSel').value || ''; buildBiji(); };
document.addEventListener('click', e => {
  const cl = e.target && e.target.closest && e.target.closest('[data-clear-pian]');
  if (cl){ bijiPian=''; fillSel(); buildBiji(); return; }
});
/* 设置行与桌面筛选行双向同步：改一处，另一处跟着变，不出现两套状态 */
function syncFilters(){
  const f3 = $('#fVer3'); if (f3) f3.value = $('#fVer').value;
  const s2 = $('#fSt2');  if (s2) s2.value  = $('#fSt').value;
  const n = D.items.filter(makeMatch()).length;
  const sn = $('#set-note'); if (sn) sn.textContent = n + ' / ' + D.items.length;
}
document.addEventListener('change', e => {
  const id = e.target && e.target.id;
  if (id === 'baseSel' && e.target.value !== basePick) return setBase(e.target.value);
  if (id === 'zhuSel'  && e.target.value !== zhuPick)  return setZhu(e.target.value);
  if ((id === 'colsel' || id === 'colsel2') && e.target.value !== viewMode) return setView(e.target.value);
});
/* Safari 上个别版本先发 input 不发 change；值不同才处理，避免双渲染 */
document.addEventListener('input', e => {
  if (e.target && (e.target.id === 'colsel' || e.target.id === 'colsel2') && e.target.value !== viewMode) setView(e.target.value);
});
/* 注文卡展开/收起：事件委托，卡片每次 select 重渲染后不必重绑 */
document.addEventListener('click', e => {
  const ub = e.target && e.target.closest && e.target.closest('.usebase');
  if (ub){ setBase(''); return; }
  const nl = e.target && e.target.closest && e.target.closest('.notelink');
  if (nl){ openBiji(nl.dataset.pian || ''); return; }
  const lc = e.target && e.target.closest && e.target.closest('.locate');
  if (lc){
    const n = lc.dataset.n, s0 = +lc.dataset.sent;
    const s1 = lc.dataset.sent2 != null ? +lc.dataset.sent2 : s0;
    const els = [];
    for (let k = s0; k <= s1; k++){
      const el = document.querySelector(`#detail .sent[data-n="${n}"][data-i="${k}"]`);
      if (el) els.push(el);
    }
    if (els.length){
      els[0].scrollIntoView({block:'center', behavior:'smooth'});
      els.forEach(el => el.classList.add('hl'));
      setTimeout(() => els.forEach(el => el.classList.remove('hl')), 2200);
    }
    return;
  }
  const nz = e.target && e.target.closest && e.target.closest('.nextzhu');
  if (nz && cur){ nextZhu(cur.n); return; }
  const cl = e.target && e.target.closest && e.target.closest('.zclose');
  if (cl){
    const c2 = cl.closest('.card');
    if (c2){
      c2.classList.remove('open');
      const mb = c2.querySelector('.zmore'); if (mb) mb.textContent = '展开全文';
      if (c2.closest('.zmainstick')){ const d=$('#detail'); if (d) d.classList.remove('expandz'); }
      const m=document.querySelector('main'); if (m && c2.getBoundingClientRect().top < 0) c2.scrollIntoView({block:'start'});
    }
    return;
  }
  const btn = e.target && e.target.closest && e.target.closest('.zmore');
  if (!btn) return;
  const card = btn.closest('.card.zhu, .card.biji');
  if (!card) return;
  const on = card.classList.toggle('open');
  btn.textContent = on ? '收起' : '展开全文';
  // 吸顶坞里的注文：展开同时把坞放平，否则只是在小窗口里滚
  if (card.closest('.zmainstick')){
    const d = $('#detail');
    if (d) d.classList.toggle('expandz', on);
    if (on) requestAnimationFrame(syncStickOffsets);
  }
});
$('#copy').onclick = () => {
  if (!cur) return;
  const zsite = isZhuSite();
  let md = `### 条 ${cur.n} 〔${cur.pian}〕\n\n**${BASE()}**(p${cur.pg}):${cur.s}\n`;
  if (!zsite || readMode === 'yuan'){
    for (const v of VERS){
      const c = cur.v[v];
      md += c.ok ? `- **${v}**(${c.cf},p${c.pg}):${c.d || c.t}\n`
                 : `- **${v}**:此版无 —— **${c.rs}**。依据:${c.ev}\n`;
    }
  } else {
    const arr = ((D.zhu && D.zhu[cur.n]) || []).filter(r => {
      if (!zhuPick) return true;
      return (((D.zhub || [])[r.b] || {}).id === zhuPick);
    });
    for (const r of arr){
      const b = (D.zhub || [])[r.b] || {};
      const meta = [r.seg ? '第' + r.seg + '段' : '', r.attr || '', r.pg != null ? 'p' + r.pg : '']
        .filter(Boolean).join(' · ');
      md += `\n**${b.name || b.id}**${meta ? '（' + meta + '）' : ''}:\n${r.t || ''}\n`;
    }
  }
  navigator.clipboard.writeText(md).then(()=>toast('已复制本条 Markdown'),
    ()=>toast('复制失败,请手动选取'));
};
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT'){
    if (e.key === 'Escape') e.target.blur();
    return;
  }
  if (e.key === 'Escape'){ drawer(false); return; }
  if (e.key === '/'){ e.preventDefault(); $('#q').focus(); return; }
  if (curTab !== 'cmp') return;
  if (e.key === 'j' || e.key === 'k'){
    stepSel(e.key === 'j' ? 1 : -1);
  }
});
/* ---------- 双区(SH / JG)切换 ----------
   两个区是两套独立编号空间,共用同一套视图;切区=换数据源并重建全部面板。 */
function refreshCounts(){
  $('#c-fang').textContent = Object.values(D.fang||{}).reduce((a,v)=>a+Object.keys(v).length,0);
  $('#c-indep').textContent = VERS.reduce((a,v)=>a+(((D.indep||{})[v])||[]).length,0);
  $('#c-rev').textContent = (D.review||[]).length;
  const cb = $('#c-biji'); if (cb) cb.textContent = (D.biji||[]).length || '';
}
function loadZone(i){
  if (!ZONES[i]) return;
  ZI = i;
  const z = ZONES[i];
  D = z.data || {}; VERS = D.vers || [];
  cur = null; curTab = 'cmp'; bijiPick = ''; bijiPian = '';
  drawer(false);
  $('#ttl').textContent = z.title || (z.name || '') + '多版本对照';
  $('#skn').textContent = (D.skel && D.skel['名称']) || '';
  document.title = $('#ttl').textContent;
  document.querySelectorAll('#zsw button').forEach((b,k)=>b.classList.toggle('on', k===i));
  document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on', b.dataset.v==='cmp'));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('on', v.id==='v-cmp'));
  // 注意别清 #side：抽屉头 .dhd 在里面，清空会把「目录/✕」一起抹掉，
  // 之后 buildSide 找不到 #sidelist 会抛错（2026-11-13 踩过）
  ['#detail','#fangbox','#pianbox','#indepbox','#revbox','#aboutbox']
    .forEach(s=>{ const e=$(s); if (e) e.innerHTML=''; });
  $('#q').value=''; $('#qclr').style.display='none';
  ['#fDiffMode','#fDiffMode2'].forEach(k=>{ const e=$(k); if (e) e.value=diffMode; });
  if ($('#fSt')) $('#fSt').value='';
  if ($('#fSt2')) $('#fSt2').value='';
  // 深链必须在 buildAll 之前读取:buildAll 内的 select 会改写 hash(旧版踩过)
  const h = +location.hash.replace('#','');
  if (h && D.items.some(x => x.n === h)) select(h);   // 深链：#条号 直达（2026-11-27 补回，之前被误删）
  // 注文索引 + 筛选可见性：没有注文的站点（骨架版 gujia）不显示这个勾选框，避免给出空功能
  ZHUHAY = {};
  if (D.zhu) for (const k in D.zhu) ZHUHAY[k] = D.zhu[k].map(r => r.t).join(' ');
  const hasZhu = Object.keys(ZHUHAY).length > 0;
  ['#fZhuWrap','#fZhuWrap2'].forEach(s => { const e = $(s); if (e) e.style.display = hasZhu ? 'flex' : 'none'; });
  if ($('#fZhu')) $('#fZhu').checked = false;
  if ($('#fZhu2')) $('#fZhu2').checked = false;
  loadPrefs();
  refreshCounts(); fillSel(); buildDnav(); checkIntegrity(); buildAll();
  const _sd = $('#side'); if (_sd) _sd.scrollTop = 0;   // 换区后目录回到顶部
  if (h && D.items.some(x=>x.n===h)) select(h);
  try{
    const u = new URL(location.href);
    u.searchParams.set('zone', i);
    history.replaceState(null, '', u.href);
  }catch(e){}
}
async function boot(){
  document.documentElement.setAttribute('data-boot','start');
  const bt = document.getElementById('boot'), bm = document.getElementById('bootmsg'), br = document.getElementById('bootretry');
  if (bt){ bt.classList.remove('off','err'); if (br) br.hidden = true; }
  if (bm) bm.textContent = '正在加载数据…';
  try{
    // fetch 发布模式：index.html 只带模板，数据从 data/zones.json 取。
    // file:// 下 fetch 会被 CORS 拒绝，此时给出明确提示（改用 http(s) 或单文件版）。
    if (window.__SHJ_FETCH__ && !(ZONES && ZONES.length)){
      const r = await fetch('data/zones.json', {cache:'no-store'});
      if (!r.ok) throw new Error('HTTP ' + r.status);
      ZONES = await r.json();
    }
  }catch(e){
    if (bt) bt.classList.add('err');
    if (bm) bm.innerHTML = '数据加载失败：' + esc(e.message || e)
      + '<br><span style="font-size:12.5px;color:var(--ink3)">检查网络后点「重试」；若以 file:// 打开，请改用 http(s) 或单文件版</span>';
    if (br) br.hidden = false;
    banner('数据加载失败：' + e.message + '（请通过 http(s) 访问；file:// 不支持 fetch，可改用单文件版）', true);
    return;
  }
  const sw = $('#zsw');
  if (ZONES.length > 1){
    sw.style.display = 'flex';
    ZONES.forEach((z,i)=>{
      const b = document.createElement('button');
      b.textContent = z.name || z.id;
      if (z.sub) b.title = z.sub;
      b.onclick = () => loadZone(i);
      sw.appendChild(b);
    });
  }
  const m = /[?&]zone=(\d+)/.exec(location.search);
  const t = new URLSearchParams(location.search).get('tab');
  try{
    loadZone(m ? Math.min(+m[1], ZONES.length-1) : 0);
    if (t){ const b = document.querySelector(`.tab[data-v="${t}"]`); if (b) b.click(); }
  }finally{
    document.documentElement.setAttribute('data-boot','end');
    if (bt){ bt.classList.add('off'); bt.style.display = 'none'; }
  }
}
// 上下条按钮：之前只绑了键盘 j/k，按钮本身没绑（2026-11-27 修）
const _nu = $('#nav-up'), _nd = $('#nav-dn');
if (_nu) _nu.onclick = () => stepSel(-1);
if (_nd) _nd.onclick = () => stepSel(1);
const _br = $('#bootretry');
if (_br) _br.onclick = () => boot();
boot();
</script>
</body>
</html>
"""

if SPLIT:
    # ── 双文件维护版 ──
    #   注意:file:// 下 fetch('data.json') 会被浏览器以 Origin null 拒绝(实测 Failed to fetch),
    #   故此处用 <script src> 外链(data.js),file:// 与 http:// 下均可正常加载。
    #   单文件版仍是主交付形态(可直接双击打开、便于发给他人)。
    import os as _os
    base = _os.path.splitext(DST)[0]
    js_path = base + "_data.js"
    with open(js_path, "w", encoding="utf-8") as fh:
        fh.write("window.__SHJ_DATA__ = " + DATA + ";" + chr(10))
    tag = '<script src="' + _os.path.basename(js_path) + '"></script>'
    out = (HTML.replace("__DATA_TAG__", tag).replace("__TITLE__", TITLE)
               .replace("__SKEL_NAME__", SKEL_NAME).replace("__SKEL_KIND__", SKEL_KIND))
    with open(DST, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"生成 {DST}  ({len(out)} bytes)")
    print(f"生成 {js_path}  ({len(DATA)+25} bytes)  —— 双击打开 HTML 即可,无需起服务")
else:
    tag = DATA_TAG or ('<script id="DATA" type="application/json">' + DATA + '</script>')
    out = (HTML.replace("__DATA_TAG__", tag).replace("__TITLE__", TITLE)
               .replace("__SKEL_NAME__", SKEL_NAME).replace("__SKEL_KIND__", SKEL_KIND))
    with open(DST, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"生成 {DST}  ({len(out)} bytes)")
