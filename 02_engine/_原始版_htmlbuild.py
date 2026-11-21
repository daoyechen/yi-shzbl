#!/usr/bin/env python3
"""生成自包含的单文件 HTML 对照浏览器(数据内嵌,离线可用)。

用法:
    python3 -m shjkit.htmlbuild <viewer_data.json> [输出.html]
"""
import json

import sys

from . import skeleton as SK

_sk = SK.skel_spec()
SKEL_NAME = _sk.get('名称', '宋本《伤寒论》398 条')
SKEL_KIND = ('条级顶层 + 条内' + (_sk.get('子层') or '句') + '级下钻层') \
    if _sk.get('分层') else '条级顶层,子层为各版异文分段'

argv = sys.argv[1:]
SPLIT = "--split" in argv
argv = [a for a in argv if a != "--split"]
DATA_PATH = argv[0] if len(argv) > 0 else "/workspace/work/viewer_data.json"
DST = sys.argv[2] if len(sys.argv) > 2 else "/workspace/output/结构化对照/对照浏览器.html"
DATA = open(DATA_PATH, encoding="utf-8").read()

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>《伤寒论》多版本对照浏览器</title>
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
.bar .cb{display:flex;align-items:center;gap:4px;cursor:pointer;user-select:none}
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
.card .cb2{padding:12px 16px;font-size:15px;line-height:1.95;white-space:pre-wrap;word-break:break-word}
.base .cb2{background:#fdfaf3}
.base{border-color:#d9c9a8}
.base .ch{background:#f3e6d2}
.base .ch .vn{color:var(--zhu)}
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
.integrity{position:sticky;top:0;z-index:99;padding:8px 16px;font-size:13px;
  background:#eef7ee;color:#1f5c2a;border-bottom:1px solid #9fd0aa;font-weight:600}
.integrity.bad{background:#fdeaea;color:#8a1f1f;border-bottom-color:#e3a3a3}
#toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#2b2620;color:#f6f2ea;
  padding:9px 18px;border-radius:20px;font-family:var(--sans);font-size:12.5px;opacity:0;
  pointer-events:none;transition:opacity .22s;z-index:99}
#toast.on{opacity:1}
kbd{font-family:var(--sans);font-size:10px;background:#efe8da;border:1px solid var(--line2);
  border-radius:3px;padding:1px 4px;color:var(--ink2)}
@media(max-width:900px){aside{width:210px}}
</style>
</head>
<body>
<noscript><div style="padding:14px 20px;background:#fdeaea;color:#8c2f22;font-family:sans-serif;font-size:13px">
本页面需要启用 JavaScript 才能交互(数据已内嵌在文件内,无需联网)。若在预览窗格中打开,请先下载到本地再用浏览器打开。</div></noscript>
<header>
  <div class="hd">
    <div class="title">《伤寒论》多版本对照<small>骨架:__SKEL_NAME__</small></div>
    <div class="search">
      <span class="ic">⌕</span>
      <input id="q" placeholder="搜条号 / 关键词(如:桂枝汤、营弱卫强、阴濡弱)…" autocomplete="off">
      <button class="clr" id="qclr" title="清空">✕</button>
    </div>
    <div style="font-family:var(--sans);font-size:11px;color:var(--ink3)">
      <kbd>j</kbd><kbd>k</kbd> 上下条 · <kbd>/</kbd> 搜索
    </div>
  </div>
  <div class="tabs" id="tabs">
    <button class="tab on" data-v="cmp">条文对照</button>
    <button class="tab" data-v="fang">方剂对照<span class="cnt" id="c-fang"></span></button>
    <button class="tab" data-v="pian">篇级对照</button>
    <button class="tab" data-v="indep">独有序<span class="cnt" id="c-indep"></span></button>
    <button class="tab" data-v="review">待复核<span class="cnt" id="c-rev"></span></button>
    <button class="tab" data-v="about">体例说明</button>
  </div>
  <div class="stat" id="stat"></div>
</header>

<div class="wrap">
  <aside id="side"></aside>
  <main>
    <section class="view on" id="v-cmp">
      <div class="bar">
        <span class="cb"><input type="checkbox" id="fDiff"> 只看有异文的条</span>
        <span class="cb"><input type="checkbox" id="fSame"> 只看各版全同</span>
        <label class="cb" title="只选版本:只看该版有此条的条文">版本 <select id="fVer"></select></label>
        <label class="cb" title="需与版本筛选配合使用">状态 <select id="fSt">
          <option value="">全部</option><option value="有">有</option>
          <option value="无">无</option><option value="anch">校记锚点</option>
          <option value="hi">高置信</option><option value="low">低置信</option>
        </select></label>
        <span class="sp"></span>
        <span id="cnt"></span>
        <span class="kv" style="color:var(--ink3)">← 点左侧条目看多版对照</span>
        <button id="copy">复制本条 Markdown</button>
      </div>
      <div class="wrap2" id="detail"></div>
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
  </main>
</div>
<div id="toast"></div>

__DATA_TAG__
<script>
const D = (function(){
  let raw = '';
  // 单文件版:DATA 是内嵌 <script type="application/json">
  // 双文件版:DATA 由外部 data.js 赋值到 window.__SHJ_DATA__
  if (window.__SHJ_DATA__){ return window.__SHJ_DATA__; }
  try { raw = document.getElementById('DATA').textContent; }
  catch(e){ return {}; }
  try { return JSON.parse(raw); }
  catch(e){
    document.addEventListener('DOMContentLoaded', ()=>banner(
      '数据解析失败:' + e.message + '(内嵌 JSON 不完整或被截断)'));
    return {};
  }
})();
const VERS = D.vers;
const $ = s => document.querySelector(s);
const esc = s => (s==null?'':String(s)).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
// 【…】→ <mark>
const mk = s => esc(s).replace(/【([^】]*)】/g, '<mark>$1</mark>');
const CF = {'校记锚点':'t-anch','高置信':'t-hi','中置信':'t-mid','低置信':'t-low'};
let cur = D.items[0], curTab = 'cmp';

/* ---------- 侧栏:条目录 ---------- */
function diffVers(it){ return VERS.filter(v => it.v[v].ok && /【/.test(it.v[v].d||'')); }
function buildSide(){
  const q = $('#q').value.trim();
  const fDiff = $('#fDiff').checked, fSame = $('#fSame').checked;
  const fv = $('#fVer').value, fst = $('#fSt').value;
  const match = it => {
    if (fDiff && !diffVers(it).length) return false;
    if (fSame && diffVers(it).length) return false;
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
      const hay = it.n+' '+it.s+' '+VERS.map(v=>it.v[v].ok?it.v[v].t:'').join(' ');
      if (!hay.includes(q)) return false;
    }
    return true;
  };
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
  $('#side').innerHTML = h || '<div class="empty">无匹配条目</div>';
  markSide();
  $('#cnt').textContent = D.items.filter(match).length + ' / ' + D.items.length + ' 条';
}

/* ---------- 详情 ---------- */
function markSide(){
  document.querySelectorAll('#side .it').forEach(el =>
    el.classList.toggle('on', cur && +el.dataset.n === cur.n));
}
function select(n){
  const it = D.items.find(x => x.n === n);
  if (!it) return;
  cur = it;
  let h = `<div class="card base"><div class="ch"><span class="vn">宋本</span>
    <span class="pg">p${it.pg}</span><span class="pg">${esc(it.pian||'')}</span>
    <span style="flex:1"></span><span class="pg">骨架条 ${it.n}</span></div>
    <div class="cb2">${mk(it.s)}</div></div>`;
  for (const v of VERS){
    const c = it.v[v];
    if (c.ok){
      const tag = CF[c.cf] || 't-low';
      const seg = (c.d||c.t).split('\n');
      h += `<div class="card"><div class="ch"><span class="vn">${esc(v)}</span>
        <span class="tag ${tag}">${esc(c.cf)}</span><span class="pg">p${c.pg}</span></div>
        <div class="cb2">${seg.map(mk).join('<br>')}</div></div>`;
    }else{
      h += `<div class="card"><div class="ch"><span class="vn" style="color:var(--ink3)">${esc(v)}</span>
        <span class="tag t-none">此版无</span><span class="pg">${esc(c.rs||'')}</span></div>
        <div class="cb2" style="color:var(--ink3);font-size:14px">依据:${esc(c.ev||'')}</div></div>`;
    }
  }
  // ★ 注文(如成无己注)挂在条下 —— 2026-11-04
  const nts = (D.notes && D.notes[it.n]) || null;
  if (nts){
    for (const vn of Object.keys(nts)){
      const paras = nts[vn].split('\n').filter(x => x.trim());
      h += `<div class="card" style="border-left:3px solid var(--gold)">
        <div class="ch"><span class="vn">${esc(vn)}·注文</span>
        <span class="pg">${paras.length} 段</span></div>
        <div class="cb2" style="font-size:14px;line-height:1.85">${
          paras.map(p => esc(p).replace(/^((注\d+·[^）]*)|（[^）]*）)$/,
            '<b style="color:var(--gold)">$1</b>')).join('<br>')}</div></div>`;
    }
  }
  $('#detail').innerHTML = h;
  document.querySelector('main').scrollTop = 0;
  markSide();
  // 深链:部分浏览器对 file:// 下的 replaceState 抛安全异常,须容错
  try { history.replaceState(null, '', '#' + it.n); }
  catch (e) { try { location.hash = it.n; } catch (e2) {} }
}

/* ---------- 统计条 ---------- */
function buildStat(){
  const tot = D.items.length;
  const diff = D.items.filter(it => diffVers(it).length).length;
  let h = `<span class="u" data-a="all">骨架 <b>${tot}</b> 条(宋本)</span>
    <span class="u" data-a="diff">有异文 <b>${diff}</b> 条</span>`;
  for (const v of VERS){
    const s = D.stats[v];
    h += `<span class="u" data-v="${esc(v)}">${esc(v)}:对 <b>${s.hit}</b> · 高置信 <b>${s.hi}</b>
      ${s.anc?`· 锚点 <b>${s.anc}</b>`:''} · 独有 <b>${s.ind}</b></span>`;
  }
  $('#stat').innerHTML = h;
  $('#stat').querySelectorAll('.u[data-v]').forEach(el => el.onclick = () => {
    const v = el.dataset.v;
    $('#fVer').value = ($('#fVer').value === v) ? '' : v;
    buildSide();
  });
}

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
  // ① 宋本无编号篇 × 各版 对照矩阵 —— 这是「真正无条号篇章」的归属字段。
  //    判据:该版篇目表有同名篇(取字数),或独有文本流出现过该篇标题行。
  let h = '<div class="card"><div class="ch"><span class="vn">宋本无编号篇 × 各版</span>' +
    '<span class="pg">' + D.spian.length + ' 篇</span></div>' +
    '<div class="cb2" style="font-size:13px;color:var(--ink3);margin-bottom:8px">' +
    '骨架之外,另有下列**整篇无条号**的篇。数字为该版此篇字数,「—」为该版无此篇。' +
    '</div>';
  if (D.spian.length){
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
  } else {
    h += '<div class="kv" style="color:var(--ink3)">(未提取到无编号篇)</div>';
  }
  h += '</div>';

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
  let h = `<div class="card"><div class="ch"><span class="vn">口径</span></div><div class="cb2" style="font-size:14px">
· <b>骨架</b>:__SKEL_NAME__(骨架性质:__SKEL_KIND__)
  依「每条只认期望的下一个编号」逐位校验切出,零缺号;仅条 154 的编号被 OCR 残损(--五四),已按位修复。<br>
· <b>对齐</b>:以内容比对为主(字符 n-gram 召回 + 短文本覆盖率排序),辅以位置单调性约束;
  编者校记所注「同《宋本伤寒论》第X条」优先采用(硬锚点)。<br>
· <b>此版无</b>:一律注明原因与原文依据,不以推测填补;理由分「选集未收 / 本版仅残卷 / 原书残损 / 体例不同 / 暂未匹配」。<br>
· <b>不臆造</b>:某版没有的条文只标「此版无」并给出依据;各版多出的内容给独立章节 ID,单列《版本独有内容》。<br>
· <b>转录</b>:本对照基于影印扫描件的逐页转录,反映影印本字面,未作校订;异体字、通假字一仍其旧,正式引用请核对原页。</div></div>`;
  h += '<div class="card"><div class="ch"><span class="vn">各版「此版无」主因与原文依据</span></div><div class="cb2" style="font-size:14px">';
  for (const v of VERS){
    const c = D.cover[v];
    if (!c) continue;
    h += `<div style="margin-bottom:9px"><b>${esc(v)}</b> —— ${esc(c.kind)}<br>
      <span class="kv">${esc(c.evid)}</span></div>`;
  }
  h += '</div></div>';
  h += `<div class="card"><div class="ch"><span class="vn">统计</span></div><div class="cb2" style="font-size:14px"><table>
    <thead><tr><th>版本</th><th>对上宋本条数</th><th>高置信</th><th>校记锚点</th><th>独立内容</th></tr></thead><tbody>`;
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
function banner(msg, bad){
  const d = document.createElement('div');
  d.className = 'integrity' + (bad ? ' bad' : '');
  d.textContent = msg;
  document.body.insertBefore(d, document.body.firstChild);
}
function checkIntegrity(){
  const errs = [];
  if (!D || !D.items) { errs.push('viewer_data 未载入'); }
  else {
    if (D.items.length !== D.expect) errs.push('条目数 ' + D.items.length + ' ≠ ' + D.expect);
    const nv = (D.vers || []).length;
    if (nv !== 9) errs.push('对照版本数 ' + nv + ' ≠ 9');
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
    // 宋本无编号篇:非空 + 不混有编号篇 + 矩阵齐全
    const spian = D.spian || [];
    if (!spian.length) errs.push('宋本无编号篇为空(篇级对照将失真)');
    else {
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
         ' 版,无编号篇 ' + D.spian.length + ' 个,注文 ' + Object.keys(D.notes||{}).length + ' 条', false);
  return true;
}

function toast(t){ const e = $('#toast'); e.textContent = t; e.classList.add('on');
  setTimeout(()=>e.classList.remove('on'), 1600); }

function buildAll(){
  buildStat(); buildSide(); select(cur ? cur.n : D.items[0].n);
  buildFang(); buildPian(); buildIndep(); buildReview(); buildAbout();
}
function fillSel(){
  const o1 = VERS.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
  $('#fVer').innerHTML = '<option value="">全部</option>' + o1;
  $('#fVer2').innerHTML = '<option value="">全部</option>' + o1;
}
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
  document.querySelectorAll('.view').forEach(x => x.classList.remove('on'));
  t.classList.add('on'); curTab = t.dataset.v;
  $('#v-' + curTab).classList.add('on');
  if (curTab === 'cmp') buildSide();
});
// 事件委托:绑定在容器上,侧栏重建后依然有效
$('#side').addEventListener('click', e => {
  const el = e.target.closest('.it');
  if (el) { select(+el.dataset.n); return; }
  const gh = e.target.closest('.gh');
  if (gh) { const b = gh.nextElementSibling;
    b.style.display = (b.style.display === 'none') ? 'block' : 'none'; }
});
window.addEventListener('error', e => toast('出错了:' + e.message));
$('#q').oninput = () => { $('#qclr').style.display = $('#q').value ? 'block' : 'none'; buildSide(); buildIndep(); };
$('#qclr').onclick = () => { $('#q').value = ''; $('#qclr').style.display = 'none'; buildSide(); $('#q').focus(); };
$('#fDiff').onchange = buildSide; $('#fSame').onchange = buildSide;
$('#fVer').onchange = buildSide; $('#fSt').onchange = buildSide;
$('#fOnly').onchange = buildFang; $('#fVer2').onchange = buildFang;
$('#copy').onclick = () => {
  let md = `### 条 ${cur.n} 〔${cur.pian}〕\n\n**宋本**(p${cur.pg}):${cur.s}\n`;
  for (const v of VERS){
    const c = cur.v[v];
    md += c.ok ? `- **${v}**(${c.cf},p${c.pg}):${c.d || c.t}\n`
               : `- **${v}**:此版无 —— **${c.rs}**。依据:${c.ev}\n`;
  }
  navigator.clipboard.writeText(md).then(()=>toast('已复制本条 Markdown'),
    ()=>toast('复制失败,请手动选取'));
};
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT'){
    if (e.key === 'Escape') e.target.blur();
    return;
  }
  if (e.key === '/'){ e.preventDefault(); $('#q').focus(); return; }
  if (curTab !== 'cmp') return;
  if (e.key === 'j' || e.key === 'k'){
    const vis = [...document.querySelectorAll('#side .it')].map(x => +x.dataset.n);
    if (!vis.length) return;
    let i = vis.indexOf(cur.n);
    i = e.key === 'j' ? Math.min(vis.length-1, i+1) : Math.max(0, i-1);
    select(vis[i]);
    const el = document.querySelector(`#side .it[data-n="${vis[i]}"]`);
    if (el) el.scrollIntoView({block:'nearest'});
  }
});
$('#c-fang').textContent = Object.values(D.fang).reduce((a,v)=>a+Object.keys(v).length,0);
$('#c-indep').textContent = VERS.reduce((a,v)=>a+D.indep[v].length,0);
$('#c-rev').textContent = D.review.length;
fillSel();
// 深链要在 buildAll 之前读取:buildAll 内的 select 会改写 hash
(function(){
  const t = new URLSearchParams(location.search).get('tab');
  const h = location.hash.replace('#','');
  const want = /^\d+$/.test(h) ? +h : null;
  checkIntegrity();
  buildAll();
  if (t){ const b = document.querySelector(`.tab[data-v="${t}"]`); if (b) b.click(); }
  if (want) select(want);
})();
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
    out = HTML.replace("__DATA_TAG__", tag).replace("__SKEL_NAME__", SKEL_NAME).replace("__SKEL_KIND__", SKEL_KIND)
    with open(DST, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"生成 {DST}  ({len(out)} bytes)")
    print(f"生成 {js_path}  ({len(DATA)+25} bytes)  —— 双击打开 HTML 即可,无需起服务")
else:
    tag = '<script id="DATA" type="application/json">' + DATA + '</script>'
    out = HTML.replace("__DATA_TAG__", tag).replace("__SKEL_NAME__", SKEL_NAME).replace("__SKEL_KIND__", SKEL_KIND)
    with open(DST, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"生成 {DST}  ({len(out)} bytes)")
