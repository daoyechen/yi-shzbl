# 08_tools · 工具

| 脚本 | 干什么 |
|---|---|
| `build_index.py` | 双站编译器：`90_out/gujia`（只原文）＋ `90_out/zhushi`（原文＋注文）＋ 落地页 |

## 编译

```bash
python3 08_tools/build_index.py --check   # 只检查；有变化 exit 2
python3 08_tools/build_index.py           # 有变化才编译
python3 08_tools/build_index.py --force   # 强制重编
python3 08_tools/build_index.py --site zhushi --force   # 只重编一个站
```

`<站>/data/manifest.json` 是台账（条数、版本数、review 数、异文条数、源/产物 sha256；zhushi 另有 `l2` 段记注文 sha 与注本数）。
**是否最新以 manifest 与实际文件比对为准，不看时间戳。**

注文条号越界、注本下标失效会让编译直接失败——挂着错条的注比少几部注本坏得多。

## JG 全链路（顺序不可换）

```bash
cd 02_engine
python3 -m shjkit.assemble <5 个版本包> --out ../50_data/52_l1_assembly/jingui --骨架 jingui
python3 apply_returns_r1.py --out ...   # H01/H02/M01
python3 apply_returns_r2.py --out ...   # L01/L02/M02（含方名归并、PUA 回填）
python3 clean_viewer_junk.py --out ...  # 剔网页残留（必跑）
python3 register_jg_gap.py  --out ...   # 登记 indep 缺篇（幂等）
python3 regenerate_reports.py --out ... # 重出 01/02/04/08
cd .. && python3 08_tools/build_index.py
```

`assemble` 从版本包重新取数，会把回传结果覆盖回去，所以**注入必须排在它之后**（硬规矩 13）。

## 发布

`90_out/index.html` 与 `90_out/*/data/` **必须同一次提交推**，只推一个会报「Failed to fetch」（缓存错配，不是代码坏）。必须走 http(s)，`file://` 下 fetch 被拒。详见 `docs/前端约定.md` §五。

## 路径常量（2026-11-21 重组时改过）

改目录结构时，这五个文件里的常量必须同步改，否则引擎与编译器当场断：

| 文件 | 关键常量 |
|---|---|
| `02_engine/shjkit/skeleton.py` | `FOUND`（项目根）、`REG_PATH`（`01_skeleton/`） |
| `02_engine/shjkit/assemble.py` | `_ROOT`、宋本转录件候选路径（`05_texts/版本正文`） |
| `01_skeleton/骨架注册表.json` | 3 条 `路径` 字段 |
| `02_engine/h02_proofs.py` 等 6 个 | `00_公共地基/xxx` 已改新顶层名 |
| `build_index.py`（本目录） | `ENGINE`／`L2`／`SITE_DIR`／`LANDING`／`SH_SRC`／`JG_SRC` |

旧→新对照见 `50_data/PATH_MAP.md`。
