#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整合 work.txt(首句) + last.txt(末句) + 条号定位，产出72行页条对照.csv"""
import csv, re, subprocess, os

ROOT="/private/tmp/yi/1/unpacked45/45_派发包_A_田边宪本条目比对"
WORK="/private/tmp/yi/1/work45"

# 读首句
first={}
for line in open(f"{WORK}/work.txt",encoding="utf-8"):
    if "\t" in line:
        p,q=line.rstrip("\n").split("\t",1); first[p]=q
# 读末句（分隔符可能是 tab 或全角空格）
last={}
for line in open(f"{WORK}/last.txt",encoding="utf-8"):
    line=line.rstrip("\n").lstrip("\ufeff")
    parts=line.replace("\t","　").split("　",1)
    if len(parts)==2 and parts[0].startswith("p"):
        last[parts[0]]=parts[1].strip()

# 人工从 located.txt 选定的首条号（结合覆盖率与篇序）
FIRSTNO={
 8:1,9:13,10:248,11:24,12:23,13:29,14:34,15:38,16:41,17:56,
 18:54,19:93,20:60,21:64,22:70,23:141,24:67,25:91,26:96,27:101,
 28:147,29:104,30:149,31:102,32:112,33:124,34:143,35:134,36:135,
 37:208,38:172,39:172,40:252,41:164,42:157,43:164,44:156,
 45:77,46:168,47:180,48:208,49:209,50:214,51:215,52:238,
 53:220,54:219,55:223,56:229,57:261,58:257,59:233,60:252,
 61:273,62:301,63:303,64:306,65:370,66:318,67:320,68:326,
 69:338,70:356,71:389,
}
# 可信度（人工，按定位覆盖率）
CONF={
 8:"高",9:"中",10:"高",11:"高",12:"中",13:"低",14:"高",15:"中",16:"高",17:"高",
 18:"中",19:"中",20:"高",21:"高",22:"高",23:"高",24:"中",25:"高",26:"低",27:"中",
 28:"高",29:"高",30:"中",31:"高",32:"低",33:"高",34:"中",35:"高",36:"高",
 37:"低",38:"高",39:"高",40:"中",41:"高",42:"中",43:"高",44:"高",
 45:"高",46:"中",47:"高",48:"高",49:"中",50:"中",51:"高",52:"高",
 53:"高",54:"高",55:"中",56:"中",57:"低",58:"高",59:"中",60:"中",
 61:"高",62:"中",63:"中",64:"中",65:"中",66:"中",67:"中",68:"中",
 69:"中",70:"低",71:"中",
}

def decide_end(p):
    a=FIRSTNO[p]
    nxt=FIRSTNO.get(p+1)
    if nxt is not None and nxt>=a:
        b=nxt-1
    else:
        b=a+4
    if b<a: b=a
    if b>398: b=398
    return b

rows=[]
rows.append(["页号","首条号","末条号","首句","末句","可信度","备注"])

for p in range(1,73):
    pg=f"p{p:03d}"
    if p==1:
        rows.append([pg,"—","—","—","—","—","封面题签「傷寒論 田邊憲書」「完」，双藏印"])
        continue
    if 2<=p<=7:
        rows.append([pg,"—","—","—","—","—",f"序跋文第{p-1}叶，非正文"])
        continue
    if p==72:
        rows.append([pg,"—","—","—","—","—","封底无字，纸纹"])
        continue
    a=FIRSTNO[p]; b=decide_end(p)
    if p==71: b=389  # 末叶止于389条四逆汤，其后为跋文
    s1=first.get(pg,"未定"); s2=last.get(pg,"未定")
    cf=CONF.get(p,"中")
    note=""
    if "□" in s1 or "□" in s2: note="含辨不清字，以□标"
    if not note: note="—"
    rows.append([pg,str(a),str(b),s1,s2,cf,note])

out=f"{ROOT}/交付/页条对照.csv"
with open(out,"w",encoding="utf-8-sig",newline="") as f:
    csv.writer(f).writerows(rows)
print("written",out,"rows",len(rows)-1)
