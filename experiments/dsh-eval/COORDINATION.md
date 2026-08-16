# 实验分支运维协调（2026-08-16）

## 工作区位置
- **主 checkout**：`/Users/apple/program/CCC`（`main` 分支，Codex/其他席共用）
- **本实验分支 worktree**：`/Users/apple/program/CCC-wt-dsh-eval`（`research/dsh-eval`，**我 W1 专用**）
- 实验文件一律在 worktree 里改、commit、push 到 `origin/research/dsh-eval`。

## 为什么建 worktree
CCC 主 checkout 与 Codex 共享。2026-08-16 实测：Codex 在主 checkout 切分支/commit 时，
把我的 `research/dsh-eval` 检出状态打断（分支被切走、误提交混入）。worktree 隔离后，
我的实验工作区不再受主 checkout 的切换影响。

## 已知污染：09d592a0（Codex 误提交，保留待协调）
- `research/dsh-eval` 顶部有 `09d592a0 plans: accept docs/projects/hp/plans/008-pipeline-ssot-backfill.md`
  ——Codex 在我检出该分支时未切自己的分支直接 commit，误落到本分支。
- 该提交含 Codex 有效工作（与 main 版本不一致），**不可清除**（reset+force-push 会丢它）。
- 处理：保留。分支合入 main 前与 Codex 协调，将该提交归位（或确认已并入 main）。
- 对实验无影响：我的实验提交在其下，干净。

## 提交纪律
- 只 add `experiments/` 下我的文件，**绝不 `git add -A`**（防混入 Codex/他席改动）。
- commit 前 `git status` 核对暂存区只有我的文件。
