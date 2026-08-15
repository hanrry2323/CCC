# 批次 3 返工指令（第二次）· 修复孤儿回收误杀真 bug

> 验收判定：**代码 bug 确认** —— 批次 3 回收逻辑把「已回写但本地分支未推送」的活跃 worktree 误判为孤儿回收
> 证据：`test_run_once_with_worktree_enabled` 日志链
>   创建 worktree 成功 → 执行体收单「已回写」→ 同一周期 _cleanup_closed_worktrees →
>   「origin/codex/t64 不存在」→ should_reap → worktree 被删（force=False）
> 影响：执行体刚建分支、收单但未 push 的窗口期，worktree + 分支证据被误删（生产会丢产物）

## 一、根因（先看懂再动手）

`server/engine/main.py` `_cleanup_closed_worktrees` 回收条件第二支：

```python
elif not remote_branch_exists:   # 只查远端 origin/codex/<slug>
    should_reap = True
```

问题：**本地分支存在 ≠ 远端分支存在**。刚 `git worktree add -b codex/<slug>` 创建的本地分支，在 push 之前远端没有对应引用。此时：
- 卡「待分派/执行中」：worktree 正在使用 → 不能回收（现有逻辑靠「远端存在才保留」漏保护）
- 卡「已回写」：worktree + 本地分支是收单证据 → 不能回收

**孤儿真义**：远端分支不存在 **且** 本地分支（`refs/heads/codex/<slug>`）也不存在 —— 才是无主残留。

## 二、修复任务（严格按序）

### 任务 1：回收条件修正（核心）

修改 `_cleanup_closed_worktrees` 的孤儿判定：

```python
# 本地分支也存在才不算孤儿（刚 add 未 push 的本地分支是活跃证据）
local_branch_exists = (git show-ref refs/heads/codex/<slug> 成功)

elif (not remote_branch_exists) and (not local_branch_exists):
    should_reap = True
    if is_dirty:
        use_force = True
```

并更新 docstring：孤儿 = 远端与本地分支均不存在。

**同时给回收保护加一道硬闸**：`disk_base in ("待分派", "执行中", "已回写")` 且 worktree 存在 → **一律跳过回收**（无论分支是否存在）——进行中/已收单卡的 worktree 是运行现场，清理只针对终态（已关闭/打回）与真孤儿。

### 任务 2：单测适配

1. `server/tests/test_engine_main.py::TestEngineWorktree::test_run_once_with_worktree_enabled`：修复后应**自动恢复**（worktree 不再被同周期回收）。若仍失败，检查断言与修复逻辑一致性。
2. `server/tests/test_worktree_lifecycle.py::test_cleanup_closed_worktrees_lifecycle`：
   - hp003（待分派+远端删→回收）场景需检查 mock 的本地分支状态——若 mock 未提供本地分支引用，该场景仍是真孤儿可回收（保持）；若 mock 有本地分支存在，则改为「保留」断言
   - **新增场景**：卡「已回写」+ 本地分支存在 + 远端不存在 → 保留（防回归本 bug）
3. 跑全量，`test_cleanup_closed_worktree`（`n==2` 断言）必须仍绿——close1/dirty1 都是终态（已关闭），修复不影响。

### 红线（重申）

1. 只改 `_cleanup_closed_worktrees` 回收判定 + 对应测试；**不动**重试重置（上次成功复用/失败重建）已验收逻辑
2. 禁 `git add -A`；禁碰 config/2017/卡文件

## 三、验证

1. `pytest server/tests/test_engine_main.py::TestEngineWorktree -v` 全绿
2. `pytest server/tests/test_worktree_lifecycle.py -v` 全绿
3. `pytest server/tests/` 仅剩 t53 存量 3 失败
4. `git status` 干净

## 四、交付

1. 改动文件 + diff 摘要
2. 修复说明（孤儿判定新语义 + 硬闸逻辑）
3. 单测输出
4. push commit hash
