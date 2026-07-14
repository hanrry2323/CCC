# Plan: patrol-zombie-cleanup — Patrol 僵尸 opencode 进程清理

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-patrol-v4.py`（954 行单文件，`main()` 按 6 步顺序执行）
- **当前结构要点**：
  1. Patrol 已有僵尸检测工具函数 `_is_zombie_pid()`（L401-414），通过 `ps -o state=` 检查 PID 是否为 Z 状态
  2. 已有崩溃循环检测 `_detect_crash_loop()`（L417-434），使用 `_is_zombie_pid()` 判断特定 task 的 PID 是否僵尸——但该函数**不接受外部 PID 参数**，只通过 task ID 猜 PID（扫描 pid 文件名匹配 tid），且返回 bool 而非执行清理
  3. 有全局 PID 目录常量 `PID_DIR = HOME / ".ccc" / "opencode-pids"`（L51），opencode-exec.py 在此写 pid 文件（`{phase_id}.pid`），最终在 executor 的 `finally` 块清理——但 zombie 进程可绕过此路径（opencode 变僵尸时 executor 还没跑完 cleanup）
  4. 目前无全量扫描 PID_DIR 检测 + 杀死僵尸 + 清理 pid 文件的函数。opencode-watchdog.sh 做了死进程和孤儿清理，但不检查僵尸状态
  5. 主流程在 `main()`（L858-946）中：Step 0 Engine 检测 → Step 1 扫描 → Step 2 异常排查 → Step 3 卡死检测 → Step 4 持久化 → Step 5 commit → Step 6 报告。新增逻辑应放在 Step 3 后/Step 4 前
- **待改动点**：
  - `scripts/ccc-patrol-v4.py`：新增 `cleanup_zombie_opencode_pids()` 函数，在 main() 中 Step 3 完成后调用

---

## 范围

- **目标**：Patrol v4 每次运行时全量扫描 `~/.ccc/opencode-pids/` 目录，检测 zombie 状态进程，杀死后清理 pid 文件，并记录操作到报告
- **只改文件**：`["scripts/ccc-patrol-v4.py"]`
- **不改文件**：`["scripts/opencode-pool.py", "scripts/opencode-watchdog.sh", "scripts/_executor.py", "scripts/_board_store.py", "scripts/ccc-engine.py", "tests/"]`
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1（Phase 1）：新增 zombie opencode 进程全量扫描 + 清理

### 做什么

当前 `_is_zombie_pid()` 和 `_detect_crash_loop()` 只针对"崩溃循环"场景做判断，不会主动清理僵尸进程。新增一个全量扫描函数，每次 patrol 运行时自动检测并清除所有僵尸 opencode 子进程。

具体行为：
1. 遍历 `~/.ccc/opencode-pids/` 下所有 `.pid` 文件
2. 读取每个文件内容获取 PID
3. 用 `_is_zombie_pid()` 检查是否为僵尸（Z 状态）
4. 僵尸进程：先 SIGTERM 优雅杀，等待 1 秒；还活着则 SIGKILL
5. 清理对应的 pid 文件（无论 kill 是否成功，pid 文件都可能残留）
6. 记录操作摘要（杀了几个、清理了几个文件）
7. 无僵尸时返回空列表（不产生噪声）

这个新函数放在 Step 3（卡死检测）之后、Step 4（状态持久化）之前调用，操作摘要写入 `all_fix_ops` 以在报告和 commit 中可见。

### 怎么做

**1a. `scripts/ccc-patrol-v4.py`** — 在 Step 2 函数区域（`triage_abnormal` 附近，L311 后）新增函数：

```python
def cleanup_zombie_opencode_pids() -> list[str]:
    """全量扫描 ~/.ccc/opencode-pids/，检测并清理 zombie opencode 进程。

    对每个 .pid 文件：
    1. 读 PID
    2. _is_zombie_pid(pid) 检查是否为 Z 状态
    3. 是 → 先 kill -TERM, sleep 1, 仍存活则 kill -KILL
    4. 清理 pid 文件（无论 kill 是否成功，文件都可能残留）

    Returns:
        操作描述列表，每项如 "zombie:{phase_id}(pid=12345) → killed+cleaned"
    """
```

实现细节：
- 如果 `PID_DIR` 不存在或为空，直接返回 `[]`
- 遍历 `PID_DIR.glob("*.pid")`
- 每个文件：`read_text().strip()` → `int()` → `_is_zombie_pid(pid)`
- 是 zombie → `os.kill(pid, signal.SIGTERM)` → `time.sleep(1)` → 仍然 `kill -0` 通过则 `os.kill(pid, signal.SIGKILL)` → `pid_file.unlink()`
- 操作字符串加入返回列表
- 非 zombie 的 pid 文件跳过（opencode-watchdog.sh 的死进程清理可覆盖）

**1b. `scripts/ccc-patrol-v4.py`** — 在 `main()`（L908-923 区域，Step 3 与 Step 4 之间）插入调用：

```python
    # ── Step 3.5: zombie opencode 进程清理 ──
    zombie_ops = cleanup_zombie_opencode_pids()
    if zombie_ops:
        all_fix_ops.extend(zombie_ops)
        engine_operated = True
```

注意：放在 `_save_stuck_counters` 之前、Step 3 的循环之后，确保 `all_fix_ops` 累积到持久化和 commit 中。

**1c. `scripts/ccc-patrol-v4.py`** — 确保 `import signal` 在文件顶部（L24 `import sys` 之后追加 `import signal`，或检查是否已引入。当前只有 `import subprocess` 无 `import signal`，需要新增）。

### 验收清单

- [ ] 新函数 `cleanup_zombie_opencode_pids()` 存在，位于 `triage_abnormal` 之后
- [ ] 函数签名 `def cleanup_zombie_opencode_pids() -> list[str]:`
- [ ] 遍历 `PID_DIR` 下所有 `.pid` 文件
- [ ] 用 `_is_zombie_pid()` 检测僵尸，不重复实现 ps 检测逻辑
- [ ] 僵尸进程先 SIGTERM 再 SIGKILL（kill -0 验证存活）
- [ ] 每次 kill 操作后清理 pid 文件（`pid_file.unlink()`）
- [ ] 无异常时静默返回 `[]`（不产生报告噪声）
- [ ] 写操作异常时 try/except 保护，不抛异常中断 patrol
- [ ] `main()` 中 Step 3 与 Step 4 之间有调用点
- [ ] 调用点将 `zombie_ops` 追加到 `all_fix_ops`
- [ ] `import signal` 在文件顶部
- [ ] `python3 -m compileall -q scripts/ccc-patrol-v4.py` 零错误
- [ ] 所有现有测试通过

### 验收

- [编译检查] `python3 -m compileall -q scripts/ccc-patrol-v4.py` → 0 errors
- [语法] `python3 -c "import ast; ast.parse(open('scripts/ccc-patrol-v4.py').read())"` → 无异常
- [函数存在] `grep -n "def cleanup_zombie_opencode_pids" scripts/ccc-patrol-v4.py` → 匹配
- [调用存在] `grep -n "cleanup_zombie_opencode_pids" scripts/ccc-patrol-v4.py` → 至少 2 处（定义 + 调用）
- [import signal] `grep "^import signal" scripts/ccc-patrol-v4.py` → 存在
- [PID_DIR 引用] `grep "PID_DIR" scripts/ccc-patrol-v4.py` → 新函数和新调用都引用此常量
- [报告集成] `grep "zombie_ops" scripts/ccc-patrol-v4.py` → `all_fix_ops.extend(zombie_ops)` 存在
- [测试] `python3 -m pytest tests/scripts/ -q --timeout=60` → 全部通过
- [E2E 回归] `python3 -m pytest tests/e2e/ -q --timeout=120`（如可用）→ 全部通过

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 新增 `cleanup_zombie_opencode_pids()` 函数扫描 PID_DIR 并清理僵尸进程 + `main()` 中 Step 3 后调用 | `feat(patrol): zombie opencode 进程全量扫描 + 清理 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译/类型检查，零错误（`python3 -m compileall -q scripts/ccc-patrol-v4.py`）
- [ ] 全部测试通过（`python3 -m pytest tests/scripts/ -q --timeout=60`）
- [ ] diff 范围仅限 `scripts/ccc-patrol-v4.py`
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json phase 数 = 1
- [ ] Plan 中所有验收意图全部达成
- [ ] 新函数复用现有的 `_is_zombie_pid()`，不引入重复的 ps 检测逻辑
- [ ] kill 流程有 try/except 保护（OSError, ValueError），不因单文件异常而中断全量扫描
- [ ] 报告集成：操作摘要加入 `all_fix_ops`，在 patrol 的单行报告中可见

---

## 后续步骤

完成此改动后，建议：
- opencode-watchdog.sh 未来可加入类似僵尸检测（当前 watchog 只杀死进程和孤儿，不检测 Z 状态）
- Cockpit Dashboard 可增加"最近清理的僵尸数"统计
- 长期可考虑在 Engine 层增加 opencode 子进程健康检查回调，尽早发现僵尸趋势