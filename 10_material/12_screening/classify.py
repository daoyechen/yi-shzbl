#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
待验区筛选器 v2 —— 判定 _待验/ 每件是「相关且尚未收录的版本（留）」还是「已收录/不相关/重复（删）」。

v2 相对 v1 的四处关键修正
  ① 探针路径前缀归一（hashes.tsv 带 "./"、probe.json 不带）→ 页数/文本层/PDF元数据首次真正生效
  ② 缺书命中（WANTED）改为「文件名 + PDF元数据 + 文本首行」三源匹配，且优先于「已收录」判定
     → 救回 01.《伤寒论》乾.pdf / 02.《伤寒论》坤.pdf（metadata: 和气氏伤寒论.2卷 = 缺书 D1）
  ③ 取消「伤寒论/伤寒金鉴」整目录粗判；改用「谱系核心词(CORE)」逐件判定
     → 救回 伤寒论集注——张志聪 / 医宗金鉴-02-金匮要略注 / 兰台轨范 等相关件
  ④ 同名择优改为「同书多载体」口径：带「部分N/卷N」的同书不同部分全部保留

判据优先级（逐件只命中一条，先命中先生效）：
  R0 字节级重复  —— sha256 与另一件完全相同，保留 1 件
  R1 非文献载体  —— 音频 wma / 课件 ppt / 散图 jpg
  R2 缺书命中    —— 命中《缺书清单》D1/D2/A5-A9/C1/C2，保留（价值最高）
  R3 主题错配    —— 金匮县志、银楼、儿妇针外科等同名歧义/异科别
  R4 谱系外      —— 文件名与元数据均无伤寒/金匮谱系核心词
  R5 已收录同版本 —— 与《书单_四象限》已处理部同版本；带刊刻形态词者另作「版本待核」保留
  R6 同书多载体  —— 同一本书的多个载体，保留最完整件（页数多者）
  R7 保留        —— 谱系内、尚未收录的版本 / 注本 / 影印本 / 电子文本

产出：30_待验区逐件台账.csv + 31_书名索引_可扩展医籍.csv
"""
import os, re, json, csv, collections

ROOT = "/Users/levi/Documents/医/共创/伤寒杂病论/_待验/"
OUT  = "/Users/levi/Documents/医/共创/伤寒杂病论/29_待验区筛选/"
HASH = "/tmp/shl_scan/hashes.tsv"
PROBE= "/tmp/shl_scan/probe.json"

# ── 项目既有登记（来源：书单_四象限.md + 11_缺书清单_总书谱系.md + index.html 版本键）──
# 已下载·已处理（18 部）
ALREADY = [
 ("L1","伤寒论","宋本·赵开美《仲景全书》本",1599), ("L2","伤寒论","千金要方(唐本)",752),
 ("L3","伤寒论","康平本",1159),             ("L4","伤寒论","康治本",1142),
 ("L5","伤寒论","高继冲本(淳化本)",992),   ("L6","伤寒论","注解伤寒论(成无己)",1144),
 ("L7","伤寒论","脉经(王叔和)",210),       ("L8","金匮玉函经","金匮玉函经",219),
 ("L9","伤寒杂病论","桂林古本(白云阁藏本)",1932), ("L10","伤寒论","敦煌写本 S.202+P.3287",945),
 ("A1","金匮要略","赵开美《仲景全书》本",1599), ("A2","金匮要略","邓珍本(现存最早刊本)",1340),
 ("A3","金匮要略","俞桥本",1522),          ("A4","金匮要略","医统正脉本(吴勉学)",1601),
 ("A10","金匮要略","人民卫生出版社排印本",1964),
 ("B1","伤寒杂病论","千金翼方",652), ("B2","伤寒杂病论","外台秘要",752),
 ("B3","伤寒杂病论","医心方",984),
]
# 已登记但「未取得实体」的缺书 —— 待验区若出现即属补缺命中，价值最高
WANTED = {
 "D1":["和气氏","和气朝臣","和气保固"], "D2":["伤寒明理论"],
 "A5":["文瑞堂"], "A6":["宝纶堂"], "A7":["崇文斋"], "A8":["江东书局"], "A9":["商务印书馆"],
 "C1":["长沙古本","湘古本","何芸樵"],   "C2":["涪陵本"],
}
# R1 非文献载体
NON_DOC_EXT = {".wma", ".ppt", ".pptx", ".jpg", ".jpeg", ".png"}

# ── R3 主题错配：与伤寒/金匮谱系无关的科别与同名歧义 ──
OFF_TOPIC = [
 (r"金匮县",          "地名同名：无锡金匮县地方志，与《金匮要略》无关"),
 (r"金匮银楼",        "同名歧义：银楼商号广告，非医籍"),
 (r"黄帝金匮玉衡经",   "道教《玉衡经》与《金匮要略》无关"),
 (r"太公金匮",        "《太公金匮》兵书，与《金匮要略》无关"),
 (r"周髀算经",        "术数理论研究，与版本无关"),
 (r"儿\s*科",          "儿科，非伤寒金匮谱系"),
 (r"妇\s*科",          "妇科，非伤寒金匮谱系"),
 (r"针\s*灸",          "针灸，非伤寒金匮谱系"),
 (r"外\s*科",          "外科，非伤寒金匮谱系"),
 (r"眼\s*科",          "眼科，非伤寒金匮谱系"),
 (r"正\s*骨",          "正骨，非伤寒金匮谱系"),
 (r"痘\s*疹",          "痘疹，非伤寒金匮谱系"),
 (r"运气心法",        "运气心法，非伤寒金匮注本"),
 (r"四诊心法",        "四诊，非伤寒金匮注本"),
 (r"删补名医方论",    "方论，非伤寒金匮注本"),
 (r"杂病心法",        "杂病心法，非《金匮要略》"),
 (r"幼科心法",        "幼科，非伤寒金匮谱系"),
 (r"刺灸心法",        "刺灸，非伤寒金匮谱系"),
 (r"金匮与风湿病研究","现代研究文章，非版本"),
 (r"治则治法探讨",    "现代研究文章，非版本"),
 (r"教研现状",        "现代教研文章，非版本"),
 (r"外感温热篇",      "温病阐释，非伤寒金匮版本"),
 (r"医药典故|药性赋|汤头歌", "药学歌赋类，非版本"),
]

# ── R3b 学术论文/短文（体积小 + 页数少 + 标题带研究性词汇）──
PAPER_HINT = re.compile(r"研究|探讨|探析|浅析|浅谈|浅论|新探|新论|考据|考证|考辨|"
                        r"关系考|版本考|古传本|当出自|证治总例|略例|述要|考|论|议|说|析")
PAPER_MAX_BYTES = 2*1024*1024
PAPER_MAX_PAGES = 20

# ── R4 谱系核心词（CORE）：命中其一才属本谱系 ──
# 「刻本/钞本/注/疏…」等辅助词必须与核心词共现才成立，故不单列为 CORE。
CORE = re.compile(
 r"伤寒|傷寒|金匮|金匱|仲景|桂林|康平|康治|敦煌|高继冲|高繼沖|淳化|和气|和氣|"
 r"脉经|脈經|脉真经|醫脈眞經|千金|外台|外臺|医心方|醫心方|汤液经|湯液經|"
 r"玉函|六经|六經|伤寒杂病论|傷寒雜病論")
# 「刊刻形态」词：与已收录部同名但形态不同 → 版本待核，保留
EDITION_FORM = re.compile(
 r"宋本|元刊|元版|宋刊|宋刻本|南宋刊|钞本|旧钞|抄本|稿本|手稿|红格|清稿|"
 r"影印|影宋|再钞|明钞|残卷|墨迹|朝鲜本|和刻|民国|石印|铅印|影写")
# 「丛书」标志：命中则标为丛书分册（供后续衍生扩展识别）
SERIES = re.compile(
 r"中医古籍珍本集成|中医古籍整理丛书|中国医学大成|皇汉医学丛书|中国汤液经方|"
 r"和刻汉籍医书集成|伤寒论注十人书|中医古籍名著丛书|近代中医珍本集|"
 r"中国医学大成续编|中医必读百部名[著着]|中国古医籍珍本集成|"
 r"中国医学大成|历代中医珍本集成|中医经典临证发微|中医药学高级丛书|"
 r"皇汉医学|医方精要系列|白话中医四部经典|图解国医典藏")
# 「现代注家」标志 → 现代注本
MODERN_AUTHOR = re.compile(
 r"刘渡舟|黄竹斋|何任|李克绍|陆渊雷|陈修园|徐灵胎|徐忠可|汪佑？|汪琥|柯琴|"
 r"喻嘉言|方有执|成无己|张志聪|尤怡|朱丹溪|张元素|王叔和|张仲景|"
 r"李今庸|陆渊雷|章巨膺|任应秋|俞长荣|李聪甫|秦伯未|熊曼琪|陈纪藩|"
 r"金匮翼|金匮悬解|金匮要略心典")
# 「现代讲研」标志
MODERN_TALK = re.compile(r"讲稿|讲义|讲课实录|课堂实录|论坛讲记|讲座|实录|问答|研究|概论|探讨|新解|新论|纵横|心得体会")

# ── R5 已收录同版本（精确匹配；与 v1 的区别见文件头注释）──
DONE_TITLES = [
 r"宋本伤寒论校注", r"校正宋版伤寒论", r"宋版伤寒论\.epub",
 r"古本康平伤寒论", r"康平本伤寒论——", r"伤寒论\.汉张仲景著\.康平本",
 r"康治本伤寒论",
 r"桂林古本伤寒", r"伤寒杂病论·桂林古本", r"桂林孤本伤寒杂病论", r"伤寒杂病论桂林古本",
 r"伤寒论注解-成无己", r"伤寒论注解 ",
 r"金匮玉函经(?!二注|要略辑义|辑义|衍义|补注)",
 r"敦煌写本", r"S\.202",
 r"邓珍", r"俞桥", r"医统正脉", r"金匮要略_第10版",
]
# 版本存疑 → 不删，改判 K2「版本待核」保留（项目内无原件留存，删了不可复原）
DONE_SOFT = [
 r"伤寒论（1-5卷）", r"伤寒论\(1-5卷\)",
]
# 说明：L1 宋本赵开美、L6 注解伤寒论(成无己) 的待验区件多数为「电子/影印复本」，
#       由 R5 + R6 处理；带刊刻形态词的（如元刊 S201）另作版本待核保留。

def load():
    rows=[]
    with open(HASH, encoding="utf-8") as f:
        for line in f:
            p=line.rstrip("\n").split("\t")
            if len(p)==3: rows.append({"rel":p[2],"sha256":p[0],"bytes":int(p[1])})
    probe={}
    for r in json.load(open(PROBE, encoding="utf-8")):
        probe[os.path.normpath(r["rel"])]=r          # ← 关键修正：去掉前缀差异
    for r in rows:
        key=os.path.normpath(r["rel"])
        r.update({k:v for k,v in probe.get(key,{}).items() if k not in ("rel","sha256","bytes")})
        if "ext" not in r:
            r["ext"]=os.path.splitext(r["rel"])[1].lower()
        r.setdefault("ext", os.path.splitext(r["rel"])[1].lower())
    return rows

def is_numbered(t):
    """文件名是否为「纯编号型」（书名由所在目录承载）——如 001.pdf / 一册.pdf / ZHSY000201_01.pdf"""
    s = re.sub(r"[0-9A-Za-z]", "", t)
    s = re.sub(r"[一二三四五六七八九十冊册卷本篇上下中部分第页張张]", "", s)
    s = re.sub(r"[\s._\-—()（）]", "", s)
    return len(s) == 0

def clean_title(rel):
    """从路径提取书名；纯数字文件名回退用父目录名。"""
    fn = os.path.basename(rel)
    t = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", fn)
    t = re.sub(r"^\s*[A-Z]?\d+[-.、_ ]", "", t)
    t = re.sub(r"^\d{2,4}[-.、]", "", t)
    t = re.sub(r"^[A-Z]\d+[-.、]?", "", t)
    t = re.sub(r"^\[\[?([^\]]{2,20})\]\]?.*$", r"\1", t)
    t = re.sub(r"^(www\.[^\s]+)\s*", "", t)
    t = re.sub(r"\s*[-–—]\s*\(?(Z-Library|z-library|1lib|z-lib)[^)]*\)?\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*\(?\(Z-Library\)[^)]*\)?\s*$", "", t, flags=re.I)
    t = re.sub(r"[（(]扫描版[^）)]*[）)]?", "", t)
    t = re.sub(r"\s+", " ", t).strip(" -_·")
    if not t or is_numbered(t):                       # 形如 001.pdf / 一册.pdf / ZHSY000201_01.pdf
        d = os.path.basename(os.path.dirname(rel))
        d = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", d)
        t = re.sub(r"\s+", " ", d).strip(" -_·")
    return t

def core_text(rel, meta):
    """谱系核心词判定文本：文件名 + 元数据；纯编号文件名追加所在目录名（目录承载书名）。"""
    fn = os.path.basename(rel)
    t = fn + " " + str(meta or "")
    if is_numbered(re.sub(r"\.[A-Za-z0-9]{2,5}$", "", fn)):
        t += " " + os.path.dirname(rel)
    return t

def title_key(rel):
    """严格书名键（用于书名索引）：去括号、去掉部分/卷册尾注。"""
    t = clean_title(rel)
    t = re.sub(r"[（(][^）)]*[）)]", "", t)
    t = re.sub(r"^第[一二三四五六七八九十\d]+[辑冊册卷].*$", "", t)
    t = re.sub(r"[·\-—_]\s*(部分\d+|卷\d+.*|\d+册|上|下|中)\s*$", "", t)
    t = re.sub(r"\s+", "", t)
    return t

def dup_key(rel):
    """宽松书名键（用于「同书多载体」择优）：同书不同部分(部分N/卷N)保持独立。"""
    t = clean_title(rel)
    t = re.sub(r"[（(][^）)]*[）)]", "", t)
    t = re.sub(r"[-_ ]\d{1,8}\s*$", "", t)              # 尾部分册号/下载ID -1 / 12091379
    # 逐段剥离尾注段（作者/出版地/机构/年份），保留书名主体
    parts = [x for x in t.split("_") if x]
    tail = re.compile(r"(编著|撰|著|译|主编|校注|出版|书局|出版社|公司|堂|馆|院|"
                      r"第|卷|册|部分|年|元|明|清|宋|民国|版本|影印|扫描|高清|无水印|"
                      r"不可复制|简体|繁体|横版|竖版|z-library|Z-Library|1lib)")
    keep = []
    for seg in parts:
        if keep and (tail.search(seg) or re.fullmatch(r"[\d\s.,:：\-—]+", seg)):
            break
        keep.append(seg)
    if len(keep) < len(parts):          # 剥离后主体过短则放弃剥离，避免误并组
        if len("_".join(keep)) < 3:
            keep = parts
    t = "_".join(keep)
    t = re.sub(r"\s+", "", t)
    return t

def is_part_of_book(rel):
    """同书不同部分标记：纯编号分册(001/一册/ZHSY…_02) 或「…部分1」「…卷二」「…上」→ 不参与择优删除。"""
    fn = os.path.basename(rel)
    stem = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", fn)
    if is_numbered(stem):          # 纯编号分册：书名由目录承载，各册内容不同
        return True
    t = clean_title(rel)
    return bool(re.search(r"(部分\s*\d+|卷[一二三四五六七八九十\d]+|上|下|中)$", t.strip()))

def classify(rows):
    by_sha = collections.defaultdict(list)
    for r in rows: by_sha[r["sha256"]].append(r)

    def sha_keep(g):
        want=[r for r in g if any(any(k in os.path.basename(r["rel"]) for k in keys)
                                 for keys in WANTED.values())]   # 文件名直接命中优先
        if want: return sorted(want,key=lambda r:(r["rel"].count("/"), len(r["rel"])))[0]
        want=[r for r in g if want_hit(r)]
        if want: return sorted(want,key=lambda r:(r["rel"].count("/"), len(r["rel"])))[0]
        tgt=[r for r in g if r["rel"].startswith("./target/")]
        pool=tgt or g
        return sorted(pool,key=lambda r:(-(r.get("pages") or 0), -r["bytes"], r["rel"]))[0]

    # 同书多载体分组
    by_dup = collections.defaultdict(list)
    for r in rows: by_dup[dup_key(r["rel"])].append(r)
    dup_pick={}
    for k,g in by_dup.items():
        if len(g)<2: continue
        cand=[r for r in g if not is_part_of_book(r["rel"]) and r["ext"]==".pdf"]          # 电子文本体积极小且可作转录素材，不参与择优
        if len(cand)<2: continue
        best=sorted(cand,key=lambda r:(-(r.get("pages") or 0), -r["bytes"], r["rel"]))[0]
        for r in g:
            if r is not best and r["ext"]==".pdf" and not is_part_of_book(r["rel"]):
                dup_pick[r["rel"]]=(best,len(g))

    out=[]
    for r in rows:
        rel=r["rel"]; fn=os.path.basename(rel); ext=r["ext"]
        title=clean_title(rel); key=title_key(rel); dkey=dup_key(rel)
        meta=str(r.get("title_meta") or "")
        pages=r.get("pages")
        hay=fn+" "+meta+" "+str(r.get("text_head") or "")   # 三源匹配
        verdict="保留"; reason="谱系内相关版本，尚未收录"; code="K"
        carrier=""
        if ext==".pdf":
            carrier = "影印扫描(无文本层)" if not r.get("has_text") else "排印本(含文本层)"
        elif ext in (".txt",".doc",".docx",".epub",".mobi",".azw3",".uvz",".azw"):
            carrier="电子文本"
        elif ext in NON_DOC_EXT:
            carrier={".wma":"音频讲座",".ppt":"教学课件",".pptx":"教学课件",
                     ".jpg":"散页图",".jpeg":"散页图",".png":"散页图"}.get(ext,"非文献")
        # 类型标注（供后续衍生扩展）
        if SERIES.search(hay):           typ="丛书分册"
        elif MODERN_TALK.search(title):  typ="现代讲研"
        elif MODERN_AUTHOR.search(title) and not EDITION_FORM.search(title): typ="现代注本"
        elif ext in (".txt",".epub",".doc",".docx",".mobi"): typ="电子文本"
        elif carrier.startswith("影印"): typ="古籍影印"
        else:                             typ="古籍排印"

        hit=[c for c,keys in WANTED.items() if any(k in hay for k in keys)]

        # R0 字节级重复
        if len(by_sha[r["sha256"]])>1:
            g=by_sha[r["sha256"]]; keep=sha_keep(g)
            if r is not keep:
                verdict,code,reason="删除","D1",f"字节级重复（sha256 与 {keep['rel'][2:]} 相同，{len(g)}件中非首选）"
            else:
                verdict,code,reason="保留","K0",f"字节级重复组首选件（{len(g)}件同内容，保留此件）"

        # R1 非文献载体
        if code=="K" and ext in NON_DOC_EXT:
            verdict,code,reason="删除","D2",f"非文献载体（{carrier}），不入版本库"

        # R2 缺书命中（最高价值，先于一切删除判定）
        if code=="K" and hit:
            verdict,code="保留","K1"
            reason=f"补缺命中（《缺书清单》{','.join(hit)}）：{title}｜原登记为「实体待补传」，本次首次取得"

        # R3 主题错配
        if code=="K":
            for pat,why in OFF_TOPIC:
                if re.search(pat, fn):
                    verdict,code,reason="删除","D3",f"主题错配：{why}"; break

        # R3b 学术论文/短文
        if code=="K" and ext==".pdf" and pages and r["bytes"]<=PAPER_MAX_BYTES \
           and pages<=PAPER_MAX_PAGES and PAPER_HINT.search(title) and not EDITION_FORM.search(title):
            verdict,code,reason="删除","D3b","学术论文/研究短文，非版本实体（书名已入索引，供后续衍生扩展）"

        # R4 谱系外（无核心词）
        if code=="K" and not CORE.search(core_text(rel, meta)):
            verdict,code,reason="删除","D4","谱系外：文件名与元数据均无伤寒/金匮谱系线索"

        # R5 已收录同版本（带刊刻形态词者改判「版本待核」保留）
        if code=="K":
            soft=[p for p in DONE_SOFT if re.search(p, fn)]
            if soft:
                verdict,code,reason="保留","K2",f"疑为已收录部（{soft[0]}），但无法确证同一版本 → 版本待核，暂留"
            for pat in DONE_TITLES:
                if re.search(pat, fn):
                    if EDITION_FORM.search(fn) or EDITION_FORM.search(meta):
                        verdict,code,reason="保留","K2",f"与已收录部同名，但刊刻形态不同（{pat}）→ 版本待核，暂留"
                    else:
                        verdict,code,reason="删除","D5",f"已收录同一版本（{pat}），不重复入库"
                    break

        # R6 同书多载体择优
        if code=="K" and r["rel"] in dup_pick:
            best,n=dup_pick[r["rel"]]
            verdict,code,reason="删除","D6",(f"同书多载体择优：同书 {n} 件，保留最完整件 "
                                            f"{os.path.basename(best['rel'])}（{best.get('pages') or '-'} 页 / {best['bytes']/1048576:.1f} MB）")

        r.update({"title":title,"title_key":key,"dup_key":dkey,"verdict":verdict,"code":code,
                  "reason":reason,"carrier":carrier,"typ":typ,"pages":pages or "",
                  "wanted":",".join(hit)})
        out.append(r)
    return out

def want_hit(r):
    hay=os.path.basename(r["rel"])+" "+str(r.get("title_meta") or "")+" "+str(r.get("text_head") or "")
    return any(any(k in hay for k in keys) for keys in WANTED.values())

def main():
    rows=load()
    res=classify(rows)
    os.makedirs(OUT, exist_ok=True)

    with open(OUT+"30_待验区逐件台账.csv","w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow(["序号","判定","代码","类型","书名","归一化书名键","目录","文件名","字节","MB","页数",
                    "载体","sha256","缺书命中","理由","完整路径"])
        for i,r in enumerate(sorted(res,key=lambda x:(x["verdict"],x["rel"])),1):
            w.writerow([i,r["verdict"],r["code"],r["typ"],r["title"],r["title_key"],
                        os.path.dirname(r["rel"]).replace("./",""),os.path.basename(r["rel"]),
                        r["bytes"],round(r["bytes"]/1048576,2),r["pages"],r["carrier"],
                        r["sha256"][:16],r["wanted"],r["reason"],r["rel"]])

    idx=collections.OrderedDict()
    for r in res:
        k=r["title_key"]
        if not k: continue
        e=idx.setdefault(k,{"files":0,"bytes":0,"v":collections.Counter(),
                            "dirs":set(),"paths":[],"sample":r["title"],"types":collections.Counter(),
                            "pages":0})
        e["files"]+=1; e["bytes"]+=r["bytes"]; e["v"][r["verdict"]]+=1
        e["types"][r["typ"]]+=1
        e["pages"]=max(e["pages"], r.get("pages") or 0)
        e["dirs"].add(os.path.dirname(r["rel"]).replace("./",""))
        e["paths"].append(r["rel"])
    with open(OUT+"31_书名索引_可扩展医籍.csv","w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow(["序号","书名(归一)","原始书名样本","件数","合计MB","最大页数","保留件","删除件",
                    "类型分布","所在目录","全部路径"])
        for i,(k,e) in enumerate(sorted(idx.items(),key=lambda kv:(-kv[1]["files"],kv[0])),1):
            w.writerow([i,k,e["sample"][:60],e["files"],round(e["bytes"]/1048576,2),e["pages"],
                        e["v"].get("保留",0),e["v"].get("删除",0),
                        ";".join(f"{a}×{b}" for a,b in e["types"].most_common()),
                        ";".join(sorted(x for x in e["dirs"] if x))," | ".join(e["paths"])])

    json.dump(res, open("/tmp/shl_scan/classified.json","w",encoding="utf-8"), ensure_ascii=False)

    st=collections.Counter((r["verdict"],r["code"]) for r in res)
    print("=== 判定统计 ===")
    for (v,c),n in sorted(st.items()):
        b=sum(r["bytes"] for r in res if r["verdict"]==v and r["code"]==c)
        print(f"  {v}  {c:<3} {n:>5} 件  {b/1048576:>9.1f} MB")
    for v in ("保留","删除"):
        g=[r for r in res if r["verdict"]==v]
        print(f"  → {v}: {len(g)} 件 / {sum(r['bytes'] for r in g)/1048576:.1f} MB")
    print(f"  书名索引条目: {len(idx)}")
    print("  类型分布:", dict(collections.Counter(r["typ"] for r in res if r["verdict"]=="保留")))

if __name__=="__main__":
    main()
