# Plan: index-json-auto-sync —  patrol commit 前自动同步 index.json

> 撰写：ccc-product | 执行：ccc-dev（auto）

---

## 当前代码状态

<!-- v0.23 强制：Plan 必须包含此段 -->
<!-- 关键发现：patrol 的 _move_task 不更新 index.json，read_board_index 用目录遍历绕过它 -->

- **入口/核心文件**：`scripts/ccc-patrol-v4.py`（860 行）、`scripts/_board_store.py`（907 行）
- **当前结构要点**：
  1. `ccc-patrol-v4.py:362-384`：`_move_task()` 搬移 task 文件但不更新 `index.json`
  2. `ccc-patrol-v4.py:107-116`：`read_board_index()` 注释写"**避开 stale index.json**"——直接遍历目录，证明了 stalenes 问题存在
  3. `_board_store.py:548-562`：`FileBoardStore.update_index()` 已有现成实现（加锁 + 原子写入），可复用
  4. `ccc-patrol-v4.py:602-652`：`commit_patrol_fix()` 在 git commit 前未同步 index.json
- **待改动点**：`ccc-patrol-v4.py` commit 流程中插入一步 index.json 同步

---

## 范围

- **目标**：patrol 的 board 操作后自动同步 index.json，使 patrol 报告和其他消费者读到最新数据
- **只改文件**：`["scripts/ccc-patrol-v4.py"]`
- **不改文件**：`["scripts/_board_store.py", "scripts/ccc-board.py"]`
- **执行方式**：`auto`
- **Phase 数**：1

---

## 改动 1：patrol commit 前同步 index.json

### 做什么

在 patrol 每次完成 board 操作（abnormal 排查、卡死检测）后、执行 git commit 之前，自动更新各 workspace 的 `.ccc/board/index.json`。

当前 patrol 只在 commit 时做 git 操作，但 **index.json 没有被重新生成**，导致：
- `read_board_index()` 不得不绕过 index 直接读目录（见函数注释）
- cockpit/dashboard 等依赖 index.json 的消费者读到 stale 数据
- patrol 自身 `scan_all_ws()` 用 `read_board_index()` 绕过了这个问题，但其他人没有绕

### 怎么做

在 `ccc-patrol-v4.py` 中：

1. **新增函数 `_sync_board_index(ws: Path) -> None`**（约 10 行）：
   - 创建 `FileBoardStore(ws)` 实例
   - 调用 `store.update_index()`
   - 静默处理异常（不因为 index 同步失败阻塞 patrol 流程）

2. **修改 `commit_patrol_fix()`**（或调用者在 main 中传入参数）：
   - 在 `git add` 之前，对本 workspace 调 `_sync_board_index(ws_path)`
   - 确保 index.json 的变动也被 `git add` 纳入

3. **不动的**：`_move_task()` 本身——不需要每次搬一个文件就写一次 index（浪费）；batch 到 commit 前一次性同步即可。

### 验收清单

- [ ] `_move_task` 搬移后，index.json 在 commit 前自动更新
- [ ] index.json 内容与目录实况一致
- [ ] index 同步失败不中断 patrol 主流程（静默跳过）
- [ ] 现有 `read_board_index()` 可以移除"避开 stale index.json"注释（验收后可选）

### 验收

- [index.json 与目录一致] 跑 patrol，确认 index.json 计数 = 实际文件数（参考：`python3 -c "import json; ..." `）
- [同步失败不中断] 模拟 index 写入失败（如只读目录），patrol 仍正常退出 code 0
- [read_board_index 可改用 index.json] 验证 patrol 报告数字一致（参考：`python3 scripts/ccc-patrol-v4.py`，对比前后 index.json）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 在 `commit_patrol_fix` 前同步 index.json | `fix(patrol): 同步 index.json 在 commit 前 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m py_compile scripts/ccc-patrol-v4.py`）
- [ ] 全部测试通过
- [ ] diff 范围仅限 `scripts/ccc-patrol-v4.py`
- [ ] 每个 phase 对应一个 commit
- [ ] phases.json 与 plan phase 数一致
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤（可选）

完成本 task 后，可择机清理 `read_board_index()` 中的"避开 stale index.json"注释——它已不再需要这个 workaround。