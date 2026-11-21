#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把目录打成干净的 zip（中文名不乱码、解压后有写权限）。

    python3 mkzip.py 输出.zip 源目录 [--skip 文件名 ...]

规则：
  - 文件按 0o644、目录按 0o755 设 external_attr，避免解压后只读
  - 文件名强制 UTF-8 标志位（0x800），Windows 资源管理器与 macOS 均可正确显示
  - 默认跳过 .DS_Store / __pycache__ / *.pyc
"""
import os
import sys
import zipfile

SKIP_DIRS = {"__pycache__", ".git", ".idea", ".vscode"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
SKIP_SUFFIX = (".pyc",)


def add_tree(zf, root, skip_names):
    root = os.path.abspath(root)
    base = os.path.basename(root)
    count = 0
    total = 0

    def put_dir(rel):
        info = zipfile.ZipInfo(rel.rstrip("/") + "/")
        info.external_attr = (0o40755 << 16) | 0x10
        info.flag_bits |= 0x800
        zf.writestr(info, b"")

    put_dir(base)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        filenames = sorted(filenames)
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir != ".":
            put_dir(os.path.join(base, rel_dir).replace(os.sep, "/"))
        for fn in filenames:
            if fn in SKIP_NAMES or fn.endswith(SKIP_SUFFIX) or fn in skip_names:
                continue
            full = os.path.join(dirpath, fn)
            arc = os.path.join(base, os.path.relpath(full, root)).replace(os.sep, "/")
            info = zipfile.ZipInfo(arc)
            info.external_attr = (0o100644 << 16) & 0xFFFFFFFF
            info.flag_bits |= 0x800
            info.date_time = (2026, 11, 17, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(full, "rb") as f:
                data = f.read()
            zf.writestr(info, data)
            count += 1
            total += len(data)
    return count, total


def main():
    args = sys.argv[1:]
    skip = set()
    if "--skip" in args:
        i = args.index("--skip")
        skip = set(args[i + 1:])
        args = args[:i]
    if len(args) != 2:
        print(__doc__)
        return 2
    out, src = args
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        n, raw = add_tree(zf, src, skip)
    size = os.path.getsize(out)
    print(f"✓ {out}\n  {n} 个文件，原始 {raw/1048576:.1f} MB → 压缩后 {size/1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
