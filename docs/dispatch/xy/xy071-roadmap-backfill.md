# 任务卡 xy071 · roadmap 状态回填（M5/M6 实况对齐，第一枪延续）

> 关联：xy-plan-008、xy-plan-009（G4 治理债延续）· 执行体：DSH · 验收：DSH · 状态：已关闭 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy071 · 状态版本：6
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

任务卡 **xy071 · roadmap 状态回填（M5/M6 实况对齐，第一枪延续）**：将 CCC 仓 `docs/projects/xy/roadmap.md` 的 M5/M6 子项目状态回填到与实况一致——(1) M6 6.1 内容库 API →「已完成（xy060 合入）」、6.2 工作流 API →「已完成（xy061 合入）」；(2) M5 头部 →「部分执行（M5 主体已完成，5.1-5.3 功能卡待出）」（与 plans/008 现口径一致，5.1-5.3 子项保持计划中）；(3) M6 头部「执行中」保持。红线：只改 roadmap.md 一个文件、diff ≤6 行、不动 plans/其他文件、不动 M7/Cookie。

## 1. 探针输出

执行前诊断（范围文件在 CCC 仓，卡声明「业务仓：无（文档收口，改 CCC 仓内 xy 计划文档）」）：

| 探针 | 输出 | 结论 |
|---|---|---|
| 授权 worktree 仓库身份 | `cat .git` → `gitdir: /Users/fan/program/apps/xianyu/.git/worktrees/xy071`；`git remote -v` → `origin git@github.com:hanrry2323/xianyu.git`；`find docs -iname "*roadmap*"` 无结果 | 授权 worktree `/Users/fan/program/apps/.ccc-wt/xy/xy071` 是 **xianyu 业务仓** checkout，不含卡范围文件；按红线禁碰业务仓，未在其内做任何 git 操作 |
| 卡范围文件实况 | `/Users/fan/program/CCC/docs/projects/xy/roadmap.md` 存在（CCC 仓），其卡 worktree `/Users/fan/program/CCC-wt/xy071`（分支 `codex/xy071`，HEAD `080cf2b68`）已含回填提交 | 回填改动已在卡分支就位、已推送；main 上 roadmap.md 仍为旧值（6.1/6.2 计划中），待环节②合入 |
| 提交内容 | `git show 080cf2b68 --stat` → 仅 `docs/projects/xy/roadmap.md`，3 增 3 删 = 6 行；完整 diff 恰为 M5 头部行 + 6.1 + 6.2 三行 | 与本卡步骤 2/3 完全一致 |
| 分支/远程 | `git rev-parse HEAD` = `080cf2b6895cf85733e1d334635639137a85bf6d`；`git ls-remote --heads origin codex/xy071` = 同一值 | 已推送，无落后 |
| 上轮打回根因 | main `97388c6b5 fix(xy008): 关联卡清单补 xy071` 已将 plans/008 关联卡补入 xy071，008 状态=部分执行 | 机审 Q1 前置条件已消解，008 口径与本卡 M5 改动一致 |
| 主仓卡文件 | `git -C /Users/fan/program/CCC status --short -- docs/dispatch/xy/xy071-roadmap-backfill.md` 无输出 | 卡文件未被改动（只读指针） |

探针结论：本卡代码工作已完成（commit 080cf2b68，分支 codex/xy071，已推送），全量验收自测通过；无需新增提交——在授权 worktree（xianyu 业务仓）内提交即违反卡红线「禁碰 xianyu 业务仓」。本结果如实记录 worktree 仓库身份与范围文件位置的偏差，改动证据以 CCC 仓卡分支为准。

## 2. 自测输出

自测命令（均在 `/Users/fan/program/CCC-wt/xy071`，CCC 仓）：

| 验收项 | 命令 | 输出 | 退出码 | 结果 |
|---|---|---|---|---|
| 验收1 6.1/6.2 已完成+合入注记 | `grep -n "6\.1 内容库\|6\.2 工作流" docs/projects/xy/roadmap.md` | L55 `6.1 内容库 API · 状态：已完成（xy060 合入） · 方案：xy-plan-009`；L56 `6.2 工作流 API · 状态：已完成（xy061 合入） · 方案：xy-plan-009` | 0 | 通过 |
| 验收2 M5 头部部分执行+待出注记 | `grep -n "^### M5" -A1 docs/projects/xy/roadmap.md` | L42 `- 状态：部分执行（M5 主体已完成，5.1-5.3 功能卡待出）` | 0 | 通过 |
| 验收3 diff 仅 roadmap.md、共 ≤6 行 | `git diff main --numstat -- docs/projects/xy/roadmap.md` | `3 3 docs/projects/xy/roadmap.md`（1 文件、3 增 3 删=6 行）；`git diff <merge-base> HEAD --name-status` 仅 `M docs/projects/xy/roadmap.md` | 0 | 通过 |
| 自测 旧值不命中 6.1/6.2 | grep 6.1/6.2 行内「状态：计划中」 | 0 命中（无匹配，退出码 1 经 `|| echo` 捕获，符合预期） | 1(预期) | 通过 |
| M6 头部保持执行中 | `grep -n "^### M6" -A1` | L51 `- 状态：执行中` | 0 | 通过 |
| 5.1-5.3 保持计划中 | `grep -n "5\.[123] "` | L46/47/48 均为 `状态：计划中` | 0 | 通过 |
| 验收4 无 M7/Cookie 改动 | `git diff main -- docs/projects/xy/roadmap.md \| grep -E "^[+-]" \| grep -iE "M7\|cookie"` | `NONE`（diff 增删行均不涉及 M7/Cookie；M6 描述上下文行含「M7 之前」为原有文本未改） | 0 | 通过 |
| 无越界文件改动 | `git status --short`（CCC-wt/xy071） | 仅 `?? .venv-hub`（未跟踪、未动） | 0 | 通过 |

完整 diff（`git diff main -- docs/projects/xy/roadmap.md`）：3 行变更 = M5 头部状态行 + 6.1 状态行 + 6.2 状态行，无结构/其他段改动。

## 维护区

1. **方案同步**：[是] 本卡为 xy-plan-008/009 的 roadmap 状态回填落地：M5 头部「部分执行（M5 主体已完成，5.1-5.3 功能卡待出）」与 plans/008 现「状态：部分执行 + 进度 2/2」口径一致；plans/008 关联卡已含本卡 xy071（main commit 97388c6b5 补齐，机审 Q1 前置已消解）；6.1/6.2「已完成（xy060/xy061 合入）」与 plans/009 关联卡（含 xy060、xy061）一致。
2. **教训沉淀**：[无] 本次仅路线图三行状态回填，无新教训；上轮已记录流程事实（第一枪 worktree 中间态丢失、本卡 worktree 曾与范围文件仓库错位），未引用 docs/notes 具体文件（无新增教训文件）。
3. **档案/README**：[否] 仅 roadmap.md 状态行，未改项目档案/README。
4. **线路图**：[否] roadmap 状态回填即线路图本体（改动对象就是 roadmap.md），无新增规划。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：通过
- 理由：CC 审核通过，自动合入完成
