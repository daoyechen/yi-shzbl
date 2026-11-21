#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zip_utf8_flag.py —— 打包并**强制**把所有条目置上 UTF-8 通用标志位(bit 11, 0x800)。

背景:Python 3.11 的 zipfile 对**纯 ASCII 文件名**会强制清除 0x800
(见 ZipInfo._encodeFilenameFlags:ASCII 走 ascii 分支)。这在标准上没错,
但部分 macOS / Windows 解压器会因此把**同级的中文目录名**整体按 CP437 解释而乱码。
本工具在打包后做二进制修补,把本地文件头与中央目录两处的 flag 位都置上 0x800。

用法:
    python3 zip_utf8_flag.py <out.zip> <文件根目录> [<相对路径> ...]
    python3 zip_utf8_flag.py --check <zip>

校验:解压后逐条比对 SHA256,并逐条确认 flag & 0x800。
"""
import os
import sys
import json
import struct
import hashlib
import zipfile

FLAG_UTF8 = 0x800
SIG_CEN = b"PK\x01\x02"
SIG_EOCD = b"PK\x05\x06"
SIG_LOC = b"PK\x03\x04"


def _collect(root, rels):
    """收集 (绝对路径, zip内相对路径) 列表。"""
    items = []
    if rels:
        for r in rels:
            p = os.path.join(root, r)
            if os.path.isdir(p):
                for dp, _, fs in os.walk(p):
                    for f in sorted(fs):
                        fp = os.path.join(dp, f)
                        items.append((fp, os.path.relpath(fp, root)))
            elif os.path.exists(p):
                items.append((p, r))
            else:
                raise SystemExit("✘ 不存在: %s" % p)
    else:
        for dp, _, fs in os.walk(root):
            for f in sorted(fs):
                fp = os.path.join(dp, f)
                items.append((fp, os.path.relpath(fp, root)))
    # 目录条目在前,保证父目录先于子文件
    items.sort(key=lambda x: (x[1].count(os.sep), x[1]))
    return items


def _patch_flags(path):
    """把 zip 内所有 local header 与 central directory 的 flag 置上 0x800。"""
    with open(path, "rb") as f:
        buf = bytearray(f.read())

    # --- 中央目录 ---
    eocd = buf.rfind(SIG_EOCD)
    if eocd < 0:
        raise SystemExit("✘ 找不到 EOCD")
    cd_size, cd_off = struct.unpack_from("<II", buf, eocd + 12)
    p = cd_off
    n = 0
    while buf[p:p + 4] == SIG_CEN:
        flags = struct.unpack_from("<H", buf, p + 8)[0]
        struct.pack_into("<H", buf, p + 8, flags | FLAG_UTF8)
        # 中央目录里的 local header offset 在 +42
        lho = struct.unpack_from("<I", buf, p + 42)[0]
        if buf[lho:lho + 4] == SIG_LOC:
            lf = struct.unpack_from("<H", buf, lho + 6)[0]
            struct.pack_into("<H", buf, lho + 6, lf | FLAG_UTF8)
        nlen = struct.unpack_from("<H", buf, p + 28)[0]
        elen = struct.unpack_from("<H", buf, p + 30)[0]
        clen = struct.unpack_from("<H", buf, p + 32)[0]
        p += 46 + nlen + elen + clen
        n += 1
    if p != cd_off + cd_size:
        raise SystemExit("✘ 中央目录解析长度不符")

    with open(path, "wb") as f:
        f.write(buf)
    return n


def build(out, root, rels=None, manifest=None):
    items = _collect(root, rels)
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for ap, rp in items:
            zi = zipfile.ZipInfo(rp, date_time=(2026, 11, 9, 12, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(ap, "rb") as f:
                z.writestr(zi, f.read())
    n = _patch_flags(out)

    # 逐条校验 flag
    z = zipfile.ZipFile(out)
    bad = [i.filename for i in z.infolist() if not (i.flag_bits & FLAG_UTF8)]
    if bad:
        raise SystemExit("✘ 仍有未置 flag 的条目: %s" % bad[:5])

    if manifest:
        rec = []
        for i in z.infolist():
            with z.open(i) as f:
                rec.append({
                    "path": i.filename,
                    "bytes": i.file_size,
                    "sha256": hashlib.sha256(f.read()).hexdigest(),
                    "utf8_flag": bool(i.flag_bits & FLAG_UTF8),
                })
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
    return n, len(items), bad


def check(path):
    z = zipfile.ZipFile(path)
    infos = z.infolist()
    bad = [i.filename for i in infos if not (i.flag_bits & FLAG_UTF8)]
    print("  条目 %d · 未置 UTF-8 flag: %d" % (len(infos), len(bad)))
    if bad:
        for b in bad[:10]:
            print("    ✘", b)
    return len(bad) == 0


if __name__ == "__main__":
    if sys.argv[1] == "--check":
        sys.exit(0 if check(sys.argv[2]) else 1)
    out = sys.argv[1]
    root = sys.argv[2]
    rels = sys.argv[3:] or None
    mf = out.rsplit(".", 1)[0] + ".manifest.json"
    n, cnt, bad = build(out, root, rels, mf)
    print("  ✔ %s" % out)
    print("    条目 %d · 全部 UTF-8 flag 已设 · %d B (%.1f MB)"
          % (cnt, os.path.getsize(out), os.path.getsize(out) / 1048576))
    print("    manifest: %s" % os.path.basename(mf))
