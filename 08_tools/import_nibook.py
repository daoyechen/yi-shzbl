#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把倪海厦图书版《伤寒论》经文并入 L1（SH）作为「倪本」列。

数据来源：10_material/11_inbox/1126_1215/人纪-4-伤寒论/ 14 个 md
产出：50_data/52_l1_assembly/shanghan/11_倪本映射.json + viewer_data.json 增列

用法：
  python3 08_tools/import_nibook.py            # 写盘
  python3 08_tools/import_nibook.py --dry-run  # 只报数
"""
import json, os, re, sys, collections

B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(B, "10_material", "11_inbox", "1126_1215", "人纪-4-伤寒论")
VDATA = os.path.join(B, "50_data", "52_l1_assembly", "shanghan", "viewer_data.json")
OUTMAP = os.path.join(B, "50_data", "52_l1_assembly", "shanghan", "11_倪本映射.json")

FILES = [
    ("3.辨太阳病脉证并治法上篇.md", "辨太阳病脉证并治上第五  合一十六法  方一十四首"),
    ("4.辨太阳病脉证并治法中篇.md", "辨太阳病脉证并治中第六  合六十六法  方三十九首"),
    ("5.辨太阳病脉证并治法下篇.md", "辨太阳病脉证并治下第七  合三十九法  方三十首"),
    ("6.辨阳明病脉证并治法.md",   "辨阳明病脉证并治第八  合四十四法  方一十首"),
    ("7.辨少阳病脉证并治法.md",   "辨少阳病脉证并治第九  方一首"),
    ("8.辨太阴病脉证并治法.md",   "辨太阴病脉证并治第十  方三首"),
    ("9.辨少阴病脉证并治法.md",   "辨少阴病脉证并治第十一  方二十三首"),
    ("10.辨厥阴病脉证并治法.md",  "辨厥阴病脉证并治第十二  方一十九首"),
]
DIG = {'零':0,'〇':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
UNIT = {'十':10,'百':100,'千':1000}
NUM = r'[一二三四五六七八九十百千零〇两]+'
VER = "倪本"

def cn2int(s):
    s = s.strip()
    if not s: return None
    if s.isdigit(): return int(s)
    if any(c in s for c in UNIT):
        total = num = 0
        for ch in s:
            if ch in DIG: num = DIG[ch]
            elif ch in UNIT: total += (num if num else 1) * UNIT[ch]; num = 0
            else: return None
        return total + num
    try: return int(''.join(str(DIG[c]) for c in s))
    except KeyError: return None

def parse():
    arts = []
    for fn, pian in FILES:
        for line_no, line in enumerate(open(os.path.join(SRC, fn), encoding='utf-8')):
            m = re.match(r'^####\s*(.+?)\s*$', line)
            if not m: continue
            t = m.group(1)
            mh = re.match(r'^(%s)\s*([、：:;,，.．]?)\s*(.*)$' % NUM, t)
            is_head = False
            if mh:
                n1 = cn2int(mh.group(1)); rest = mh.group(3)
                if n1 is not None and n1 <= 400:
                    if mh.group(2): is_head = True
                    elif rest.startswith('「') or (len(rest) >= 10 and re.search(r'[，。；：]', rest)): is_head = True
            if is_head:
                n2 = None; jing = mh.group(3)
                mm = re.match(r'^(%s)\s*([、：:;,，.．])\s*(.*)$' % NUM, mh.group(3))
                if mm:
                    c = cn2int(mm.group(1))
                    if c is not None and len(mm.group(1)) <= 2 and (c == n1+1 or c == (n1+1) % 10):
                        n2 = n1 + 1; jing = mm.group(3)
                arts.append(dict(no=n1, no2=n2, jing=jing.strip().strip('“”"'), pian=pian, file=fn))
                continue
            # 无编号但像经文的标题 → 并入上一条经文
            if arts and ('「' in t or '，' in t or ',' in t) and len(t) > 8 \
               and not t.rstrip().endswith('方') and not t.rstrip().endswith(('：', ':')):
                arts[-1]['jing'] = arts[-1]['jing'].rstrip() + '\n' + t.strip()
    return arts

# —— 对齐修正表（人工核过，理由见注释）——
FIX = {
    191: 176,   # 「脉浮滑…白虎汤」夹在 175/177 之间；宋350 另有倪366 对应
    222: 206,   # 「面含赤色」= 宋206「面合色赤」；宋200 是「被火…」
    275: 261,   # 方名与宋261/262 对调（倪本有误，照录），按顺位挂 261
}
MERGE = {25: (21, 2), 142: (128, 2), 240: (221, 3), 242: (225, 2),
         247: (231, 2), 272: (257, 2), 367: (351, 2)}
HINT = {25: ['若微恶寒者']}

def hanzi_only(s):
    return re.sub(r'[^\u4e00-\u9fff]', '', s)

def grams(t, k=4):
    return {t[i:i+k] for i in range(len(t)-k+1)} if len(t) >= k else {t}

def norm_map(s):
    out, idx = [], []
    for i, ch in enumerate(s):
        if '\u4e00' <= ch <= '\u9fff': out.append(ch); idx.append(i)
    return ''.join(out), idx

def split_by(no, n0, span, txt):
    if span == 1: return [txt]
    nm, idx = norm_map(txt)
    hints = HINT.get(no, [])
    cuts = [0]
    for k in range(1, span):
        target = hanzi_only(hints[k-1]) if k-1 < len(hints) else None
        if not target:
            # 用宋本第 n+k 条前 8 字；找不到降级 6/5/4 字
            song = SONG[n0 + k]
            for L in (8, 6, 5, 4):
                target = hanzi_only(song)[:L]
                pos = nm.find(target)
                if pos > cuts[-1]: break
        else:
            pos = nm.find(target)
        if pos <= cuts[-1]: return None
        cuts.append(pos)
    cuts.append(len(nm))
    parts = []
    for i in range(span):
        s = 0 if i == 0 else idx[cuts[i]]
        e = idx[cuts[i+1]] if cuts[i+1] < len(idx) else len(txt)
        parts.append(txt[s:e].strip().strip('。;；,，'))
    return parts

def main():
    dry = '--dry-run' in sys.argv
    arts = parse()
    vd = json.load(open(VDATA, encoding='utf-8'))
    SONG = {}
    for it in vd['items']:
        SONG[it['n']] = it['s']
    globals()['SONG'] = SONG
    NMAX = max(SONG)

    # 初对齐：top1
    G = {n: grams(hanzi_only(t)) for n, t in SONG.items()}
    rows = []
    for a in arts:
        g = grams(hanzi_only(a['jing']))
        top = max(((len(g & G[n]) / max(1, len(g)), n) for n in G))[1]
        n, span = MERGE.get(a['no'], (FIX.get(a['no'], top), 1))
        rows.append(dict(no=a['no'], no2=a['no2'], n=n, span=span, jing=a['jing']))

    # 切分 + 反查
    by_n = collections.defaultdict(list)
    bad = []
    for r in rows:
        parts = split_by(r['no'], r['n'], r['span'], r['jing'])
        if parts is None:
            bad.append(r['no']); parts = [r['jing']] + [''] * (r['span'] - 1)
        r['parts'] = parts
        for i, p in enumerate(parts):
            if p: by_n[r['n'] + i].append(dict(no=r['no'], seg=i + 1, kind=('合' if r['span'] > 1 else '单'), text=p))
    if bad: print("!! 切分失败:", bad)

    # 校验
    miss = [n for n in range(1, 382) if n not in by_n]
    extra = [n for n in by_n if n > 381]
    order = [(rows[i-1]['no'], rows[i-1]['n'], rows[i]['no'], rows[i]['n'])
             for i in range(1, len(rows)) if rows[i]['n'] < rows[i-1]['n']]
    print(f"倪本 {len(rows)} 标题 / {sum(1 + (1 if r['no2'] else 0) for r in rows)} 号")
    print(f"覆盖宋本 {len(by_n)} 条；1-381 缺 {miss}；超界 {extra}；非单调 {order or '无'}")

    # —— 写 viewer_data ——
    if VER not in vd['vers']:
        vd['vers'].append(VER)
    hit = hi = 0
    for it in vd['items']:
        n = it['n']
        lst = by_n.get(n)
        if lst:
            t = '\n'.join(x['text'] for x in lst)
            conf = '高置信' if (len(lst) == 1 and lst[0]['kind'] == '单') else '中置信'
            it['v'][VER] = dict(ok=1, cf=conf, pg=None, t=t, d='')
            hit += 1
            if conf == '高置信': hi += 1
        else:
            it['v'][VER] = dict(ok=0, rs='倪本不收此条',
                                ev='倪本自编号一至三九七（缺七七），霍乱、阴阳易、差后劳复三篇未收；不含此条')
    vd.setdefault('stats', {})[VER] = dict(hit=hit, hi=hi, anc=0, ind=0)
    vd.setdefault('indep', {})[VER] = []
    print(f"入列：hit={hit} 高置信={hi} 中置信={hit-hi} 无={NMAX-hit}")

    # —— 映射表 ——
    no2song = {}
    for r in rows:
        no2song[str(r['no'])] = r['n']
        if r['no2']: no2song[str(r['no2'])] = r['n']
    out = dict(
        说明="倪海厦图书版《伤寒论》自编号 → 宋本骨架条号。拆条=一号对一条；合并条=一号跨多条，parts 已按宋本切分",
        来源="10_material/11_inbox/1126_1215/人纪-4-伤寒论/（14 md）",
        条数=len(rows), 号数=len(no2song), 覆盖宋本=len(by_n),
        标题=[dict(no=r['no'], no2=r['no2'], n=r['n'], span=r['span'],
                  parts=[dict(n=r['n']+i, text=p) for i, p in enumerate(r['parts'])]) for r in rows],
        号到条=no2song,
        条到号={str(n): [x['no'] for x in lst] for n, lst in sorted(by_n.items())},
    )
    if dry:
        print("dry-run，不写盘"); return
    json.dump(vd, open(VDATA, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    json.dump(out, open(OUTMAP, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print("已写", VDATA)
    print("已写", OUTMAP)

if __name__ == '__main__':
    main()
