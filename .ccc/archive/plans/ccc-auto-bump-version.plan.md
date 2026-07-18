# Plan: ccc-auto-bump-version — Engine released 后自动版本 bump

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-board.py`（4219 行，7 角色看板核心）
- **当前结构要点**：
  1. `kb_role()`（L2670-2798）管理 verified → released 流转：读 VERSION → 创建 `board-{task_id}` tag → 推送 → CHANGELOG 追加（旧版本号）→ 收集建议 → move_task → `_bump_version()` 后置 bump → `_append_changelog()` 补 CHANGELOG 新条目 + git commit VERSION+CHANGELOG
  2. `_bump_version()`（L4148-4163）读 VERSION 文件，patch +1，写回；`_append_changelog()`（L4166-4211）追加 CHANGELOG 条目并 git commit VERSION+CHANGELOG.md
  3. 当前问题：CHANGELOG 被写了两次（old version L2728 + new version L4170）；git tag 是 `board-{task_id}` 而非 `v{major.minor.patch}`；VERSION bump 在 move 之后执行，导致 tag 不指向版本 bump commit
- **待改动点**：`scripts/ccc-board.py` 中 `kb_role()` 函数的重排序 + 版本 tag 替换 + 移除重复操作

---

## 范围

- **目标**：task 进入 released 列时自动 VERSION patch bump + 创建 `v{新版本}` git tag + 推送，不再手动版本管理
- **只改文件**：`["scripts/ccc-board.py"]`
- **不改文件**：`["VERSION", "CHANGELOG.md", "scripts/_board_store.py", "scripts/ccc-engine.py", "scripts/ccc-patrol-v4.py", "tests/"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：kb_role() 重排序 — 先 bump 版本 + 创建 v tag，后 release

### 做什么

当前 `kb_role()` 中版本 bump 在 move_task 之后执行，且 git tag 是看板级 `board-{task_id}` 而不是语义化版本 `v{major.minor.patch}`。改为：

1. 在每个 task 的 released 流程中，**先** `_bump_version()` 获得新版本号
2. **然后** `_append_changelog()` 追加 CHANGELOG 并 git commit VERSION+CHANGELOG（此函数已自包含 git add + git commit）
3. 创建 `v{新版本号}` annotated git tag，推送
4. 可选的：保留 `board-{task_id}` tag 作为辅助标记（不推送或保留）
5. 最后收建议 → move_task → released

移除旧代码中：
- 旧 CHANGELOG 追加块（L2715-2734，写旧版本号的重复条目）
- move 之后的重复 `_bump_version()` + `_append_changelog()`（L2749-2753）

### 怎么做

**1a. `scripts/ccc-board.py` — `kb_role()` 函数重构**（L2670-2798 局部修改，在 task 循环体内部）：

当前 task 循环体（从 `for task in list_tasks("verified"):` 开始到 `moved.append(task_id)` 结束）内：

1. **替换** L2678-2683（读取 VERSION）为新的流程入口：
   - 先调用 `new_ver = _bump_version(ROOT)` 拿到新版本号
   - 然后 `_append_changelog(ROOT, task_id, new_ver)` 追加 CHANGELOG + 自动 git commit

2. **替换** L2685-2713（`board-{task_id}` tag 创建+推送）为：
   - `sp.run(["git", "tag", "-a", new_ver, "-m", f"{new_ver}: {task_id} 发布"], ...)`
   - `sp.run(["git", "push", "origin", new_ver], ...)`
   - 可选保留 `board-{task_id}` tag（本地不推送）：`sp.run(["git", "tag", "-a", f"board-{task_id}", "-m", ...])` — 无 push 调用

3. **删除** L2715-2734（旧的 CHANGELOG 追加块，写 `[{version}] {today_str}` 等代码）

4. **删除** L2749-2753（后置 `_bump_version()` + `_append_changelog()` 重复调用）

5. L2736-2747（建议收集 + move_task）保持不变

**替换后的 task 循环体伪代码：**

```python
for task in list_tasks("verified"):
    task_id = task["id"]
    
    # ── Step 1: 版本 bump + CHANGELOG ──
    try:
        new_ver = _bump_version(ROOT)
        _append_changelog(ROOT, task_id, new_ver)
    except Exception as exc:
        _log.warning("version bump failed, skipping tag: %s", exc)
        new_ver = "unknown"
    
    # ── Step 2: git tag v{version} ──
    if new_ver != "unknown":
        sp.run(["git", "tag", "-a", new_ver, "-m", f"{new_ver}: {task_id} 发布"],
               cwd=ROOT, capture_output=True, timeout=10)
        sp.run(["git", "push", "origin", new_ver],
               cwd=ROOT, capture_output=True, timeout=30)
    
    # ── Step 3: 收集建议 ──
    report_file = ROOT / ".ccc" / "reports" / f"{task_id}.report.md"
    all_suggestions.extend(...)
    verdict_file = ROOT / ".ccc" / "verdicts" / f"{task_id}.verdict.md"
    all_suggestions.extend(...)
    
    # ── Step 4: 挪 released ──
    move_task(task_id, "verified", "released")
    moved.append(task_id)
```

**删除的确切代码段：**

```
L2715-L2734:
    # CHANGELOG.md 追加（第一处用旧版本号）
    today_str = now_iso()[:10]
    changelog_path = ROOT / "CHANGELOG.md"
    ...
    _log.info("[kb]  CHANGELOG 追加 %s (%s)", task_id, version)

L2749-L2753:
    try:
        new_ver = _bump_version(ROOT)
        _append_changelog(ROOT, task_id, new_ver)
    except Exception as exc:
        _log.warning("version bump failed (non-blocking): %s", exc)
```

### 验收清单

- [ ] `kb_role()` task 循环开头调用 `_bump_version(ROOT)` 获取新版本号
- [ ] 之后调用 `_append_changelog(ROOT, task_id, new_ver)` 追加 CHANGELOG + 自动 git commit
- [ ] 之后创建 `v{new_ver}` git tag 并 push origin
- [ ] 旧 CHANGELOG 追加块（`today_str = now_iso()[:10]` 开始的约 20 行）已删除
- [ ] 后置重复 `_bump_version()` + `_append_changelog()` 调用已删除
- [ ] 建议收集和 move_task 逻辑保持不变
- [ ] 版本 bump 或 tag 异常时不影响 task 流转（try/except 保护）
- [ ] `_append_changelog()` 内部已有 task_id 和版本去重检查

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-board.py` → 0 errors
- [语法] `python3 -c "import ast; ast.parse(open('scripts/ccc-board.py').read())"` → 无异常
- [bump 调用] `grep -n "_bump_version" scripts/ccc-board.py` → `kb_role()` 内调用一次（L4152 定义保留）
- [tag 创建] `grep -n '"git", "tag", "-a"' scripts/ccc-board.py` → `kb_role()` 内创建 `v{new_ver}` tag
- [tag 推送] `grep -n '"git", "push"' scripts/ccc-board.py` → `kb_role()` 推送 `v{new_ver}` tag
- [旧 CHANGELOG 块已删] `grep -n "today_str = now_iso()\[:10\]" scripts/ccc-board.py` → `kb_role()` 内不再出现（`_append_changelog` 内部有是正常的）
- [后置 bump 已删] `grep -n "post-move.*bump\|_bump_version.*after\|_append_changelog" scripts/ccc-board.py` → L2749 附近无 `_bump_version` + `_append_changelog` 对
- [测试] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | kb_role() 重排序：released 前先 bump VERSION + 创建 `v{版本}` tag + 推送，移除旧 CHANGELOG 重复追加和后置 bump | `feat(kb): released 后自动 VERSION bump + v tag (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/ccc-board.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/ccc-board.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
- [ ] 重排序后 task 流转不受影响：建议收集、move_task 逻辑不变
- [ ] 异常保护：bump / tag 操作有 try/except，不阻塞 task 进入 released

---

## 后续步骤

完成此改动后：
- 后续 `v{version}` tag 会逐步积累到 git 历史中；建议定期 `git push origin --tags` 确保所有 tag 同步
- 可考虑在 Cockpit Dashboard 展示最新版本号