# Plan: gitkeep-cleanup — 看板 .gitkeep 清理

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`.ccc/board/backlog/`、`.ccc/board/planned/`、`.ccc/board/in_progress/`、`.ccc/board/testing/`、`.ccc/board/verified/`、`.ccc/board/released/`
- **当前结构要点**：
  1. 看板 6 列目录各有一个 `.gitkeep`（0 字节空文件），全都被 git tracked
  2. `.gitignore` 中 `.ccc/board/released/` 已被忽略（L22），但 `released/.gitkeep` 在被跟踪后加入的 gitignore，仍会被 git 跟踪
  3. 这些 `.gitkeep` 的唯一用途是保持空目录在 git 中 — 但看板列目录即使无 `.gitkeep` 也会因为目录中存在其他被跟踪的 JSONL 任务文件而被 git 保留（`backlog/`、`in_progress/`、`released/` 都有内容）
  4. `testing/` 和 `verified/` 目前为空（仅 .gitkeep），`planned/` 仅 .gitkeep — 删除后这些空目录不再出现在 git 中，但磁盘上仍存在
  5. `docs/v1.0-pipeline-plan.md:30` 已标记 `.gitkeep` 为待清理项（"无所谓但难看"），代码中无任何对 `.gitkeep` 的引用依赖
- **待改动点**：
  - `.ccc/board/backlog/.gitkeep` — `git rm`
  - `.ccc/board/planned/.gitkeep` — `git rm`
  - `.ccc/board/in_progress/.gitkeep` — `git rm`
  - `.ccc/board/testing/.gitkeep` — `git rm`
  - `.ccc/board/verified/.gitkeep` — `git rm`
  - `.ccc/board/released/.gitkeep` — `git rm`

---

## 范围

- **目标**：从 git 跟踪中移除 6 个看板列的 `.gitkeep` 空文件。磁盘上文件保留（git rm 后如不 commit 则文件仍在），commit 后磁盘文件删除。
- **只改文件**：无代码文件改动。操作对象是 6 个 `.gitkeep`（`git rm`）。
- **不改文件**：所有 `.py` / `.sh` / `.md` / `.json` / `.jsonl` 文件不动
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：`git rm` 全部 6 个 .gitkeep

### 做什么

从 git 跟踪中移除看板 6 列的 `.gitkeep` 空文件。这些文件仅在 git 首次跟踪空目录时有用，现在看板列已存有实际任务文件（`backlog/` 有 3 个 JSONL、`in_progress/` 有 1 个、`released/` 有 80 个），空目录已被隐含保留。删除后 `testing/`、`verified/`、`planned/` 若不包含被跟踪文件则在 git 中不再存在目录条目，但磁盘上目录依然存在（`.gitkeep` 文件本身在 `git rm` 后未 commit 前保留）。

### 怎么做

**1. `git rm` 全部 6 个 .gitkeep**：

```bash
git rm .ccc/board/backlog/.gitkeep
git rm .ccc/board/planned/.gitkeep
git rm .ccc/board/in_progress/.gitkeep
git rm .ccc/board/testing/.gitkeep
git rm .ccc/board/verified/.gitkeep
git rm .ccc/board/released/.gitkeep
```

合理合并为单条 `git rm` 命令：
```bash
git rm .ccc/board/*/.gitkeep
```

### 验收清单

- [ ] 验收条件 1：`git rm` 后 `git status` 显示 6 个 "deleted" 变更
- [ ] 验收条件 2：commit 后 `git ls-files .ccc/board/*/.gitkeep` 返回空
- [ ] 验收条件 3：磁盘上 `ls -la .ccc/board/*/.gitkeep` 文件已删除（被 `git rm` + commit 清理）
- [ ] 验收条件 4：看板运行不受影响 — `ccc-board.py` / `ccc-engine.py` 不依赖 .gitkeep 存在
- [ ] 边界场景：`testing/`、`verified/`、`planned/` 目录在 commit 后仍保留在磁盘（空目录）
- [ ] 错误处理：无。纯 `git rm` 操作，无外部依赖。

### 验收

- [git 状态确认] commit 前 `git status` 显示 6 个 `deleted: .ccc/board/*/.gitkeep`（参考：`git status | grep gitkeep`）
- [git 跟踪确认] commit 后 `git ls-files .ccc/board/*/.gitkeep` 输出为空
- [磁盘确认] `ls -la .ccc/board/*/.gitkeep 2>&1` 输出 `No such file or directory`
- [回归确认] `uv run pytest tests/scripts/ -q 2>&1 | tail -5` 全部 PASSED

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 从看板 6 列删除 .gitkeep 空文件 | `chore(board): 移除看板 6 列的 .gitkeep 空文件 (phase 1/1)` |

---

## 全局验收清单

- [ ] `git rm` 后 `git status` 确认 6 个 deleted
- [ ] commit 后 `git ls-files .ccc/board/*/.gitkeep` 空
- [ ] 磁盘 `.gitkeep` 文件清除
- [ ] pytest 全部通过
- [ ] 单 phase 单 commit
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

无。部署无需重启服务。`testing/`、`verified/`、`planned/` 在 git 中不再有目录条目，但磁盘目录依然存在，新文件被 git add 时会自动重新跟踪。