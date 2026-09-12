# 任务卡 xy070 · 状态口径回填（008/roadmap 计划状态修正）

> 关联：xy-plan-008（G4 治理债）· 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy070 · 状态版本：7
> 业务仓：无（文档收口，改 CCC 仓内 xy 计划文档）

## 目标
修正 xy 两份计划文档的口径矛盾，让看板/方案状态如实反映进度：
1. `docs/projects/xy/plans/008-high-expression-v2.md`：头部「进度：2/2 (100%)」与「状态：部分执行」矛盾——**回填为「状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出）」**，进度行与描述一致。
2. `docs/projects/xy/roadmap.md` M6 段：6.1「内容库 API」、6.2「工作流 API」实际已合入（xy060/xy061 已交付），**从「计划中」回填为「已完成」**并注记关联卡号。

## 实现要求
用文本编辑（Edit）精确改两处状态字段，不改结构/其他内容；改后自测（grep 确认新值在位、旧值消失）。

## 红线
1. 只改上述两文件的**状态/**进度字段行**，不重构段落、不改其他项目、不动 xianyu 业务仓。
2. 不启动 M7、不触碰 Cookie 外部账号、不发布。
3. 若发现 roadmap/008 既有内容与实况还有冲突，如实记进回执别硬改。

## 范围
- docs/projects/xy/plans/008-high-expression-v2.md
- docs/projects/xy/roadmap.md

## 步骤
1. 读两个文件相关段，确认现状。
2. `plans/008`：进度行旁加注「M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径」；头部「状态」保持「部分执行」但补一句注记，消除「100% 但部分执行」的矛盾。
3. `roadmap.md` M6：6.1/6.2 状态改「已完成」，注记「（xy060/xy061 合入）」。
4. 自测：grep 新状态再位、旧「计划中」对 6.1/6.2 不再命中；plans008 无「进度 2/2 (100%)」无解释的孤立行。
5. 写 .ccc-result.md（五段）交回写。

## 验收标准
1. `grep "6.1 内容库" roadmap.md` 显示状态=已完成（xy060 注记）；6.2 同。
2. `grep "进度：2/2" plans/008` 所在行有「M5 主体完成…」注记，不再是孤立矛盾行。
3. diff 仅两文件、共 ≤15 行改动（含加注行）。
4. 无 M7/Cookie/业务仓改动。

## 门禁
- card_gate 五项校验（必填字段齐全、状态=待分派、项目前缀 xy 在 registry、验收=Claude Code（phase2 机审）、范围两路径在仓内存在）——本卡全部满足。

## 回写要求
- 回写区四问（方案同步/教训沉淀/档案README/线路图）逐项填。

## 人工批注
无批注。

## 回写区

## 0. 卡标题复述

任务卡 xy070「状态口径回填（008/roadmap 计划状态修正）」：修正 `docs/projects/xy/plans/008-high-expression-v2.md` 头部「进度：2/2 (100%)」与「状态：部分执行」的口径矛盾，回填为「状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出）」并在进度行加注「M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径」；将 `docs/projects/xy/roadmap.md` M6 段 6.1「内容库 API」、6.2「工作流 API」从「计划中」回填为「已完成」并注记 xy060/xy061 合入。人工批注：无批注（占位）。实现范围仅上述两文件的状态字段行：不改结构/其他内容/其他项目、不动 xianyu 业务仓、不启动 M7、不触碰 Cookie 外部账号、不发布。

## 1. 探针输出

- **派发目录与目标仓不匹配（实测复核，延续前轮结论）**：卡范围两路径属 CCC 仓（origin=git@github.com:hanrry2323/CCC.git）；wrapper 派发的工作目录 `/Users/fan/program/apps/.ccc-wt/xy/xy070` 实为 **xianyu 业务仓** worktree（origin=git@github.com:hanrry2323/xianyu.git，branch codex/xy070-state-backfill），docs/ 下无 projects/xy、无卡白名单文件。判定派发目录系误指：按卡红线「不动 xianyu 业务仓」在 CCC worktree `/Users/fan/program/CCC-wt/xy070`（branch codex/xy070）执行核验；xianyu 业务仓零 git 改动（git status 仅既有 untracked .venv）。
- **打回原因核验（本轮关键前置）**：卡内机审区「结论：不通过——Q1 声明方案同步[是]，但卡头『关联』未包含有效方案编号（如 prefix-plan-NNN）」。引擎已在前轮修复分支补卡头 `关联：xy-plan-008`（commit 3c37c3fe6，仅改卡文件 1 行），本轮 Q1[是] 的卡头前提成立。
- **现状确认（前轮实现 commit 24f24845d 已就位、本轮全量 diff 复测成立）**：008 头部「状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出）」、进度行「2/2 (100%) —— M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径」；roadmap M6 6.1/6.2 均为「已完成（xy060/xy061 合入）」。
- **红线 3 残余口径（超出本卡范围，未改动，记回执转治理）**：`roadmap.md:42` M5 里程碑仍为「计划中（M6 全部卡验收后启动）」，与 008「部分执行（M5 主体完成）」不一致；且 M6 尚未全验收（6.3/6.4 仍计划中）。属同族口径债，超出本卡两处字段白名单与验收标准「diff ≤15 行」约束，如实记入回执未硬改。
- 交付佐证：`docs/archive/ccc-tasks/xy/xy060-content-library-api.md`、`xy061-m6-2-workflow-api-verify.md` 卡头均「状态：已关闭」，支撑「已完成（xy060/xy061 合入）」注记。

## 2. 自测输出

```
$ cd /Users/fan/program/CCC-wt/xy070
$ grep -n "6.1 内容库\|6.2 工作流" docs/projects/xy/roadmap.md
55:  - 6.1 内容库 API · 状态：已完成（xy060 合入） · 方案：xy-plan-009
56:  - 6.2 工作流 API · 状态：已完成（xy061 合入） · 方案：xy-plan-009
$ grep -n "进度：2/2" docs/projects/xy/plans/008-high-expression-v2.md
8:> 进度：2/2 (100%) —— M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径
$ grep -nE "进度：2/2 \(100%\)$" docs/projects/xy/plans/008-high-expression-v2.md   # 孤立矛盾行：无输出 ✓
$ git show 24f24845d --stat --oneline
24f24845d feat(xy070): 状态口径回填——008 头部/进度加 M5 注记消除 100% vs 部分执行矛盾，roadmap M6 6.1/6.2 改已完成（xy060/xy061 合入）
 docs/projects/xy/plans/008-high-expression-v2.md | 4 ++--
 docs/projects/xy/roadmap.md                      | 4 ++--
 2 files changed, 4 insertions(+), 4 deletions(-)
$ git status --short   # 工作树干净：仅 ?? .venv-hub（未动）
$ git ls-remote --heads origin codex/xy070
3c37c3fe65d32ae0a63d42de1eaf6a814d46a36c        refs/heads/codex/xy070   # 与本地 tip 一致，已推送
```

验收标准逐条：① 6.1/6.2 状态=已完成+（xy060/xy061 合入）注记 ✓；② 进度行含「M5 主体已完成…」注记、孤立矛盾行消除 ✓；③ diff 仅两文件共 4 行（≤15）✓；④ 无 M7/Cookie/业务仓改动 ✓（xianyu worktree 零 git 改动）。退出码：上述 grep 命中命令 0、无命中命令 1（预期）、git 命令 0。

## 维护区

1. **方案同步**：[是] 008 头部状态回填 + 进度行加注（M5 主体完成、2/2 为子项口径），消除「100% vs 部分执行」矛盾；卡头关联 xy-plan-008 已就位（引擎 3c37c3fe6）。
2. **教训沉淀**：[有] 机审打回教训——维护区 Q1 声明[是] 时卡头「关联」必须含有效方案编号；本轮已核验前置成立并在回执如实补记。
3. **档案/README**：[否] 未动架构/接口/README，仅状态字段行。
4. **线路图**：[否] roadmap 6.1/6.2 状态回填即线路图本体更新，无新增规划。

## 机审区

- 审核方：Claude Code（phase2 自动）
- 结论：不通过
- 理由：维护区未完成：Q1 方案同步校验失败。方案 xy-plan-008 状态为「部分执行（M5 主体完成，5.1-5.3 功能卡待出）」（须为部分执行/已完成）；方案关联卡「xy059、xy064、xy067、xy065、xy066、xy068、xy069；其余功能卡待出（xy059=html-preview CLI 已回写）」中不包含本卡 ID「xy070」；Q2 声明了有教训沉淀[有]，但说明中未引用任何 docs/notes/*.md 或 lessons.md 文件
