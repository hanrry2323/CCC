# 批次 3 执行指令 · CCC 系统化升级（B 生命周期：worktree 回收 + 重试重置）

> 来源：qx-map/__archive__/decisions/ccc-系统化升级方案-2026-08-08.md（commit d4f463e）· 批次 3「B 生命周期」
> 角色：OpenCode CCC 窗口（出指令 Agent）发出 · 你（Claude Code）是执行 Agent，**只执行本指令，不自行扩方向**
> 工作目录：/Users/apple/program/CCC（main 分支，批次 2 已含 421baf39）

## 一、目标（一句话）

给 worktree 与分支装上「生命周期」：**远端分支已删/卡已关闭/卡已打回即回收**（清理条件从「分支已合入 main」放宽到「远端凭证消失」），重试**不复用脏 worktree**（P1 灭），残留分支归零。

## 二、基线事实（先核对再动手）

- 2017 侧现状：**199 个本地分支、78 个 worktree**（方向档批次 3 基线「47 残留分支」已膨胀）
- 现有清理 `_cleanup_closed_worktrees`（server/engine/main.py:444-528）：
  - 只清**已关闭**卡 + worktree 干净 + `origin/main..HEAD` 无独有提交
  - **不处理**：卡已打回/待分派但 worktree 残留、远端分支已删但本地分支残留、卡已关闭但 worktree 有脏状态
- P1 现场（main.py:799-801）：「Worktree 目录已存在，重用」——重试/重派**无条件复用已存在 worktree**，脏状态/半成品分支被复用
- 批次 2 已完成：sidecar 失效机制（clear_card_state）、approve-merge 收口

## 三、任务（严格按序执行）

### 任务 1：worktree 回收条件放宽（核心）

改造 `server/engine/main.py` 的 `_cleanup_closed_worktrees`（或新建 `_reap_orphan_worktrees` 并在引擎周期调用）：

回收条件（满足**任一**即回收，worktree 干净或允许强删的场合分开处理）：
1. **远端分支已删**：`git ls-remote origin "refs/heads/codex/<slug>"` 无结果（或 fetch 后 origin/codex/<slug> 不存在）→ worktree 可回收（孤儿）
2. **卡已关闭/打回**：磁盘卡状态为「已关闭」「打回」→ worktree 可回收
3. 保留保护（**绝不强删**）：
   - worktree 有未提交改动 且 卡仍在执行/机审中（.running 标记存在）→ 跳过
   - 卡状态「执行中」「待分派」且远端分支存在 → 跳过（进行中）

实现要求：
- 回收 = `git worktree remove`（干净）或 `git worktree remove --force`（有脏改动但卡已关闭/打回/远端分支已删——**仅在**卡终态时允许 force）
- 回收后 `git worktree prune`
- 同一引擎周期内，对每个卡执行（复用现有 store.list_work + registry.entries 遍历框架）
- **注意**：引擎周期入口在 main.py:1607 `_cleanup_closed_worktrees(store, registry, cfg, log_dir)`——把新逻辑并入该调用点（返回清理计数，日志输出）

### 任务 2：本地残留分支清理

新增分支清理逻辑（并入任务 1 的同一周期）：
- 扫 `git branch` 本地 codex/* 分支，对每个分支：
  - 远端 `origin/codex/<slug>` 不存在（已删）→ 本地分支删除（`git branch -D`）
  - 卡已关闭且分支已合入 main → 删除
  - 分叉/未合入/进行中 → 保留（日志 INFO）
- 保留 `main` 与当前分支；不碰远端任何分支（远端清理归 approve-merge）

### 任务 3：重试不复用脏 worktree（P1 灭）

改造 `server/engine/main.py:794-800`（worktree 获取逻辑）：

规则：
1. 若 worktree 已存在，先检查**上次执行是否成功收单**（sidecar 状态：`read_card_state` 该卡最后状态为「已回写」且有产物证据；或 `{id}.log` 最新 worker 事件 ok=True）
2. 上次成功 → 复用（正常重派续跑场景）
3. 上次失败/无记录 → **不复用**：worktree 重置到干净状态（`git checkout -- .` + 清理 untracked）或删除重建（`git worktree remove --force` + `git worktree add -b codex/<slug> origin/main`）
4. 若重置失败（分支分叉等）→ 记录 warning，用干净重建兜底
5. 保留「目录不存在 → 新建」现有逻辑

验收锚点：重试时不再出现「复用上次失败的脏半成品」——每次重试从 `origin/main` 干净分支开始。

### 任务 4：单测补齐

`server/tests/`（新建 test_worktree_lifecycle.py 或并入现有 engine 测试）：
1. 回收条件：远端分支已删 → 可回收；卡已关闭 → 可回收；卡执行中+远端分支存在 → 不可回收
2. 分支清理：远端已删 → 本地删；分叉 → 保留
3. 重试重置：worktree 存在但上次失败 → 重置/重建（不直接复用）
4. 用 tmp_path 构造 fake git 仓或 mock subprocess（若构造 git 仓成本过高，允许 mock `subprocess.run` 断言调用序列）

### 任务 5：收敛存量（M1 侧只读，2017 侧由部署执行）

- M1 本地仅 2 分支无残留（无需清）
- 收敛逻辑（任务 1/2 的引擎周期）落地后，在 2017 部署后自动收敛 199 分支/78 worktree——**本批不 ssh 2017 手动清**，只保证代码逻辑正确

## 四、红线（违反即停）

1. **禁止触碰**：`server/config/`；2017 worktree/运行面（本批不改 2017、不 ssh 手清残留）；`docs/dispatch/` 卡文件
2. **禁止** 强删有未提交改动且卡仍进行中的 worktree（数据保护底线）
3. **禁止** 回退批次 1（P6）/批次 2（sidecar 规则、approve-merge 收口）已验收改动
4. 禁 `git add -A`；禁含密钥提交
5. 测试不过/歧义 → 停手记录

## 五、验证（写完必须跑）

1. `pytest server/tests/` 全绿（t53 存量 3 失败除外）
2. 任务 4 新增测试全绿
3. `git status` 干净

## 六、交付（执行完输出）

1. 改动文件清单 + diff 摘要（含行数）
2. 单测结果（跑通输出）
3. 回收/清理/重置逻辑说明（何时删、何时保留、何时 force）
4. 2017 侧预计收敛效果（基于当前 199 分支/78 worktree 估算：多少可清、多少保留）
5. push commit hash
6. 未决项 / 遗留

## 七、验收条件（OpenCode 窗口复核用）

1. 回收条件实现：远端分支已删/卡已关闭/卡已打回 → 可回收；进行中卡受保护
2. 本地分支清理：远端已删 → 删；分叉/进行中 → 保留
3. 重试重置：上次失败不复用脏 worktree（干净重建），上次成功才复用
4. force 删除仅限卡终态（已关闭/打回）或远端分支已删
5. 单测全绿（t53 除外）；push 后 origin/main 含改动；工作区干净
6. 不碰 2017/config/卡文件
