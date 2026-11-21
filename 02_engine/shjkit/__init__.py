#!/usr/bin/env python3
"""shjkit —— 《伤寒论》多版本对照 · 公共地基引擎。

设计目标:**新增一个版本 = 写一份 spec.json + 提供转录件,不改引擎任何一行代码。**
这是多人并行分包的技术前提。

用法:
    python3 -m shjkit.pkgbuild <版本包目录>       # 跑一个版本包
    python3 -m shjkit.pkgnew   <目录> <版本名> <文件>  # 生成 spec 模板
    python3 -m shjkit.verify   <版本包目录>        # 校验交付件完整性
"""
__version__ = "1.0"
