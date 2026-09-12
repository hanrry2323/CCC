# 任务卡 xy070 · 状态口径回填（008/roadmap 计划状态修正）

> 关联：G4 治理债（L1-D xy 盘点 §未闭环）· 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：xy · 日期：2026-09-13 · 版本：xy070 · 状态版本：2
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

任务卡 xy070「状态口径回填（008/roadmap 计划状态修正）」：修正 `docs/projects/xy/plans/008-high-expression-v2.md` 头部「进度：2/2 (100%)」与「状态：部分执行」的口径矛盾，回填为「状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出）」并在进度行加注；将 `docs/projects/xy/roadmap.md` M6 段 6.1「内容库 API」、6.2「工作流 API」从「计划中」回填为「已完成」并注记 xy060/xy061 合入。人工批注：无批注（占位）。

## 1. 探针输出

- **派发目录与目标仓不匹配（重要）**：卡范围两路径属 **CCC 仓**（origin=git@github.com:hanrry2323/CCC.git），引擎预置 worktree `/Users/fan/program/CCC-wt/xy070`（branch `codex/xy070`，首提交 0cb53741a 即卡文件）。wrapper 派发的工作目录 `/Users/fan/program/apps/.ccc-wt/xy/xy070` 实为 **xianyu 业务仓** worktree（branch `codex/xy070-state-backfill`，本地分支、无 origin 镜像），glob 全树无白名单文件；卡红线明令「不动 xianyu 业务仓」。判定派发目录系误指，实际实现严格按卡范围在 CCC worktree `/Users/fan/program/CCC-wt/xy070` 执行；xianyu 业务仓未做任何 git 改动。
- 现状确认：008 头部「状态：部分执行」与「进度：2/2 (100%)」矛盾成立；roadmap M6 6.1/6.2 均为「计划中」。
- 交付佐证：`docs/archive/ccc-tasks/xy/xy060-content-library-api.md`、`xy061-m6-2-workflow-api-verify.md` 卡头均「状态：已关闭」，支撑「已完成（xy060/xy061 合入）」注记。

## 2. 自测输出

```
$ cd /Users/fan/program/CCC-wt/xy070
$ grep -n "6.1 内容库\|6.2 工作流" docs/projects/xy/roadmap.md
55:  - 6.1 内容库 API · 状态：已完成（xy060 合入） · 方案：xy-plan-009
56:  - 6.2 工作流 API · 状态：已完成（xy061 合入） · 方案：xy-plan-009
$ grep -n "进度：2/2" docs/projects/xy/plans/008-high-expression-v2.md
8:> 进度：2/2 (100%) —— M5 主体已完成（5.1-5.3 待排期），进度 2/2 为子项完成口径
$ grep -n "状态：" docs/projects/xy/plans/008-high-expression-v2.md | head -1
3:> 项目：xy · 编号：xy-plan-008 · 状态：部分执行（M5 主体完成，5.1-5.3 功能卡待出） · 作者：OpenCode（集群架构） · 工具：OpenCode
$ grep -nE "进度：2/2 \(100%\)$" docs/projects/xy/plans/008-high-expression-v2.md   # 孤立矛盾行，无输出
$ git diff --stat    # 仅两文件、4 行改动（≤15）
 docs/projects/xy/plans/008-high-expression-v2.md | 4 ++--
 docs/projects/xy/roadmap.md                      | 4 ++--
 2 files changed, 4 insertions(+), 4 deletions(-)
```
验收标准逐条：① 6.1/6.2 状态=已完成+注记 ✓；② 进度行含「M5 主体完成…」注记、孤立矛盾行消除 ✓；③ diff 仅两文件共 4 行（≤15）✓；④ 无 M7/Cookie/业务仓改动 ✓（xianyu worktree 零改动）。

## 维护区

1. **方案同步**：[是] 008 状态口径修正，头部状态回填 + 进度行加注（M5 主体完成、2/2 为子项口径）。
2. **教训沉淀**：[无] 无新教训（口径回填属治理）。
3. **档案/README**：[否] 未动架构/接口。
4. **线路图**：[否] roadmap 状态回填即线路图本体，无新增规划。
