#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
待验区重构：把 _待验/ 下的 470 件保留件，按「黄帝内经」式编号分类结构重新归置并改名。

设计要点
--------
1) 分类只用**可核验字段**（书名 / 形态词 / 谱系编号 / 载体），不靠版本学知识猜测。
2) 三类重点分开存放：
   - 02_高价值版本   版本学价值高（宋元明刊、钞稿、影宋、活字、和刻），且不撞已收录部书名
   - 03_同名异刻     与《书单_四象限》已收录 18 部同名，但**刊刻形态可辨不同** → 版本扩充线索
   - 04_版本待核     与已收录部同名，但**形态标识缺失** → 无法确证是否同版本
3) 命名规范：<谱系编号>_<书名>_<形态特征>_<分册>.<ext>
   —— 一眼能看出「哪一版」。
4) 优先级（互斥、可复跑）：补缺命中 > 同名异刻 > 版本待核 > 古本高价值 > 注本辑校 > 现代著述 > 电子文本
"""
import json, os, re, csv, shutil, sys, unicodedata

def load_strong():
    """正文序跋强证据（版本独有标识）→ {rel: [(code,name,form)]}"""
    p = f"{SCAN}/probe2.json"
    if not os.path.exists(p):
        return {}
    d = json.load(open(p, encoding="utf-8"))
    out = {}
    for rel, v in d.items():
        s2 = [m for m in v.get("markers", []) if not str(m[2]).startswith("WEAK:")]
        if s2:
            out[rel] = s2
    return out

ROOT = "/Users/levi/Documents/医/共创/伤寒杂病论/_待验"
SCAN = "/tmp/shl_scan"
OUT  = "/Users/levi/Documents/医/共创/伤寒杂病论/29_待验区筛选"

# ───────────────────────────── 已收录 18 部（书单_四象限.md）─────────────────────────────
# 用「完整书名」精确匹配，不用子串（避免「金匮玉函经二注」误撞 L8「金匮玉函经」）
COLLECTED = [
    ("L1",  "伤寒论",        [r"^伤寒论$", r"^伤寒论\s*[（(]1-5卷[）)]$", r"^伤寒论简体版",
                             r"^伤寒论篇\d+$", r"^伤寒论 田边睿书$", r"^伤寒论_田边睿书$"]),
    ("L2",  "千金要方",      [r"^千金要方$"]),
    ("L3",  "康平本",        [r"^古本康平伤寒论", r"^康平本伤寒论"]),
    ("L4",  "康治本",        [r"^康治本伤寒论$", r"^康治本$"]),
    ("L5",  "高继冲本",      [r"^高继冲本", r"^淳化本"]),
    ("L6",  "注解伤寒论",    [r"^注解伤寒论$", r"^伤寒论注解", r"^元版.*伤寒论注解",
                             r"^伤寒论注十人书—注解伤寒论", r"^中医古籍珍本集成.*注解伤寒论$"]),
    ("L7",  "脉经",          [r"^脉经$"]),
    ("L8",  "金匮玉函经",    [r"^金匮玉函经$", r"^金匮玉函$"]),
    ("L9",  "桂林古本",      [r"^伤寒杂病论·桂林古本", r"^桂林古本", r"^桂林孤本"]),
    ("L10", "敦煌写本",      [r"^敦煌", r"^S\.202"]),
    ("A1",  "赵开美仲景全书",[r"^订正仲景全书伤寒论注$", r"^订正仲景全书金匮要略注$"]),
    ("A2",  "邓珍本",        [r"^邓珍本$"]),
    ("A4",  "医统正脉本",    [r"^医统正脉", r"^仲景全书$"]),
    ("A10", "人卫1964",      [r"^金匮要略\s*[（(]第10版"]),
    ("B1",  "千金翼方",      [r"^千金翼方$"]),
    ("B2",  "外台秘要",      [r"^外台秘要$"]),
    ("B3",  "医心方",        [r"^医心方$"]),
]
# 缺书清单 9 部（未取得实体 → 本目录命中即为补缺）
WANTED = {
    "D1": [r"和气氏", r"和气朝臣", r"和气保固"],
    "D2": [r"伤寒明理论", r"明理药方论"],
    "A5": [r"文瑞堂"], "A6": [r"宝纶堂"], "A7": [r"崇文斋"],
    "A8": [r"江东书局"], "A9": [r"商务印书馆"],
    "C1": [r"长沙古本", r"湘古本", r"何芸樵"], "C2": [r"涪陵本"],
}

# ───────────────────────────── 形态词表 ─────────────────────────────
# 古本形态（用于「高价值版本」判定）
ANCIENT_FORM = [
    ("影宋本","影宋本"),("泥活字","泥活字"),("活字本","活字本"),("旧钞本","旧钞本"),
    ("钞本","钞本"),("稿本","稿本"),("手稿本","手稿本"),("清稿本","清稿本"),
    ("红格","红格"),("朱格","朱格"),("墨格","墨格"),
    ("宋刊","宋刊"),("宋刻本","宋刻本"),("宋版","宋版"),("南宋刊","南宋刊"),("北宋刊","北宋刊"),
    ("元刊","元刊"),("元版","元版"),
    ("明刊","明刊"),("明刻","明刻"),("和刻","和刻"),("和刻本","和刻本"),
    ("清刊","清刊"),("清刻","清刻"),("影印","影印"),("扫描","扫描"),
]
# 纪年 / 刊刻者 / 形态特征（命名时保留）
FEATURE = [
    ("宋乾道七年","宋乾道七年"),("乾道七年","乾道七年"),
    ("宋景定元年","宋景定元年"),("景定元年","宋景定元年"),
    ("清道光三年","清道光三年"),("道光三年","清道光三年"),
    ("清旌德","清旌德"),("弘治","弘治"),("嘉靖","嘉靖"),("万历","万历"),
    ("顺治","顺治"),("康熙","康熙"),("雍正","雍正"),("乾隆","乾隆"),
    ("嘉庆","嘉庆"),("道光","道光"),("咸丰","咸丰"),("同治","同治"),
    ("光绪","光绪"),("宣统","宣统"),("民国","民国"),("昭和","昭和"),
    ("躋壽館","躋壽館"),("跻寿馆","跻壽館"),("和刻","和刻"),("古刻","古刻"),
    ("四部丛刊","四部丛刊"),("百衲本","百衲本"),("影刻","影刻"),("手录","手录"),
    ("卷上","卷上"),("卷中","卷中"),("卷下","卷下"),

]
# 出版/格式噪音（剥离，不进文件名）
NOISE = [
    r"\s*[（(]\s*Z-?Library[^）)]*[）)]", r"\s*[（(]\s*z-library[^）)]*[）)]",
    r"\s*—\s*$", r"\s*_\s*$",
    r"\s*_?\d{7,8}$",                     # z-library 数字尾
    r"^www\.[A-Za-z0-9.]+\s+",            # 站点前缀
    r"^https?://\S+\s+",
    r"_高清无水印_无书签_不可复制", r"高清无水印", r"无书签", r"不可复制",
    r"（高清版）", r"\(高清版\)", r"_高清版", r"（高清）",
    r"（扫描版）", r"\(扫描版\)", r"扫描版",

    r"\s*[（(][^）)]*(?:出版|印刷|排印|扫描|高清|无水印|无书签|不可复制|Z-?Library|z-library)[^）)]*[）)]",
    r"\s*[（(][^）)]*(?:撰|著|注|校注|辑|订正|整理|点校|审订)[^）)]*[）)]",
    r"第\d+版", r"新世纪第\d+版",
    r"\s*[（(]供中医专业用[）)]", r"\s*[（(]中医案头必备用书[）)]",
    r"（套装共\d+册）", r"\(套装共\d+册\)",
    r"\s*-\s*第\d+辑\s*$", r"\s*第\d+辑\s*$",
]
# 库编号前缀
PREFIX_ID = re.compile(r"^(?:[A-Z]{0,3}\d{2,6}[A-Z]?\.\s*|\d{1,3}\.\s*|ZHSY\d{6}\s*)")
# 电子文本类后缀编号（457-、465- 等）
TXT_ID = re.compile(r"^\d{3,4}-\s*")
# 分册尾号
PART_TAIL = re.compile(r"[-_](\d{1,2})$")

# 现代著述特征（须排除古籍同名书：《重订通俗伤寒论》《通俗伤寒论》等为清·程国彭）
MODERN_HINT = re.compile(
    r"讲稿|讲义|讲坛|讲记|讲课实录|讲座|授课|教程|白话精解|释疑|释读|诠释|讲解|"
    r"心得|体会|心得集|临床实验|新探|新解|方证|类方汇参|方法案|验案精选|"
    r"心得录|求索|探源|辞典|手册|精讲|问答|综述|临证指要|临床录|讲稿集|"
    r"选读|研读|漫画版|图解|口袋书|必读百部|白话中医|回归中医|科普|初步|入门")
# 「通俗」「浅说」「研究」「应用」等中性词：只有现代排印件才按现代著述判
MODERN_WEAK = re.compile(r"通俗|浅说|浅述|研究|应用|释义|详解|今释")
# 古籍载体（影印/丛书/古籍排印）里的中性词不算现代著述
TEXTBOOK_HINT = re.compile(r"讲义|教材|必读百部|口袋书|图解|漫画|白话精解|白话中医|科普|初步|入门")

# 朝代标记（括号内）：出现即判为古籍，缺一不可
DYNASTY = re.compile(r"[（(]\s*(东汉|西汉|汉|后汉|晋|唐|宋|北宋|南宋|元|明|清|秦|隋|魏|梁|齐)\s*[）)]")
# 古籍丛书（古籍影印/整理系列）
ANCIENT_SERIES = re.compile(
    r"中医古籍珍本集成|中医古籍整理丛书|中国医学大成|皇汉医学丛书|聿修堂医书选|"
    r"中华医书集成|近代中医珍本集|历代中医名著文库|湖湘名医典籍精华|"
    r"中医古籍名著丛书|历代中医珍本集成|四部丛刊|古今医统|珍本续刻")
# 现代丛书 / 教材系
MODERN_SERIES = re.compile(
    r"中医药学高级丛书|中医经典白话精解丛书|中医经典临证发微|三部六病医学流派丛书|"
    r"医方精要系列|现代著名老中医名著重刊丛书|中医师承学堂|白话中医四部经典|"
    r"国学堂|倪海厦人纪|湖湘名医典籍精华|中华医书集成|中医必读百部")
# 明确 20 世纪后半叶的现代作者（其著作为现代著述）
MODERN_AUTHOR = re.compile(
    r"万友生|裴慎|李克绍|乔模|余无言|郝万山|李培生|张家礼|王雪华|连建伟|李今庸|"
    r"章巨膺|俞长荣|黄竹斋|秦伯未|任应秋|刘渡舟|陈亦人|左季云|蔡德元|卞嵩京|"
    r"王渭川|李金庸|熊曼琪|熊寥笙|倪海厦|徐文兵|胡希恕|冯世纶|郭生白|李阳波|"
    r"孙曼之|肖相如|梁冬|余无言|曹颖甫|陆渊雷|恽铁樵|陈伯壇|陈伯墰|"
    r"熊曼琪|唐容川|邹洙安|曹颖甫")

# 古籍注本系统（清/民国及以前的具体注家）
# 古代注家（清代及以前）——其著作为版本学对象
ANCIENT_ANNOTATORS = ("成无己", "许叔微", "朱肱", "韩祗和", "庞安时", "刘昉", "陈自明",
    "张志聪", "徐彬", "喻嘉言", "汪机", "汪绮", "陈修园", "柯琴", "尤怡", "徐灵胎",
    "徐大椿", "黄元御", "黄坤载", "顾观光", "王叔和", "魏荔彤", "费伯雄", "周学海",
    "舒驰远", "张璐", "唐容川", "唐宗海", "沈明宗", "戴北野", "林亿", "赵以德",
    "周杨俊", "尤在泾", "秦越人", "孙思邈", "王焘", "丹波康赖", "李东垣", "张元素",
    "刘完素", "张子和", "朱丹溪", "李时珍", "张景岳", "叶天士", "钱潢", "张卿子",
    "舒诏", "程国彭", "徐用诚", "杨上善", "王冰", "滑寿", "李杲", "严用和", "王怀隐",
    "万全", "万全忠", "杨璇", "杨璿", "李柽", "郭雍", "韩祗", "王履", "周汉卿",
    "高武", "徐春甫", "龚廷贤", "龚贤", "李中梓", "张卿子", "陈自明", "高继冲")
ANNOTATORS = ANCIENT_ANNOTATORS

# 电子载体
ELEC_EXT = {".txt", ".epub", ".doc", ".docx", ".mobi", ".azw3", ".uvz", ".pdf"}

# ───────────────────────────── 工具函数 ─────────────────────────────
def is_numbered(t):
    s = re.sub(r"[0-9A-Za-z]", "", t)
    s = re.sub(r"[一二三四五六七八九十冊册卷本篇上下中部分第页張张]", "", s)
    s = re.sub(r"[\s._\-—()（）]", "", s)
    return len(s) == 0

def base_stem(rel):
    """取文件名主干；纯编号则回退到所在目录名（目录承载书名）。"""
    b = os.path.basename(rel)
    stem = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", b)
    if is_numbered(stem):
        d = os.path.basename(os.path.dirname(rel))
        return d + "｜" + stem          # 保留分册编号
    return stem

def strip_noise(s):
    for pat in NOISE:
        s = re.sub(pat, "", s)
    s = PREFIX_ID.sub("", s)
    s = TXT_ID.sub("", s)
    return re.sub(r"\s+", " ", s).strip(" -_·—、,，.")

def extract_features(s):
    """抽出形态/纪年特征词，去重保序；长词优先，短词被长词包含则丢弃。"""
    found = []
    for pat, tag in FEATURE:
        if re.search(pat, s):
            found.append(tag)
    found.sort(key=len, reverse=True)
    out = []
    for t in found:
        if not any(t != o and t in o for o in found):
            if t not in out:
                out.append(t)
    return sorted(out, key=lambda x: s.find(x) if x in s else 999)

def strip_features(s, feats):
    """把特征词从书名主体中摘掉（保留其余信息）。"""
    t = s
    for f in feats:
        t = t.replace(f, " ")
    # 摘掉后残留的连接符与序号
    t = re.sub(r"[_\-–—·,，、\s]+$", "", t)
    t = re.sub(r"^[_\-–—·,，、\s]+", "", t)
    return re.sub(r"\s{2,}", " ", t).strip(" -_·—、,，.")

def split_part(s):
    """拆出分册标记（上/下/中/卷X/册X）。"""
    m = re.search(r"[\s_]*(卷[上中下]|[上中下]册|第[一二三四五六七八九十\d]+册|上册|下册|中册)", s)
    if m:
        return s[:m.start()].strip(" -_·"), m.group(1)
    return s.strip(" -_·"), ""

def parse(r):
    """解析一件 → {book, feats, part, ext, raw}"""
    rel = r["rel"]
    ext = os.path.splitext(rel)[1].lower()
    raw = base_stem(rel)
    body = strip_noise(raw)
    feats = extract_features(body)
    # 年份（4 位）
    yrs = re.findall(r"(?<!\d)(1[6-9]\d\d|20[0-2]\d)\s*年?", body)
    for y in yrs:
        y = y.strip() + "年"
        if y not in feats:
            feats.append(y)
    body = re.sub(r"(?<!\d)(1[6-9]\d\d|20[0-2]\d)\s*年?", " ", body)
    body2 = strip_features(body, feats)
    book, part = split_part(body2)
    # 分册标记丢失时回填到 feats
    if part and part not in feats:
        feats.append(part)
    return {"book": book, "feats": feats, "part": part, "ext": ext, "raw": raw}

def match_collected(book, raw, rel):
    """是否与已收录 18 部同名 → 返回 (编号, 书名) 或 None"""
    cand = [book, raw]
    for code, name, pats in COLLECTED:
        for p in pats:
            for c in cand:
                if re.search(p, c):
                    return code, name
    return None

def match_wanted(book, raw, rel):
    txt = book + " " + raw + " " + rel
    for code, pats in WANTED.items():
        for p in pats:
            if re.search(p, txt):
                return code
    return None

def has_ancient_form(feats, book, raw, rel):
    t = " ".join(feats) + " " + book + " " + raw + " " + rel
    for pat, tag in ANCIENT_FORM:
        if re.search(pat, t):
            return tag
    return None

# ───────────────────────────── 分类 ─────────────────────────────
def classify(r, strong=None):
    p = parse(r)
    book, feats, part = p["book"], p["feats"], p["part"]
    rel = r["rel"]; ext = p["ext"]
    typ = r["typ"]
    strong = strong or {}

    wcode = match_wanted(book, p["raw"], rel)
    ccode = match_collected(book, p["raw"], rel)
    ancient = has_ancient_form(feats, book, p["raw"], rel)

    # 正文序跋强证据：能定出版式，直接进「同名异刻」并带出版式名
    sm = strong.get(rel[2:])
    if sm:
        code, vname, form = sm[0]
        # 若正文证据与文件名书名冲突 → 以正文为准
        if ccode and ccode[0] != code:
            ccode = (code, vname)
        elif not ccode:
            ccode = (code, vname)
        feats = [form] + [f for f in feats if f not in form]
        return "03_同名异刻", code, book, feats, part, ext, \
               f"正文序跋实证：{form} → 与已收录 {code} 同书，刊刻形态可辨不同"

    # 1) 补缺命中 —— 缺书清单登记的 9 部
    if wcode:
        return "02_高价值版本/01_补缺命中", wcode, book, feats, part, ext, \
               f"缺书清单 {wcode} 命中：首次取得实体"

    # 2) 同名异刻 —— 撞已收录部，但形态/年代/载者可辨不同
    if ccode:
        code, cname = ccode
        blob = book + " " + p["raw"] + " " + rel
        # 「形态差异证据」：刊刻形态词 / 正文序跋实证 / 明确年代 / 异丛书归属 / 异撰者
        diff_ev = (
            ancient                                   # 刊刻形态词（宋刊/钞本/活字…）
            or feats                                   # 已抽出的纪年/形态特征
            or sm                                      # 正文序跋实证
            or re.search(r"_[一-鿿]{2,3}\s*\(", blob)  # 括号内撰者（与已收录部不同）
            or re.search(r"注十人书|珍本集成|医大成|古籍整理丛书|聿修堂|皇汉医学|"
                         r"四部丛刊|医学大成|医略六书|十六种", blob)   # 异丛书归属
            or re.search(r"田边睿|叶橘泉|友助医学社|左盛德|赵开美", blob)  # 异整理者/藏家
        )
        if diff_ev:
            return "03_同名异刻", code, book, feats, part, ext, \
                   f"与已收录 {code}《{cname}》同名，但刊刻形态可辨不同 → 版本扩充线索"
        return "04_版本待核", code, book, feats, part, ext, \
               f"与已收录 {code}《{cname}》同名，形态标识缺失 → 无法确证是否同版本"

    # 3) 古本高价值（不撞已收录）
    if ancient and typ in ("古籍影印", "丛书分册", "古籍排印"):
        return "02_高价值版本/02_宋元明刊本" if ancient in ("宋刊","宋刻本","宋版","南宋刊","北宋刊","元刊","元版","明刊","明刻","和刻","和刻本") \
               else "02_高价值版本/03_清刻旧钞稿本", None, book, feats, part, ext, \
               f"古本形态：{ancient} → 版本学价值高"

    # 4) 注本辑校（清/民国及以前的具体注家，或古籍丛书收录）
    if typ in ("古籍影印", "丛书分册", "古籍排印") and (
            any(a in (book + p["raw"]) for a in ANNOTATORS)
            or re.search(r"中医古籍整理丛书|中国医学大成|中医古籍珍本集成|聿修堂医书选|皇汉医学", book + p["raw"])):
        return "05_注本辑校", None, book, feats, part, ext, "清民及以前注本 / 古籍丛书收录"

    # 5) 现代著述 —— 仅限「现代注本/现代讲研」类型，或明确教材特征
    if typ in ("现代注本", "现代讲研"):
        return "06_现代著述", None, book, feats, part, ext, "现代注本/讲稿/教材/工具书"
    if typ in ("古籍影印", "丛书分册", "古籍排印"):
        blob = book + " " + p["raw"] + " " + rel
        ancient_sig = (
            DYNASTY.search(blob)                       # 括号朝代标记
            or ANCIENT_SERIES.search(blob)              # 古籍丛书
            or ancient                                  # 刊刻形态词
            or any(a in blob for a in ANCIENT_ANNOTATORS)  # 古代注家
        )
        if ancient_sig and not (MODERN_AUTHOR.search(blob) and not DYNASTY.search(blob)
                                and not ancient):
            return "05_注本辑校", None, book, feats, part, ext, "古籍载体（影印/丛书分册/排印）"
        if MODERN_AUTHOR.search(blob) or MODERN_SERIES.search(blob):
            return "06_现代著述", None, book, feats, part, ext, "现代著作（扫描/影印）"
        return "05_注本辑校", None, book, feats, part, ext, "古籍载体（影印/丛书分册/排印）"
    # 电子文本：按内容分流
    if MODERN_HINT.search(book) or TEXTBOOK_HINT.search(book) or MODERN_WEAK.search(book):
        return "06_现代著述", None, book, feats, part, ext, "电子文本·现代著述（讲稿/教材/通俗读物）"
    return "07_电子文本", None, book, feats, part, ext, "电子文本（古籍转录素材）"

# ───────────────────────────── 命名 ─────────────────────────────
def safe(s):
    s = unicodedata.normalize("NFC", s)
    s = s.replace("/", "／").replace("\x00", "")
    s = re.sub(r"[·・•,，、;；:：!！?？\"'\'()（）\[\]【】<>《》]+", " ", s)
    s = re.sub(r"[+＋]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:60]

def build_name(code, book, feats, part, ext, used, idx):
    b = safe(book) or "未命名"
    b = b.replace("｜", " ").strip()
    tag = []
    if code:
        tag.append(code)
    for f in feats:
        if f not in tag and not (part and f == part):
            tag.append(f)
    if part and part not in tag:
        tag.append(part)
    name = "_".join(tag) if tag else ""
    base = (name + "_" + b) if name else b
    base = re.sub(r"_{2,}", "_", base).strip("_")
    # 去重
    cand = f"{base}{ext}"
    n = 2
    while cand.lower() in used:
        cand = f"{base}_{n}{ext}"; n += 1
    used.add(cand.lower())
    return cand

# ───────────────────────────── 主流程 ─────────────────────────────
def rescan_current():
    """迁移后重扫：直接枚举当前 _待验 结构，用 probe.json 的旧属性 + 新路径。"""
    old = {r["rel"][2:]: r for r in json.load(open(f"{SCAN}/classified.json", encoding="utf-8"))
           if r["verdict"] == "保留"}
    out = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), ROOT)
            r = dict(old.get(rel) or {})
            if not r:
                r = {"rel": "./" + rel, "bytes": os.path.getsize(os.path.join(dp, f)),
                     "sha256": "", "ext": os.path.splitext(f)[1].lower(),
                     "pages": None, "typ": "未分类", "title": f,
                     "title_meta": "", "has_text": False}
            r["rel"] = "./" + rel
            r["title"] = r.get("title") or f
            out.append(r)
    return out

def main():
    STRONG = load_strong()
    if "--rescan" in sys.argv:
        keep = rescan_current()
    else:
        rows = json.load(open(f"{SCAN}/classified.json", encoding="utf-8"))
        keep = [r for r in rows if r["verdict"] == "保留"]
    print(f"待处理 {len(keep)} 件；正文强证据 {len(STRONG)} 件")

    # 现有磁盘文件（校验用）
    actual = set()
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            actual.add(os.path.relpath(os.path.join(dp, f), ROOT))

    plan = []
    for r in keep:
        sub, code, book, feats, part, ext, reason = classify(r, STRONG)
        plan.append({"r": r, "sub": sub, "code": code, "book": book,
                     "feats": feats, "part": part, "ext": ext, "reason": reason})

    # 命名（同一目录内去重）
    used = {}
    for it in plan:
        key = it["sub"]
        u = used.setdefault(key, set())
        it["newname"] = build_name(it["code"], it["book"], it["feats"], it["part"], it["ext"], u, 0)

    # 校验源文件都在
    miss = [it for it in plan if it["r"]["rel"][2:] not in actual]
    if miss:
        print(f"!! 源文件缺失 {len(miss)} 件")
        for it in miss[:10]:
            print("   ", it["r"]["rel"])
        return 1

    # 输出映射表
    with open(f"{SCAN}/remap.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["目标目录", "新文件名", "原路径", "谱系编号", "书名", "形态特征",
                    "页数", "MB", "类型", "判定理由", "sha256"])
        for it in sorted(plan, key=lambda x: (x["sub"], x["newname"])):
            r = it["r"]
            w.writerow([it["sub"], it["newname"], r["rel"], it["code"] or "",
                        it["book"], ";".join(it["feats"]), r.get("pages") or "",
                        round(r["bytes"] / 1048576, 2), r["typ"], it["reason"], r.get("sha256") or ""])

    import collections
    print("\n=== 目标目录分布 ===")
    for d, n in sorted(collections.Counter(it["sub"] for it in plan).items()):
        b = sum(it["r"]["bytes"] for it in plan if it["sub"] == d)
        print(f"  {d:<34} {n:>4} 件 {b/1048576:8.1f} MB")
    print("\n=== 前 40 条映射（抽样）===")
    for it in sorted(plan, key=lambda x: (x["sub"], x["newname"]))[:40]:
        print(f'  {it["sub"]:<30} {it["newname"][:60]}')
    return 0

if __name__ == "__main__":
    sys.exit(main())
