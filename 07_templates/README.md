# 07_templates · 模板

## 注本派发（2026-11-22 新增）

电子本注本结构化用的整套东西。**打包装箱一条命令**：

```bash
python3 07_templates/注本派发/打包.py            # 预检，只报缺什么
python3 07_templates/注本派发/打包.py --apply    # 真打包到 30_dispatch/31_注释本/
```

| 文件 | 是什么 |
|---|---|
| `注本任务书_模板.md` | 任务书模板，`{{}}` 占位由打包脚本填。按 skill `TASK模板` 十三节写：执行方式与通道／判定类型与收益类别（V1–V4）／写隔离（只读处理）／目标与验收代号／禁止／回传命名／硬伤／降级 |
| `注本交付格式.md` | `notes.json`／`manifest.json` 字段定义，随包发给承接方 |
| `自检_注本.py` | 交付自检：条号越界／倒序／占位残留／标签残留／契约缺字段。硬伤一处即不合格 |
| `注本派发/分包表_20261122.csv` | 9 部电子本注本的分包账：id、侧、C5 编号、字数、rho、难度 |
| `注本派发/实测记录_20261122.md` | 我方对 B21／B7 的实测：短行占比、条次标记覆盖、串行问题 |
| `注本派发/打包.py` | 按分包表出包：转 UTF-8、生成骨架、取样例、填任务书、写 `PACK_VERSION.md`、打 zip、**把 `manifest.json` 写进包内**、生成外部 `.sha256` |

### 每包固定 8 条目

```
<包名>/任务书.md
<包名>/PACK_VERSION.md
<包名>/数据/<注本全文>.txt
<包名>/数据/骨架_<侧>_<N>条.json
<包名>/数据/样例_notes.json
<包名>/工具/自检_注本.py
<包名>/交付/交付格式.md
manifest.json          ← 包根，逐文件 sha256/bytes
```

发包前必跑（skill `scripts/pack_check.py`）：

```bash
python3 ~/.workbuddy/skills/classic-edition-collation/scripts/pack_check.py \
  <包>.zip --expect 任务书.md PACK_VERSION.md 数据/骨架_sh_398条.json \
  工具/自检_注本.py 交付/交付格式.md --forbid db state/
```

`RESULT: PASS` 才可发。它查五件事：ZIP 完整、manifest 与包内文件哈希逐条一致且无遗漏、必需文件在包、无 db/state、任务书引用路径不悬空。

## 版本判同

- `版本判同/`：任务书模板、交付格式模板、自检器

## 派发样例

- `dispatch_samples/`：注释本任务书 6 份（按书型）＋退回 prompt 2 份

入库。
