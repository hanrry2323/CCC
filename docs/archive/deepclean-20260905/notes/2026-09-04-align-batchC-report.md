# 批C执行报告 · 配置绑定值对齐（插座注册表 + 脚本路径）2026-09-04

> 指令：`/Users/fan/.ccc/instructions/2026-09-04-align-batchC.md`
> 执行窗口：2017 产线修复窗口（Claude CLI）· 全程 `/Users/fan/program/CCC`（权威仓）
> 性质：配置/脚本文本对齐；**零 Python 代码逻辑改动**；未重启引擎
> 开工基线 `ec2faac90` → 收尾 head `eaf4c0333`（2 笔 commit，逐笔 push）
> 对齐基准：插座理念（注册表 = 插座绑定单源）——管理/总调度 = 可替换调度插件（现役外脑 Z Code，桌面端休眠）；前段执行（拆解/开发/前置机审，待分派→已回写前）= DSH；后段执行（已回写后：审核/验收/合入/提交/部署）= Claude Code CLI（主链 phase2 自动）

## 一、改动清单（对指令逐项）

### 1. server/config/executors.json（生产注册表 · 文本字段）
- 顶层 `description` 改写为「插座绑定单源 · 2026-09-04 对齐」口径，明确三职责段（管理/总调度=可替换调度插件；前段=DSH；后段=CC CLI 主链 phase2 自动）+「一切绑定皆插件可换，换绑定只改本文件」+ 命令绝对路径保留说明（Engine Popen cwd 语义，2026-08-29 实证）。
- 管理席：`当前绑定`「桌面端总调度（2026-08-27）」→「可替换调度插件（现役外脑 Z Code；桌面端休眠）」；`备注`「出卡/裁决；不执行；不验收」保留。
- 验收席：`当前绑定`「自动化值班组件 + 桌面端终审（2026-08-27）」→「后段 CC CLI（主链 phase2 自动）」；`备注`改「后段验收契约 v2（主仓卡只读+log_dir 工件→verdict 工件）；本行命令为 --audit 手动兜底链（历史绑定 DSH，批E 换 claude wrapper）；主链 phase2 不经本行」；**`命令` 行未动**（`/Users/fan/program/CCC/scripts/dsh-auditor.sh`，换 wrapper 属批E 原子变更）。
- 维护执行体：`备注`补「前段执行含前置机审（DSH 自检属前段职责）」。
- 只读取证行：`参数模板`「/Users/fan/.dsh/run-executor.sh {card_path}」→「$HOME/.dsh/run-executor.sh {card_path}」；`备注`同步 `$HOME` 口径。

> 注：该文件被 `.gitignore:25` 忽略（运行期配置），本批按对齐需要以 `git add --force` 强制纳入（gitignore 规则未改）。

### 2. server/config/executors.example.json
- `description` 与生产完全同步（2026-09-04 对齐口径）。
- 结构/字段与生产一致（五角色 schema 不变）。
- 相对/绝对路径口径统一：开发执行体 `当前绑定` 由「执行会话 / 自动化值班组件（2026-08-27 三层分工）」统一为「DSH」（与生产同行同值）；命令保留 example 相对路径 `scripts/dsh-*.sh`；只读取证参数模板同生产 `$HOME/.dsh/run-executor.sh {card_path}`。
- 「桌面端总调度」「CLI 为核心开发执行者」等旧表述随 description/绑定文本清除。

### 3. scripts/dsh-auditor.sh
- 新增 `_CCC_ROOT="$(cd "$_SELF/.." && pwd -P)"`（复用既有 `_SELF` 相对定位）。
- `sys.path.insert(0, "/Users/fan/program/CCC")` → `sys.path.insert(0, "$_CCC_ROOT")`（:86）。
- `_TE_CFG` 默认 `config.env` 绝对路径 → `$_CCC_ROOT/server/config/config.env`（:115）。
- `test-evidence.sh` 绝对路径 → `"$_CCC_ROOT/scripts/test-evidence.sh"`（:127）。

### 4. scripts/dsh-executor.sh
- 同样新增 `_CCC_ROOT`。
- `_TE_CFG` 默认 `config.env` → `$_CCC_ROOT/server/config/config.env`（:117）。
- `test-evidence.sh` 绝对路径 → `"$_CCC_ROOT/scripts/test-evidence.sh"`（:136）。
- 双仓提示卡相对路径 `${CARD_PATH#/Users/fan/program/CCC/}` → `${CARD_PATH#$_CCC_ROOT/}`（:102；`_CCC_ROOT` 已定义且规范化，无尾斜杠，实测前缀剥除正确）。

### 5. scripts/audit-merge-agent.sh / scripts/spot-check.sh
- `audit-merge-agent.sh:8`：`cd /Users/fan/program/CCC` → `cd "$(dirname "$0")/.."`。
- `spot-check.sh:79`：`config.env` 默认绝对路径 → `$PROJECT_ROOT/server/config/config.env`（PROJECT_ROOT 为脚本既有相对定位）。

### 6. 测试同步（仅文本断言 · 断言行为不放宽）
- 改前 `grep` 结果：`test_skeleton.py` 对注册表无绑定文本断言（DSH 契约断言的是 `scripts/dsh-` 命令/位置模板/注入提示，不锁绑定文本）→ 不动。
- `test_engine_dispatch.py` 三处锁旧绑定文本 → 同步为新文本：
  - `assert cli.binding == "执行会话 / 自动化值班组件（2026-08-27 三层分工）"` → `"DSH"`（example 开发执行体绑定已统一为 DSH）。
  - `cli_entry_for_binding("自动化值班组件 + 桌面端终审（2026-08-27）")` → `("后段 CC CLI（主链 phase2 自动）")`。
  - `{e.binding for e in acc_rows} == {"后段 CC CLI（主链 phase2 自动）"}`。
  - 命令断言（`scripts/dsh-executor.sh` / `scripts/dsh-auditor.sh`）、角色、分类、注入提示等断言**全部保留**（行为未放宽）。

## 二、commit 列表（2 笔，均已 push origin main）

| commit | 说明 |
|--------|------|
| `83e5ae519` | chore(align): align executor registry bindings with plugin model —— executors.json(+example) description/binding/note 对齐 + 只读取证 `$HOME` 参数模板 + test_engine_dispatch 断言文本同步 |
| `eaf4c0333` | chore(align): replace hardcoded repo paths with relative _SELF anchors —— dsh-auditor/executor/audit-merge-agent/spot-check 四脚本绝对路径 → 相对仓库根 |

## 三、验证与边界

- `python3 -c "import json;json.load(...)"`：两个注册表均 JSON 通过；五角色结构字段一致（脚本核验）。
- 验收席 `命令` 行本批未动（生产 `/Users/fan/program/CCC/scripts/dsh-auditor.sh` 保持，独立脚本核验）。
- 定向测试 `pytest server/tests/test_skeleton.py server/tests/test_engine_dispatch.py -q` → **64 passed（全绿）**。
- `git diff --check` 无尾随空白；四个脚本 `bash -n` 语法通过。
- `grep -n '/Users/fan/program/CCC'` 于四脚本 → 0 命中（绝对路径全部消除，仅剩 `$_CCC_ROOT`/`$PROJECT_ROOT` 相对锚点）。
- 仅改 `*.py` = `server/tests/test_engine_dispatch.py`（测试断言文本），无引擎/运行逻辑文件改动；未重启引擎。
- 未改卡文件；未改运行面/密钥；逐笔显式 `git add`，无 `git add -A`。
- 遗留：`executors.json` 本为 gitignored 运行配置，本批强制纳入对齐；后续批E 换验收席 wrapper 时同路径继续原子变更。

## 收尾

- 最终 head：`eaf4c0333`（本报告 commit 前 HEAD；报告提交后 head 见末尾一行）。
