# 08_tools · 工具

| 脚本 | 干什么 |
|---|---|
| `build_index.py` | 双站编译器：`90_out/gujia`（只原文）＋ `90_out/zhushi`（原文＋注文）＋ 落地页 |

## 与核心引擎分开的原因（2026-11-22 确认）

`02_engine/` 管核心解析、组装和回传注入实现；本目录管项目级编译与操作入口。继续分开，以便区分算法/源数据处理变更与展示编排变更，不为了目录数量而物理合并。

`07_templates/注本派发/打包.py` 具有执行入口职责，但仍依赖同目录分包表和固定模板路径。只登记为未来可参数化的入口，本轮不搬、不改配置、不运行迁移。

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

## 路径约定

当前主要入口按项目根目录定位；辅助脚本可能残留旧路径，运行前逐项核实，不推定全链输入已齐。修改目录结构时，先扫描 `02_engine/`、`08_tools/`、注册表和模板中的硬编码路径，再搬目录；历史日志和迁移对照表保留旧路径，不作为当前命令。

| 入口 | 当前路径 |
|---|---|
| 引擎 | `02_engine/` |
| 骨架注册表 | `01_skeleton/骨架注册表.json` |
| L1 总装 | `50_data/52_l1_assembly/` |
| L2 注本 | `50_data/51_notes/` |
| 物料台账 | `10_material/15_catalog/` |
| 网页输出 | `90_out/` |

旧→新对照仅用于解释历史迁移，见 `50_data/PATH_MAP.md`。
