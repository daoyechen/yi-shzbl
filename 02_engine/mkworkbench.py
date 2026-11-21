#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一份「待裁定清单」生成成单文件 HTML 核定台（双击即用，离线，自动存本地）。

为什么要有这个
--------------
派出去的活里，有一类是**必须人看**的：某条到底是「本版无」还是「并进前条」、
这个私用区方框本来是哪个字。这类活给 CSV 让人填，人要在两个窗口间来回对；
给 PDF 让人批注，回来还得再誊一遍。

这里生成一个「左边清单、右边题面、点一下定性、自动存、一键导出」的页面：
接包人不需要装任何东西，浏览器打开就能干，干完导出一个 JSON 交回来。

配置结构（--json 指向的文件）
----------------------------
{
  "title": "页面标题",
  "subtitle": "副标题（写清这批是什么、共几条）",
  "intro": "开头说明（可含 HTML）",
  "export_name": "交付文件名.json",
  "items": [
    {
      "id": "T-001",                  # 唯一键（导出用它对齐）
      "tag": "条 13 · 邓珍本",         # 列表里显示的短标签
      "stem": "骨架原文（必填）",       # 题面主区
      "body": "本版原文 / 待判文字",    # 题面次区（可空）
      "ref": "证据、上下文、出处",      # 小字（可空）
      "hint": "这一条要判什么",         # 提示条（可空）
      "options": [{"v": "有", "label": "确认有此条"}, ...],  # 选项；缺省用顶层 options
      "text": false                   # true = 还要填一个文本框（如「本字」）
    }
  ],
  "options": [{"v": "...", "label": "..."}],   # 顶层默认选项
  "text_label": "本字"                          # 文本框标题
}

用法
----
    python3 mkworkbench.py 配置.json 输出.html
"""
import json
import sys

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --paper:#f6f2ea; --panel:#fffdf8; --ink:#262219; --ink2:#5d564a; --ink3:#8d8577;
  --line:#ddd5c6; --line2:#c9bfa9; --zhu:#9c3524; --qing:#2c5a5f; --ok:#3f6b3f;
  --warn:#a2621b; --gold:#b07d1f;
  --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
  --serif:"Songti SC","STSong","Source Han Serif SC","Noto Serif CJK SC",serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:var(--serif);font-size:15px;line-height:1.8;
  -webkit-font-smoothing:antialiased}
header{position:sticky;top:0;z-index:20;background:linear-gradient(180deg,#fffdf8,#f9f5ec);
  border-bottom:1.5px solid var(--line2);box-shadow:0 1px 5px rgba(0,0,0,.05)}
.hd{display:flex;align-items:center;gap:14px;padding:10px 18px;flex-wrap:wrap}
.title{font-size:18px;font-weight:700;letter-spacing:.5px}
.sub{font-family:var(--sans);font-size:11.5px;color:var(--ink3)}
.sp{flex:1}
button{font-family:var(--sans);font-size:12.5px;border:1px solid var(--line2);background:#fff;
  padding:5px 11px;border-radius:6px;cursor:pointer;color:var(--ink)}
button:hover{border-color:var(--gold)}
button.primary{background:var(--zhu);border-color:var(--zhu);color:#fff}
button.primary:hover{background:#8a2d1e}
.bar{display:flex;align-items:center;gap:10px;padding:7px 18px;border-top:1px solid var(--line);
  font-family:var(--sans);font-size:11.5px;color:var(--ink2);flex-wrap:wrap}
.prog{flex:1;height:6px;background:#e7dfd0;border-radius:3px;overflow:hidden;min-width:120px}
.prog i{display:block;height:100%;background:var(--ok);width:0;transition:width .2s}
.wrap{display:flex;align-items:flex-start;gap:0}
aside{width:266px;flex:none;height:calc(100vh - 92px);overflow-y:auto;border-right:1px solid var(--line);
  background:#fbf8f1;padding:8px 0}
.it{display:flex;gap:7px;align-items:baseline;padding:6px 14px;cursor:pointer;font-size:13.5px;
  border-left:3px solid transparent}
.it:hover{background:#f3ecdd}
.it.on{background:#fff;border-left-color:var(--zhu)}
.it .dot{width:7px;height:7px;border-radius:50%;background:#cfc6b4;flex:none;margin-top:7px}
.it .dot.done{background:var(--ok)}
.it .dot.flag{background:var(--warn)}
.it .tx{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.it .id{font-family:var(--sans);font-size:10.5px;color:var(--ink3)}
main{flex:1;min-width:0;padding:18px 22px 80px;height:calc(100vh - 92px);overflow-y:auto}
.card{background:var(--panel);border:1px solid var(--line);border-radius:9px;margin-bottom:14px;overflow:hidden}
.card .ch{padding:7px 14px;background:#f1ead9;border-bottom:1px solid var(--line);
  font-family:var(--sans);font-size:11.5px;color:var(--ink2);display:flex;gap:10px;align-items:center}
.card .cb{padding:12px 16px;font-size:15.5px;line-height:2;white-space:pre-wrap;word-break:break-word}
.card.s .cb{background:#fdfaf3}
.hint{background:#fbf3e0;border:1px solid #e6d4a8;color:#7a5a16;padding:8px 12px;border-radius:7px;
  font-family:var(--sans);font-size:12.5px;margin-bottom:14px}
.opts{display:flex;gap:9px;flex-wrap:wrap;margin:4px 0 12px}
.opts button{padding:8px 15px;font-size:13.5px}
.opts button.on{background:var(--qing);border-color:var(--qing);color:#fff;font-weight:600}
.opts button.on.warnv{background:var(--warn);border-color:var(--warn)}
.opts button.on.flagv{background:#8d8577;border-color:#8d8577}
textarea{width:100%;min-height:78px;border:1px solid var(--line2);border-radius:7px;padding:9px 11px;
  font-family:var(--serif);font-size:15px;line-height:1.9;background:#fff;resize:vertical;outline:none}
textarea:focus{border-color:var(--gold);box-shadow:0 0 0 3px rgba(176,125,31,.1)}
label.fld{display:block;font-family:var(--sans);font-size:11.5px;color:var(--ink3);margin:10px 0 4px}
.pua{font-size:22px;color:var(--zhu);border:1px dashed var(--zhu);padding:0 6px;border-radius:4px}
.ctxs{font-family:var(--sans);font-size:13px;line-height:2.1}
.ctxs b{color:var(--zhu);background:#fbeeeb;padding:0 3px;border-radius:3px}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#33302a;color:#fff;
  padding:9px 18px;border-radius:20px;font-family:var(--sans);font-size:12.5px;opacity:0;pointer-events:none;
  transition:opacity .2s;z-index:99}
.toast.on{opacity:1}
.intro{background:#fffdf8;border:1px solid var(--line);border-radius:9px;padding:14px 16px;
  font-size:14px;line-height:1.95;margin-bottom:14px}
.intro code{background:#f2ebdc;padding:1px 5px;border-radius:3px;font-size:13px}
.intro a,.loc a{color:var(--qing);text-decoration:underline;text-underline-offset:2px}
.intro a:hover,.loc a:hover{color:var(--zhu)}
.books{margin-top:10px;padding:9px 11px;background:#f2f5f1;border:1px solid #d5dfd0;border-radius:7px;
  font-family:var(--sans);font-size:12px;line-height:2}
/* 书证核对台：大字本字 + 五版并排 */
.glyphbox{display:flex;align-items:center;gap:18px;padding:4px 0 16px;border-bottom:1px dashed var(--line2);margin-bottom:14px}
.glyphwrap{flex:none;text-align:center}
.glyphbig{font-size:64px;line-height:1.1;color:var(--zhu);border-radius:10px;
  min-width:96px;text-align:center;padding:9px 8px;background:#fdf1ec;flex:none;font-family:var(--serif)}
.glyphcap{font-family:var(--sans);font-size:10.5px;color:var(--ink3);margin-top:5px;letter-spacing:1px}
.evi{font-family:var(--sans);font-size:13px;line-height:1.95;color:var(--ink2)}
.evi b{color:var(--ink)}
.weak{color:var(--ink3);font-size:12px}
.pftitle{font-family:var(--sans);font-size:12px;color:var(--ink2);font-weight:600;margin-bottom:8px}
.proofs{font-family:var(--serif)}
.pf{border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:11px}
.pmeta{background:#f1ead9;padding:5px 11px;font-family:var(--sans);font-size:11.5px;color:var(--ink2);
  border-bottom:1px solid var(--line)}
.prow{display:grid;grid-template-columns:172px 1fr;gap:10px;padding:6px 11px;border-top:1px solid #efe8da;
  font-size:14.5px;line-height:1.9;align-items:baseline}
.prow:first-of-type{border-top:none}
.prow.main{background:#fdf6f3}
.pv{font-family:var(--sans);font-size:11.5px;color:var(--ink3);white-space:nowrap}
.pt{word-break:break-all}
.pt b.hit,.pt b.qmark{color:#fff;background:var(--zhu);padding:1px 4px;border-radius:3px;font-weight:600;font-size:16px}
.pt b.qmark{font-family:var(--sans);font-size:14px;letter-spacing:1px}
.pt .miss{color:var(--ink3);font-family:var(--sans);font-size:12px}
.pt i.weak{font-size:11px;margin-left:6px;font-style:normal}
.loc{font-family:var(--sans);font-size:12.5px;line-height:2;color:var(--ink2)}
.loc b{color:var(--ink)}
.loc code{background:#f2ebdc;padding:1px 5px;border-radius:3px;font-size:12.5px}
.scanbox{margin-top:10px;border:1px solid var(--line);border-radius:7px;padding:7px 10px;background:#fff}
.scanbox summary{cursor:pointer;font-family:var(--sans);font-size:12px;color:var(--qing)}
.scanbox img.scan{display:block;max-width:100%;max-height:460px;margin:9px auto 4px;border:1px solid var(--line2)}
@media(max-width:820px){
  .wrap{display:block}
  aside{width:100%;height:auto;max-height:168px;overflow-y:auto;border-right:none;
    border-bottom:1px solid var(--line2);padding:5px 0}
  .it{padding:6px 12px;font-size:12.5px}
  main{height:auto;max-height:none;overflow:visible;padding:14px 12px 70px}
  body{font-size:16px}
  .title{font-size:16px}
  .hd{padding:8px 12px;gap:8px}
  .bar{padding:6px 12px}
  .prow{grid-template-columns:1fr;gap:2px;padding:7px 10px}
  .pv{white-space:normal}
  .glyphbox{gap:12px;flex-wrap:wrap}
  .glyphbig{font-size:48px;min-width:66px}
  .cb{font-size:15.5px;line-height:1.95}
  .opts button{padding:9px 12px;font-size:13.5px}
}
</style>
</head>
<body>
<header>
  <div class="hd">
    <div>
      <div class="title">__TITLE__</div>
      <div class="sub">__SUBTITLE__</div>
    </div>
    <div class="sp"></div>
    <button id="imp">导入已有结果</button>
    <button id="exp" class="primary">导出交付 JSON</button>
    <input type="file" id="file" accept=".json" style="display:none">
  </div>
  <div class="bar">
    <span id="cnt"></span>
    <div class="prog"><i id="pi"></i></div>
    <span id="pct"></span>
    <span style="color:var(--ink3)">结果自动存在本机浏览器；换电脑请先「导出」</span>
  </div>
</header>
<div class="wrap">
  <aside id="side"></aside>
  <main id="main"></main>
</div>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const KEY = 'wb:' + DATA.key;
const ITEMS = DATA.items;
let S = {};
try { S = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e){ S = {}; }
let cur = 0;

const $ = s => document.querySelector(s);
const esc = s => (s==null?'':String(s)).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function optOf(it){ return it.options || DATA.options || []; }
function st(it){ const s = S[it.id]; if (!s || (!s.choice && !(s.text||'').trim())) return 0;
  return (s.choice === '?' || s.flag) ? 2 : 1; }

function toast(t){ const e=$('#toast'); e.textContent=t; e.classList.add('on');
  setTimeout(()=>e.classList.remove('on'), 1500); }

function save(){ localStorage.setItem(KEY, JSON.stringify(S)); }

function buildSide(){
  $('#side').innerHTML = ITEMS.map((it,i)=>{
    const s = st(it);
    const cls = s===1?'done':(s===2?'flag':'');
    return `<div class="it ${i===cur?'on':''}" data-i="${i}">
      <span class="dot ${cls}"></span>
      <span class="tx"><span class="id">${esc(it.listLabel ?? it.id)}</span> ${esc(it.tag||'')}</span></div>`;
  }).join('');
  const done = ITEMS.filter(x=>st(x)===1).length, flag = ITEMS.filter(x=>st(x)===2).length;
  $('#cnt').textContent = `已定 ${done} / 存疑 ${flag} / 共 ${ITEMS.length}`;
  const p = Math.round((done+flag)/ITEMS.length*100);
  $('#pi').style.width = p+'%'; $('#pct').textContent = p+'%';
}

function render(){
  const it = ITEMS[cur], s = S[it.id] || {};
  const opts = optOf(it);
  let h = '';
  if (DATA.intro) h += `<div class="intro">${DATA.intro}</div>`;
  // hint 由出题方撰写，允许少量标签（<b> 强调）；正文一律转义
  if (it.hint) h += `<div class="hint">${it.hint}</div>`;
  if (it.stem) h += `<div class="card s"><div class="ch"><span>骨架原文</span>
      <span style="margin-left:auto">条 ${esc(it.id)}</span></div>
      <div class="cb">${esc(it.stem)}</div></div>`;
  if (it.body) h += `<div class="card"><div class="ch"><span>${esc(it.bodyLabel||'本版原文')}</span></div>
      <div class="cb">${it.bodyHtml ? it.body : esc(it.body)}</div></div>`;
  if (it.ref) h += `<div class="card"><div class="ch"><span>依据 / 上下文</span></div>
      <div class="cb" style="font-size:13px;color:var(--ink2)">${it.refHtml ? it.ref : esc(it.ref)}</div></div>`;
  h += `<div class="opts">` + opts.map(o=>{
      const on = s.choice === o.v;
      const cls = o.v === '?' ? 'flagv' : (o.warn ? 'warnv' : '');
      return `<button data-v="${esc(o.v)}" class="${on?'on '+cls:''}">${esc(o.label)}</button>`;
    }).join('') + `</div>`;
  if (it.text){
    // 出题方可给 defaultText（机器已推出的候选答案）；用户未输入时用它预填，
    // 但只有点过选项才算「已定」，进度条不把预填当作完成。
    const t0 = (s.text != null) ? s.text : (it.defaultText || '');
    h += `<label class="fld">${esc(DATA.text_label||'填写')}</label>
      <textarea id="tx" placeholder="${esc(it.placeholder||'')}">${esc(t0)}</textarea>`;
  }
  h += `<label class="fld">备注（可不填）</label>
      <textarea id="note" style="min-height:56px" placeholder="判断依据一句话，方便复核">${esc(s.note||'')}</textarea>`;
  h += `<div style="margin-top:14px;display:flex;gap:9px">
      <button id="prev">← 上一条</button>
      <button id="next" class="primary">下一条 →</button>
      <span style="flex:1"></span>
      <span style="font-family:var(--sans);font-size:11.5px;color:var(--ink3)">
        第 ${cur+1} / ${ITEMS.length} 条 · 键盘 1-9 选项，J/K 翻条</span></div>`;
  $('#main').innerHTML = h;
  $('#main').scrollTop = 0;

  document.querySelectorAll('.opts button').forEach(b=> b.onclick = ()=>{
    const st0 = S[it.id] || {};
    // 需要填「一个字」的题：没填字就不许点「能定」，防止空结论交回来充数。
    if (it.oneChar && b.dataset.v !== '?' && st0.choice !== b.dataset.v){
      const t0 = ((st0.text != null) ? st0.text : (it.defaultText || '')).trim();
      if (t0.length !== 1){ toast('请先在上方输入框填一个本字，再点这个选项'); return; }
    }
    // 兼容带预填答案的老配置：选「改」却没真改字，也不许点。
    if (b.dataset.v === '改' && it.requireTextChange && st0.choice !== '改'){
      const t0 = (st0.text != null) ? st0.text : (it.defaultText || '');
      if (!t0.trim() || t0.trim() === (it.defaultText||'').trim()){
        toast('要改本字，请先在上方输入框里改成新字'); return;
      }
    }
    if (st0.choice === b.dataset.v) delete st0.choice; else st0.choice = b.dataset.v;
    S[it.id] = st0; save(); render(); buildSide();
  });
  const tx = $('#tx'); if (tx) tx.oninput = ()=>{ S[it.id] = Object.assign(S[it.id]||{}, {text:tx.value}); save(); buildSide(); };
  const nt = $('#note'); if (nt) nt.oninput = ()=>{ S[it.id] = Object.assign(S[it.id]||{}, {note:nt.value}); save(); };
  $('#prev').onclick = ()=> go(-1);
  $('#next').onclick = ()=> go(1);
}

function go(d){
  const n = Math.min(ITEMS.length-1, Math.max(0, cur+d));
  if (n === cur){ toast(d>0?'已是最后一条':'已是第一条'); return; }
  cur = n; render(); buildSide();
}

$('#side').addEventListener('click', e=>{
  const el = e.target.closest('.it'); if (!el) return;
  cur = +el.dataset.i; render(); buildSide();
});
$('#exp').onclick = ()=>{
  const out = {
    key: DATA.key, title: DATA.title, exported: new Date().toISOString(),
    total: ITEMS.length,
    done: ITEMS.filter(x=>st(x)===1).length,
    flagged: ITEMS.filter(x=>st(x)===2).length,
    rows: ITEMS.map(it=>{
      const s = S[it.id] || {};
      const t0 = (s.text != null) ? s.text : (it.defaultText || '');
      return {id: it.id, tag: it.tag||'', choice: s.choice||'', text: t0,
              note: s.note||'', defaultText: it.defaultText||''};
    })
  };
  const b = new Blob([JSON.stringify(out, null, 1)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b); a.download = DATA.export_name || '交付.json'; a.click();
  toast('已导出 ' + (DATA.export_name||'交付.json'));
};
$('#imp').onclick = ()=> $('#file').click();
$('#file').onchange = e=>{
  const f = e.target.files[0]; if (!f) return;
  const r = new FileReader();
  r.onload = ()=>{
    try{
      const d = JSON.parse(r.result);
      let n = 0;
      (d.rows||[]).forEach(row=>{ if(row.id){ S[row.id] = {choice:row.choice, text:row.text, note:row.note}; n++; } });
      save(); render(); buildSide(); toast('已导入 '+n+' 条');
    }catch(err){ toast('导入失败：'+err.message); }
  };
  r.readAsText(f);
};
document.addEventListener('keydown', e=>{
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if (e.key === 'j' || e.key === 'J'){ go(1); return; }
  if (e.key === 'k' || e.key === 'K'){ go(-1); return; }
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= 9){
    const btns = document.querySelectorAll('.opts button');
    if (btns[n-1]) btns[n-1].click();
  }
});

buildSide(); render();
</script>
</body>
</html>
"""


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    cfg.setdefault("options", [])
    cfg.setdefault("export_name", "交付.json")
    cfg.setdefault("key", cfg.get("title", "wb"))
    data = json.dumps(cfg, ensure_ascii=False, separators=(",", ":"))
    out = (HTML.replace("__TITLE__", cfg.get("title", "核定台"))
               .replace("__SUBTITLE__", cfg.get("subtitle", ""))
               .replace("__DATA__", data))
    open(sys.argv[2], "w", encoding="utf-8").write(out)
    print(f"生成 {sys.argv[2]}  ({len(out)} 字符, {len(cfg['items'])} 条)")


if __name__ == "__main__":
    main()
