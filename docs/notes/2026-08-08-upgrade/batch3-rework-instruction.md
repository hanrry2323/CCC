# 批次 3 返工指令 · 补测试适配

> 验收判定：代码逻辑通过，测试 2 处不达标 → 返工
> 范围极小：只补测试，不动已通过的生命周期逻辑

## 返工任务（严格按序）

### 任务 1：适配存量回归测试

文件：`server/tests/test_engine_main.py::TestEngineWorktree::test_cleanup_closed_worktree`

现状：断言 `assert n == 1` + `assert wt2.exists()`（旧语义「已关闭+脏 → 保留」）

新语义（批次 3 设计，已验收通过）：**卡终态（已关闭/打回）即有未提交改动 → force 回收**

修改断言：
- `assert n == 2`（close1 干净回收 + dirty1 终态 force 回收）
- `assert not wt1.exists()` 保留
- `assert not wt2.exists()`（改为断言 dirty1 被 force 回收）

并在测试注释中写明：dirty1 卡已关闭（终态）→ 脏改动 force 回收属设计语义，未提交改动由关闭流程归档兜底。

### 任务 2：补正向用例

文件：`server/tests/test_worktree_lifecycle.py`（或并入 `test_dispatch_and_collect_retry_reset_on_failure`）

新增测试：`test_dispatch_and_collect_retry_reuses_successful_worktree`
- 构造：worktree 已存在 + sidecar 该卡 state=已回写（或 log 末尾 ok=True 事件）
- 断言：**不触发** checkout/clean/remove 重置命令，直接复用 worktree 路径
- 用 mock subprocess.run 断言调用序列（与现有测试同法）

### 红线（同批次 3，重申）

1. **不动** `_cleanup_closed_worktrees` / 重试重置的已验收逻辑（只补测试）
2. 禁 `git add -A`；禁碰 config/2017/卡文件

## 验证

1. `pytest server/tests/test_engine_main.py::TestEngineWorktree -v` 全绿
2. `pytest server/tests/test_worktree_lifecycle.py -v` 全绿（3 个测试）
3. `pytest server/tests/` 仅剩 t53 存量 3 失败
4. `git status` 干净

## 交付

1. 改动文件 + diff 摘要
2. 单测输出
3. push commit hash
