# 任务卡 xy071 · roadmap 状态回填（M5/M6 实况对齐，第一枪延续）

> 关联：xy-plan-008、xy-plan-009（G4 治理债延续）· 执行体：DSH · 验收：DSH · 状态：打回（CC 审核不通过） · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy071 · 状态版本：3
> 业务仓：无（文档收口，改 CCC 仓内 xy 计划文档）

## 目标
把 `docs/projects/xy/roadmap.md` 的 M5/M6 子项目状态回填到与实况一致（第一枪 xy070 已做 008 状态口径，但 roadmap 回填未落地——worktree 中间态丢失）：
1. M6 6.1「内容库 API」、6.2「工作流 API」：从「计划中」→「已完成（xy060/xy061 合入）」（这两卡已合入 xianyu main，见归档卡状态）。
2. M5 段：头部「状态：计划中（M6 全部卡验收后启动）」→「状态：部分执行（M5 主体已完成，5.1-5.3 功能卡待出）」，与 plans/008 当前口径一致；5.1-5.3 子项目保持「计划中」不动（功能卡确实未出）。
3. M6 头部「状态：执行中」保持（6.3/6.4 未完成）。

## 实现要求
用 Edit 精确改 roadmap.md 的 M5 头部状态行 + M6 6.1/6.2 状态字段 + 注记关联卡号；不改结构、不动其他段、不动 M7。

## 红线
1. 只改 `docs/projects/xy/roadmap.md` 一个文件；禁碰 plans/* 其他、禁碰 xianyu 业务仓。
2. 不启动 M7、不碰 Cookie。
3. M5 改「部分执行」须与 008 现口径一致（008 已是「部分执行」，勿改回）。

## 范围
- docs/projects/xy/roadmap.md

## 步骤
1. 读 roadmap M5/M6 段，确认现状（6.1/6.2 计划中、M5 计划中）。
2. M6 6.1 → 「已完成（xy060 合入）」；6.2 → 「已完成（xy061 合入）」。
3. M5 头部 → 「部分执行（M5 主体已完成，5.1-5.3 功能卡待出）」。
4. 自测：grep 确认新值在位、旧「计划中」对 6.1/6.2 不再命中；diff ≤6 行。
5. 写 .ccc-result.md（五段）交回写。

## 验收标准
1. `grep -n "6.1 内容库\|6.2 工作流" roadmap.md` 显示状态=已完成+合入注记。
2. `grep -n "M5" roadmap.md` 头部状态=部分执行+待出注记。
3. diff 仅 roadmap.md、共 ≤6 行。
4. 无 M7/Cookie/其他文件改动。

## 门禁
- card_gate 五项校验（必填字段齐全、状态=待分派、项目前缀 xy 在 registry、验收=DSH、范围路径在仓内存在）——本卡全部满足。

## 回写要求
- 回写区四问逐项填；教训沉淀若引用教训须注明 docs/notes 具体文件（机审 Q2 要求）。

## 人工批注
无批注。

## 回写区

## 0. 卡标题复述

任务卡 **xy071 · roadmap 状态回填（M5/M6 实况对齐，第一枪延续）**：

## 1. 探针输出

执行前诊断（worktree `/Users/fan/program/CCC-wt/xy071`，分支 `codex/xy071`，HEAD 基线 73eaa9111）：

| 探针 | 输出 | 结论 |
|---|---|---|
| `git status` / `git branch --show-current`（CCC-wt/xy071） | 分支 codex/xy071，HEAD=73eaa9111，仅未跟踪 .venv-hub | 目标分支就绪 |
| `grep -n "### M5" -A1` | L42 `- 状态：计划中（M6 全部卡验收后启动）` | M5 头部旧值在位 |
| `grep -n "6.1 内容库\|6.2 工作流"` | L55/L56 均为 `状态：计划中` | 6.1/6.2 旧值在位 |
| `git diff main --stat -- docs/projects/xy/roadmap.md` | 空（无差异） | 卡所述「roadmap 回填未落地」属实：`git log` 显示 main 上 xy071 提交（73eaa9111/53d430526）仅建卡文件、未改 roadmap.md；xy070 对 6.1/6.2 的「已完成」改动在 1df106338 merge 时被回退（--cc diff 确认） |
| `git -C /Users/fan/program/CCC status --short -- docs/dispatch/xy/xy071-roadmap-backfill.md` | 无输出 | 主仓卡文件未被改动（只读指针） |

探针结论：目标状态改动在 main/分支上均未落地，本卡需真实落地。范围文件位于 CCC 仓 worktree（任务卡「业务仓：无（文档收口，改 CCC 仓内 xy 计划文档）」），非 xianyu 业务仓。

## 2. 自测输出

自测命令（均在 `/Users/fan/program/CCC-wt/xy071`，相对 main 基线）：

| 验收项 | 命令 | 输出 | 退出码 | 结果 |
|---|---|---|---|---|
| 验收1 6.1/6.2 已完成+合入注记 | `grep -n "6.1 内容库\|6.2 工作流" docs/projects/xy/roadmap.md` | L55 `6.1 内容库 API · 状态：已完成（xy060 合入）`；L56 `6.2 工作流 API · 状态：已完成（xy061 合入）` | 0 | 通过 |
| 验收2 M5 头部部分执行+待出注记 | `grep -n "^### M5" -A1 docs/projects/xy/roadmap.md` | L42 `- 状态：部分执行（M5 主体已完成，5.1-5.3 功能卡待出）` | 0 | 通过 |
| 验收3 diff 仅 roadmap.md、共 ≤6 行 | `git diff main --numstat -- docs/projects/xy/roadmap.md` | `3 3 docs/projects/xy/roadmap.md`（1 文件，3 增 3 删 = 6 行） | 0 | 通过 |
| 自测 旧值不命中 6.1/6.2 | `grep -c "6.1 内容库 API · 状态：计划中\|6.2 工作流 API · 状态：计划中"` | `0`（无匹配，符合预期；grep 无匹配退出码 1，经 `|| echo` 捕获确认 0 命中） | 1(预期) | 通过 |
| M6 头部保持执行中 | `grep -n "^### M6" -A1` | L51 `- 状态：执行中` | 0 | 通过 |
| 5.1-5.3 保持计划中 | `grep -n "5\.[123] "` | L46/L47/L48 均为 `状态：计划中` | 0 | 通过 |
| M7/Cookie 未触碰 | `grep -n "M7\|Cookie"` | 仅原有文本行（L7/53/60/61/63/65/107），无改动 | 0 | 通过 |
| 无越界文件改动 | `git status --short` | 仅 ` M docs/projects/xy/roadmap.md`（+.venv-hub 未跟踪，未动） | 0 | 通过 |

完整 diff（`git diff docs/projects/xy/roadmap.md`）：3 行变更 = M5 头部状态行 + 6.1 状态行 + 6.2 状态行，无结构/其他段改动。

## 维护区

1. **方案同步**：[是] xy-plan-008/009 的 roadmap 状态回填，附本卡号 xy071 ——与 xy070（第一枪，008 口径）衔接，本次补上 roadmap 落地（6.1/6.2 已完成 + M5 部分执行，与 008 现「部分执行」口径一致）。
2. **教训沉淀**：[无] 本次仅路线图状态行回填，无新教训；roadmap 合入回退问题（第一枪 worktree 中间态丢失）为流程事实，已在本结果 探针输出 段记录，未引用 docs/notes 具体文件（无新增教训文件）。
3. **档案/README**：[否] 仅 roadmap 状态行，未改项目档案/README。
4. **线路图**：[否] roadmap 状态回填即线路图本体（本次改动的就是 roadmap.md），无新增规划。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：Q1 方案同步校验失败。方案关联卡「xy059、xy064、xy067、xy065、xy066、xy068、xy069、xy070；其余功能卡待出（xy059=html-preview CLI 已回写）」中不包含本卡 ID「xy071」
