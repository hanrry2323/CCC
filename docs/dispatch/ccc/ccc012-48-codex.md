# 任务卡 ccc012 · 48 分叉 codex 分支人工核验清理（Claude Code 执行）

> 关联：升级批次 3 生命周期 · 执行体：Claude Code · 验收：Claude Code · 状态：已关闭· 派发：manual · 项目：ccc · 日期：2026-08-08

## 目标

2017 侧 48 个 codex/* 分叉分支逐一人工核验：无保留价值者删除（git branch -D），有价值的记录保留理由，收敛后分支总数显著下降。

## 红线（先看）

1. 1. 只改 scripts/deploy-ccc.sh 第 55 行 pytest 调用；不动其他任何文件/服务。
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

白名单：仅 2017 侧 `git branch` 本地 codex/* 分支的**删除动作**（人工核验后执行）。禁止碰远端分支、worktree、卡文件。

权威路径：2017 /Users/fan/program/CCC（引擎回收逻辑只清孤儿，分叉分支需人工核验）。禁止新建 worktree。

## 步骤

1. 2017 侧 `git branch | grep codex/` 列出全部本地 codex 分支（当前 48 个）。
2. 逐支核验保留理由：`git log --oneline origin/main..<branch> | head` 看独立 diff；`git show-ref --verify refs/remotes/origin/codex/<slug>` 看远端是否已删（远端已删+本地分叉=重点核验对象）。
3. 判定标准：无独立价值（diff 为空/已并入 main/远端已删且 diff 无意义）→ `git branch -D <branch>`；有独立价值（未合入的实质改动）→ 保留并记录。
4. 输出核验清单（每支：保留/删除+理由）到回写区。
5. 卡头改为「已回写」。
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 核验清单覆盖全部 48 支（每支有 保留/删除 结论）。
2. 删除动作只在 2017 本地执行，远端/卡文件零触碰。
3. 探针=git 对齐：`git branch | wc -l` 删除后计数与清单一致。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：Claude Code · 日期：2026-08-08

核验完成（2026-08-08，2017 侧人工核验+执行）：本地 codex 分支 48 → 12。

**删除 36 支**（14 支：远端已删+无独立提交=纯垃圾；22 支：远端在备份+已关闭卡残留）：
- flow-real-001, t52-auto-base, t53-console-roadmap-fix, t54-auto-naming, t57-big-small-cards, t58-board-refactor, t59-conversation-as-workflow, t59-engine-parallel, t61-task-flow-linked, t63-nginx-entry, t64-engine-auto-worktree, t65-dual-shell-align, t66-card-format, t69-release-engine-plist-rebuild
- hp016, mx009, mx013-mx023(10), mx025, xy016, xy017, xy019-xy023(5), xy025

**保留 12 支**：
- 5 支 worktree 占用（执行中/通用 ws）：hp009, mx026, xy024, xy026, t67-deploy-race-guard
- 7 支远端已删+有独立提交（唯一副本，main 无）：t51-kb-mcp-optimize(5), t55-index-layer(1), t56-card-components(5), t60-console-cockpit(1), t62-archive-review(2), t71-fix-server-p0(4), t72-desktop-p0(3)

探针：`git branch | grep -c 'codex/'` = 12；远端/worktree/卡文件零触碰。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
