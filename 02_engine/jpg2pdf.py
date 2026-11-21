#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简 JPEG->PDF 合成器：JPEG 以 DCTDecode 原样嵌入，不做二次编码。

用法: python3 jpg2pdf.py 输出.pdf 页码 图片1.jpg 图片2.jpg ...
      python3 jpg2pdf.py 输出.pdf 150 目录/   # 目录内按文件名排序
"""
import glob
import os
import struct
import sys


def jpeg_size(data):
    """返回 (宽, 高)。解析 SOF0..SOF3/SOF5..SOF7/SOF9..SOF11 标记。"""
    i = 2
    n = len(data)
    while i < n - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        m = data[i + 1]
        if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7 or m == 0x01:
            i += 2
            continue
        seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + seglen
    raise ValueError("找不到 SOF 标记")


def build(pdf_path, dpi, jpgs):
    objs = []           # 每项为 bytes（不含 obj 头尾）
    page_ids = []
    # 1 catalog, 2 pages tree 占位
    objs.append(None)   # 1
    objs.append(None)   # 2

    for jf in jpgs:
        data = open(jf, "rb").read()
        w, h = jpeg_size(data)
        # 图片对象
        img_id = len(objs) + 1
        hdr = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
               f"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /DCTDecode "
               f"/Length {len(data)} >>\nstream\n").encode("ascii")
        objs.append(hdr + data + b"\nendstream")

        # 内容流
        wpt = w * 72.0 / dpi
        hpt = h * 72.0 / dpi
        content = f"q {wpt:.2f} 0 0 {hpt:.2f} 0 0 cm /Im0 Do Q".encode("ascii")
        cont_id = len(objs) + 1
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")

        page_id = len(objs) + 1
        page = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {wpt:.2f} {hpt:.2f}] "
                f"/Resources << /XObject << /Im0 {img_id} 0 R >> /ProcSet [/PDF /ImageB] >> "
                f"/Contents {cont_id} 0 R >>").encode("ascii")
        objs.append(page)
        page_ids.append(page_id)

    kids = " ".join(f"{p} 0 R" for p in page_ids)
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = (f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>").encode("ascii")

    # 写文件
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % idx + body + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objs) + 1
    out += b"xref\n0 %d\n" % n
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (n, xref_pos))
    open(pdf_path, "wb").write(out)
    print(f"✓ {pdf_path}  {len(page_ids)} 页  {len(out)/1048576:.1f} MB")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    out = sys.argv[1]
    dpi = float(sys.argv[2])
    args = sys.argv[3:]
    if len(args) == 1 and os.path.isdir(args[0]):
        files = sorted(glob.glob(os.path.join(args[0], "*.jpg")))
    else:
        files = args
    build(out, dpi, files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
