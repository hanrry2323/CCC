# 批B执行报告 · 文档 P2/P3 + 代码注释对齐（2026-09-04）

> 全程 `/Users/fan/program/CCC` 权威仓；零代码逻辑变更；未重启引擎；未改测试。
> 开工基线 `0625dbbfb` → 收尾 head `81e84eef0`（22 笔 commit，逐笔 push）。

## 交付核对（对指令清单）

### 文档 P2/P3 群（17 项）

| # | 文件 | 改动要点 | commit |
|---|------|---------|--------|
| 1 | README.md | :60-63 三服务→两服务（board-scheduler 标收敛进 engine）；:99 relay 行标退役 | `437cfec74` |
| 2 | CLAUDE.md | header 双真值统一为「环节②审核合入中枢」；:63-66 环节② 改「可替换调度插件（现役外脑）+ 后段 phase2 CC」 | `fb6c22fb4` |
| 3 | AGENTS.md | :96-97 合入一条龙改「phase2 默认自动；桌面端/口令为人工兜底插件」 | `81cdf238c` |
| 4 | SSOT.md | :12 版本→v0.71.0；:21 relay 行标退役 | `523666c6e` + `39c5869b7` |
| 5 | docs/roadmap.md | :3 版本；P1/P4/P5 + 现状 M1/M2/M4 改现役（3456）+ 退役标注 | `b625b9331` |
| 6 | docs/ENGINEERING-CANON.md | 原则 6 开发端改 2017 权威仓；原则 7 加「模型同源（3456/Code）已接受风险」现实注；决策档路径改「已清理」 | `c7e36b835` |
| 7 | docs/product/north-star-slice.md | 合入口径默认 phase2 自动+老板否决；单卡通道例外加注 | `0a674d553` |
| 8 | docs/product/machine-audit-flow.md | 两段式机审标「史」，改 phase2 一段式 | `bac24be7a` |
| 9 | docs/product/accept-board-sop.md | 文首加「人工兜底通道」标注 | `0d88c6995` |
| 10 | docs/product/hub-context-sop.md | :11,79 M1 口径改 2017 权威仓 | `fbd35bdab` |
| 11 | docs/product/card-hub-manual.md | :3 制卡中枢双真值统一；:88 交叉配对删（表已不存在） | `24578e93f` |
| 12 | docs/deploy/topology.md | 中枢 M1 职责改「可替换调度插件（现役外脑）；M1 只读看板（RETIRED-2026-08-22）」；三服务→两服务 | `725b57457` |
| 13 | docs/deploy/server-layout.md | 文首加「史（Hub/Desktop 期）」标注；现行以 2017 布局为准 | `725b57457` |
| 14 | references/board-task-schema.md | T<序号> 命名改 prefix 命名；角色定义去具体工具名（OpenCode/Trae/Codex）→ 绑定见 executors.json | `5e5dd2818` |
| 15 | docs/DOC-PROTOCOL.md | :46 T-mapping 死链删/标注（已核实文件不存在） | `ffbf994b3` |
| 16 | server/README.md | :3 两服务；结构图删 relay/ 行；版本 v0.71.0 | `523666c6e` |
| 17 | STARTUP-BRIEF.md 补刀 | 核查无残留「三服务/6100 现行/v0.70/OpenCode 默认」——6100/6102 两处为「已退役历史路径」正确标注，无需改 | — |

### 代码注释群（8 项 · 零行为变更）

| # | 文件 | 改动要点 | commit |
|---|------|---------|--------|
| 18 | server/engine/phase2.py | 模块头改「后段验收插件（现役绑定见 executors.json）→合入→部署」；错误消息内嵌通道改从 dsh_gateway 常量拼装（新增 import，仅文本来源） | `c3d8a7203` |
| 19 | server/engine/dsh_gateway.py | 模块头改「后段审核插件网关环境（现役经 M1 3456 中转，模型绑定走配置）」 | `c3d8a7203` |
| 20 | server/engine/dispatch.py | :45,63,324 管理席/验收席注释去矛盾；:14,81,405 opencode 示例改中性「executor」 | `7ef416ffe` |
| 21 | server/config/loader.py | :61-63 模型名注释改「模型绑定走 DSH_PROBE_MODEL/配置单源」 | `0584ba42c` |
| 22 | server/web/brain.py | 头注释改「出口由 config.env CCC_BRAIN_BASE_URL 决定」——**先核实实配**：config.env `CCC_BRAIN_DIRECT=1` + `CCC_BRAIN_BASE_URL` 空 → 当前直连；已注明两态 | `ffa2f9443` |
| 23 | server/engine/main.py | :1206,1180-1199,1324 机审信封 docstring 标注「仅 --audit 手动侧链；主链 phase2 已 worktree 退出机审」；:3986-3993 交叉配对段 + :2219-2238 MachineAuditPrompt 加「DEAD：待批E收敛删除」（本批不删） | `f483fa03e` |
| 24 | server/board/roles.py | :13-17 注释按前段/后段语义改写（校验行为不变） | `f12007bb5` |
| 25 | server/engine/card_gate.py | :2-5 注释后加「（TODO 批D：触发口径改按卡头 schema，去工具名依赖）」 | `28d0ece19` |

### 收尾

| 项 | commit |
|----|--------|
| SSOT relay 退役标注（拆分补） | `39c5869b7` |
| 文档尾部空白清理（`git diff --check` 清零） | `81e84eef0` |

## 一致性自查

- 版本号：VERSION=v0.71.0，SSOT/roadmap/server-README 全对齐 v0.71.0（批A 已改根 VERSION，批B 同步派生文档）。
- 服务数：全仓现行入口均为「两服务」（web-server + engine；board-scheduler 收敛）；CHANGELOG.md 与 `docs/archive/`、`docs/projects/*/plans/` 内的「三服务」为历史记录/方案，未改动。
- 模型通道：现行文档统一「M1 3456 → LiteLLM → Code」；6100/6102 均标注退役。
- 入口文档门禁：`python3 scripts/check-entry-docs.py` → [OK]（零硬编码 + 必需指针齐全）。

## 校验

- 8 个改动 py 文件 `py_compile` 全部通过（零行为变更，仅注释/docstring/错误文本来源）。
- `git diff --check` 无输出。
- 每笔 commit 后 ruff（`server/` lint）与 validate task cards 钩子通过。
- 引擎未重启（批B 无需重启）；未改测试。

## 红线合规

- 未改 `executors.json`（批C 范围）；未改卡文件；未改任何运行面。
- 未触碰代码逻辑；phase2.py 仅新增 `ANTHROPIC_BASE_URL/ANTHROPIC_MODEL` 导入用于错误文本拼装。
- 禁 `git add -A`——全部按文件分组显式 add。
