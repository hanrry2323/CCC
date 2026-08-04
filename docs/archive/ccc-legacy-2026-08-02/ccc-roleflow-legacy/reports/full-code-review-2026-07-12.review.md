# Code Review Report — CCC 项目全面审查

> **审查日期**: 2026-07-12  
> **审查者**: 代码审查专家（火眼眼 👁️）  
> **审查范围**: `scripts/*.py` + `scripts/*.sh` + `tests/`  
> **审查标准**: `references/code-review-standard.md` v1.0  
> **代码规模**: ~15 Python 文件, ~3500 行核心代码

---

## 审查摘要

**Verdict**: CONDITIONAL_PASS

**问题统计**:

| 级别 | 数量 |
|------|------|
| Critical | 3 |
| High | 6 |
| Medium | 8 |
| Low | 5 |

**整体印象**:

CCC 项目的架构设计相当出色——7 角色看板 + 串行引擎 + 红线约束体系，体现了成熟的工程思维。安全意识不错（无 shell=True、无 eval、有路径穿越防护），进程管理有完善的 try/finally 兜底。

但代码质量确实"参差不齐"，主要体现在三个方面：

1. **R-08 红线大面积违反** — 几乎所有脚本用 `print()` 冒充日志
2. **错误吞没泛滥** — 大量 `except Exception: pass` 让问题静默消失
3. **代码重复严重** — `sanitize_id` / `now_iso` 等函数定义了 3-4 份

值得表扬的设计：文件锁 + 原子写入、advisory lock 防并发审查、phase 依赖循环检测（DFS 三色标记）、进程组 kill 级联。

---

## 详细发现

### 🔴 Critical

#### C-001: `_archive_to_quarantine` 引用不存在的 `self.workspace` 属性

**文件**: `scripts/_board_store.py:604`  
**维度**: 正确性

```python
def _archive_to_quarantine(self, task_id, task, reason, from_col):
    workspace = self.workspace if hasattr(self, "workspace") else self.board.parent.parent
```

**Why**: `FileBoardStore.__init__` 只设了 `self.board` 和 `self.events_dir`，没有 `self.workspace`。虽然有 `hasattr` 兜底，但 `self.board.parent.parent` 依赖路径层级假设（`.ccc/board` → `.ccc` → workspace）。如果 `FileBoardStore` 被传入非标准路径，`parent.parent` 会指向错误目录。

**Suggestion**: 在 `__init__` 中显式保存 `self.workspace = workspace`。

---

#### C-002: `_record_event` 写文件无锁保护

**文件**: `scripts/_board_store.py:699`  
**维度**: 安全性 / 正确性

```python
def _record_event(self, task_id, from_col, to_col):
    ...
    with open(event_file, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

**Why**: `move_task` 和 `create_task` 都在持锁状态下调用 `_record_event`，但 `_record_event` 用 `open("a")` 追加写。如果两个线程同时 `move_task`（虽然有锁，但 `_acquire_ro` 读锁和写锁用的是同一个 lockfile，锁机制是 O_EXCL 互斥），事件文件可能被并发追加导致行交错。

**Suggestion**: 用 `_atomic_write` 模式（读旧 → 追加 → 原子写），或确保只在持锁状态下调用。

---

#### C-003: R-08 红线大面积违反 — print 冒充日志

**文件**: `scripts/ccc-board.py` (全文件), `scripts/_board_store.py`, `scripts/ccc-engine.py`  
**维度**: 可维护性 / 红线合规

grep 统计：仅 `ccc-board.py` 就有 **60+ 处 print()** 调用，包括关键路径如：

```python
# ccc-board.py:677
print(f"[failure-isolation] {task_id} all phases failed/skipped → abnormal")

# ccc-board.py:680
print(f"[failure-isolation] {task_id} move to abnormal failed: {exc}", file=sys.stderr)
```

红线 R-08 明确要求："所有 ccc-* 脚本必须用统一 logger，禁止用 print() 冒充日志输出。"

**Why**: print 无法被过滤、分级、重定向到文件。关键异常日志（如 failure-isolation）走 stderr print 会在 launchd 环境下丢失。

**Suggestion**: 
- 在 `_config.py` 或新建 `_logger.py` 中创建统一 logger
- 所有 `print(f"[role] ...")` 替换为 `logger.info("...")`
- 至少在 `ccc-board.py`、`ccc-engine.py`、`_board_store.py` 三个核心文件中完成迁移

---

### 🟡 High

#### H-001: `ccc-board.py` 单文件 3233 行 — 超出可维护上限

**文件**: `scripts/ccc-board.py`  
**维度**: 可维护性

**Why**: 单文件包含 7 个角色的完整实现 + phase 依赖解析 + git diff + LLM 审查 + 审计 + 回归 + 批处理 + CLI 入口。任何修改都需要在 3000+ 行中定位，PR review 困难，合并冲突频繁。

**Suggestion**: 按角色拆分：
- `ccc_roles/product.py` — product_role + plan 生成
- `ccc_roles/dev.py` — dev_role + launch/relaunch/check_complete
- `ccc_roles/reviewer.py` — reviewer_role + LLM 审查
- `ccc_roles/tester.py` — tester_role
- `ccc_roles/ops.py` — ops_role + stale 检测
- `ccc_roles/kb.py` — kb_role + AGENTS.md
- `ccc_roles/regress.py` — regress_role
- `ccc_roles/audit.py` — audit_role
- `ccc_board_core.py` — phases 解析 + 共享函数

---

#### H-002: 错误吞没泛滥 — 大量 `except Exception: pass`

**文件**: 全项目  
**维度**: 正确性 / 可维护性

grep 统计：约 **40+ 处** bare `except ...: pass`，典型如：

```python
# ccc-board.py:331
except Exception:
    pass

# ccc-board.py:574
except Exception:
    pass

# _board_store.py:327
except Exception:
    pass
```

**Why**: 静默吞掉异常会导致：
- 问题时滞：bug 不会立即暴露，而是在下游产生连锁反应
- 不可调试：日志里没有任何痕迹
- 违反红线 R-08 精神：异常应被 logger 记录

**Suggestion**: 至少加一行 `logger.debug(...)` 记录被吞掉的异常。对关键路径（如 phases.json 写入、lock 释放）的异常应升级为 `logger.warning`。

---

#### H-003: `sanitize_id` / `now_iso` 重复定义 3-4 份

**文件**: `ccc-board.py:49`, `_board_store.py:59`, `ccc-board-server.py:60`  
**维度**: 可维护性

```python
# ccc-board.py:49
def sanitize_id(tid: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(tid))
    return safe if safe else "invalid"

# _board_store.py:59 — 完全相同
def sanitize_id(tid: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(tid))
    return safe if safe else "invalid"

# ccc-board-server.py:60 — 多了 os.path.basename
def sanitize_id(tid: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", os.path.basename(tid))
```

同样 `now_iso` 在 4 个文件中各自定义，且行为不一致：
- `ccc-board.py` 返回 `Asia/Shanghai` 时区
- `_board_store.py` 返回 UTC
- `ccc-engine.py` 返回 `Asia/Shanghai`

**Why**: 行为不一致是定时炸弹。`now_iso()` 在 board.py 返回 +08:00，在 store.py 返回 Z，时间比较时可能出错。

**Suggestion**: 统一到 `_config.py` 或新建 `_utils.py`，所有脚本从那里导入。

---

#### H-004: `quarantines_cleanup_task` / `quarantines_index_task` 与 `quarantine_store_content` 格式不匹配

**文件**: `scripts/_board_store.py:760-945`  
**维度**: 正确性

```python
# quarantine_store_content (line 789-792): 直接 copy，无 .tar.gz 后缀
if content_path.is_dir():
    shutil.copytree(content_path, out_file, dirs_exist_ok=True)
else:
    shutil.copy2(content_path, out_file)

# 但 quarantines_cleanup_task (line 815): 只扫 .tar.gz
for tar in quarantine_dir.glob("*.tar.gz"):
    ...

# quarantines_index_task (line 857): 也只扫 .tar.gz
for tar in d.glob("*.tar.gz"):
    ...
```

**Why**: `quarantine_store_content` 已改为直接 copy（无 tar.gz），但 cleanup 和 index 函数还在扫描 `*.tar.gz`。这意味着所有 quarantine 副本永远不会被清理，也不会被索引。

**Suggestion**: 更新 cleanup 和 index 函数的 glob 模式，扫描所有文件（或排除 `index.json`）。

---

#### H-005: `list_tasks` 读操作使用排他锁 — 性能瓶颈

**文件**: `scripts/_board_store.py:441-469`  
**维度**: 性能

```python
def list_tasks(self, column: str) -> list[dict]:
    ...
    excl_path = self._acquire_ro(timeout_s=3.0)  # O_EXCL 排他锁
```

**Why**: `_acquire_ro` 实际上调用 `_acquire_lock`，创建的是 O_EXCL 独占锁文件。这意味着所有读操作都互斥——`get_board_state` 调用 `list_tasks` 7 次，每次都获取/释放锁，共 7 次文件系统 IPC。

在 `ccc-board-server.py` 的 `/api/dashboard` 路由中，多 workspace 场景下每个 ws 要读 5 列 × 7 workspace = 35 次锁获取。

**Suggestion**: 
- 读操作不需要排他锁，可以直接读文件（JSONL 文件是 append-only，读时不会有撕裂）
- 或者用 `fcntl.flock(LOCK_SH)` 共享锁（但项目已注释 `_HAS_FLOCK = False`）
- 至少在 `get_board_state` 中一次性获取锁，读所有列后释放

---

#### H-006: `_resolve_phase_dependencies` 函数内部重复 import

**文件**: `scripts/ccc-board.py:274, 304`  
**维度**: 可维护性 / 性能

```python
def _resolve_phase_dependencies(phases: list[dict]) -> ...:
    ...
    if cycles:
        try:
            ...
            import json as _json  # ← 函数内 import
            ...
            import json as _json  # ← 又一次
```

**Why**: `json` 已在文件顶部导入。函数内重复 import 是不必要的，且 `_json` 别名容易混淆。

**Suggestion**: 删除函数内的 `import json as _json`，直接用顶部导入的 `json`。

---

### 🟡 Medium

#### M-001: `dev_role` 函数 300 行 — 逻辑臃肿

**文件**: `scripts/ccc-board.py:1051-1346`  
**维度**: 可维护性

**Why**: `dev_role()` 函数从第 1051 行到第 1346 行，包含退避检查、retry 计数、phases.json 读写、PID 检查、opencode 启动、结果处理 6 个职责。

**Suggestion**: 拆分为：
- `_dev_check_retry(task_id, phases_file)` → 退避检查 + retry 计数
- `_dev_check_done(task_id)` → .done 文件检查 + 结果处理
- `_dev_launch_opencode(task_id, plan, phases_file)` → 启动 opencode

---

#### M-002: `_get_code_context` 缓存永不失效

**文件**: `scripts/ccc-board.py:840`  
**维度**: 正确性

```python
_get_code_context_cache: dict[str, str] = {}

# line 835
_get_code_context_cache[str(ws_path)] = result
```

**Why**: 模块级字典缓存，进程存活期间永不失效。如果 product_role 在同一 Engine 进程中被多次调用，代码文件树和 git log 会使用首次调用时的快照，错过后续代码变更。

**Suggestion**: 加 TTL 过期（如 300s）或改为按 git commit hash 缓存。

---

#### M-003: `tester_role` 用 `shlex.split` 执行验收命令 — 命令注入风险

**文件**: `scripts/ccc-board.py:1972-1978`  
**维度**: 安全性

```python
for cmd in verify_commands:
    r = sp.run(
        shlex.split(cmd),
        shell=False,
        ...
    )
```

**Why**: 虽然用了 `shell=False`（好），但验收命令来自 `plan.md` 文件，如果 plan 中被注入恶意命令（如 `; rm -rf /`），`shlex.split` 会把它拆成参数传给第一个 token。不过 `shell=False` 确实阻止了 shell 注入，所以风险等级降为 Medium。

**Suggestion**: 对验收命令做白名单过滤（只允许 `python3 -m pytest`、`ruff`、`mypy` 等）。

---

#### M-004: `regress_role` 对所有 released task 跑全量 py_compile

**文件**: `scripts/ccc-board.py:2612-2618`  
**维度**: 性能

```python
for task in tasks:
    ...
    for py in py_files:  # py_files = 全部 scripts/*.py
        r = sp.run(
            ["python3", "-m", "py_compile", str(py)],
            ...
        )
```

**Why**: 每个 released task 都对所有 Python 文件跑一次 py_compile。如果有 10 个 released task 和 20 个 py 文件，就是 200 次 subprocess 调用。py_compile 结果应该只跑一次然后共享。

**Suggestion**: 在 task 循环外跑一次 py_compile，循环内只检查结果。

---

#### M-005: `ccc-board-server.py` `_verify_auth` 无 rate limit for auth failures

**文件**: `scripts/ccc-board-server.py:339-361`  
**维度**: 安全性

**Why**: 虽然有全局 `_RateLimiter`，但 401 认证失败不计入 rate limit。攻击者可以无限次尝试 token。

**Suggestion**: 认证失败时也消耗一个 token，或对 401 响应加 1s 延迟。

---

#### M-006: `kb_role` CHANGELOG 追加模式可能导致重复条目

**文件**: `scripts/ccc-board.py:2188-2194`  
**维度**: 正确性

```python
entry = f"\n## [{version}] - {today_str}\n\n- {task_id}: ..."
if changelog_path.exists():
    changelog_path.write_text(changelog_path.read_text() + entry)
```

**Why**: 如果 kb_role 被重试（如 git push 失败后重跑），同一个 task 会生成两条 CHANGELOG 条目。没有去重检查。

**Suggestion**: 写入前检查 CHANGELOG 中是否已包含 `task_id`。

---

#### M-007: `_board_store.py` `_release_lock` 有死代码 — `_HAS_FLOCK` 永远为 False

**文件**: `scripts/_board_store.py:23, 324-338`  
**维度**: 可维护性

```python
_HAS_FLOCK = False  # 硬编码 False

def _release_lock(lock_obj):
    if _HAS_FLOCK:        # 永远不执行
        try:
            fcntl.flock(lock_obj, fcntl.LOCK_UN)
        ...
    else:
        os.unlink(str(lock_obj))
```

**Why**: `_HAS_FLOCK` 硬编码为 False，flock 分支是死代码。留着只会让读者困惑。

**Suggestion**: 删除 flock 分支，直接 `os.unlink`。

---

#### M-008: `_get_git_diff` fallback 逻辑用 `HEAD~1` 不检查是否有 commit

**文件**: `scripts/ccc-board.py:1513-1518`  
**维度**: 正确性

```python
rev_r = sp.run(
    ["git", "rev-parse", "--verify", since],
    ...
)
ref = since if rev_r.returncode == 0 else "--root"
```

**Why**: 如果仓库只有 1 个 commit，`HEAD~1` 不存在会 fallback 到 `--root`，这是正确的。但如果仓库完全没有 commit，`--root` 也会失败，异常会被外层 `except (subprocess.TimeoutExpired, OSError)` 捕获返回空字符串。虽然不会崩溃，但返回空 diff 会让 reviewer 误判为"无变更"。

**Suggestion**: 在 diff 为空时显式记录 warning。

---

### 💭 Low

#### L-001: `ccc-board.py` 模块级全局变量 `cfg` / `store` / `ROOT`

```python
cfg = Config()
store = FileBoardStore(cfg.workspace)
ROOT = cfg.workspace
```

**Why**: 模块级初始化意味着 import 时就创建 FileBoardStore（包括 mkdir）。如果 workspace 路径有权限问题，import 直接失败。

**Suggestion**: 改为延迟初始化或 lazy property。

---

#### L-002: `ccc-engine.py` 用 importlib 加载 ccc-board.py

```python
_spec = _importlib_util.spec_from_file_location("ccc_board", _ccc_board_path)
ccc_board = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(ccc_board)
```

**Why**: 因为文件名含连字符无法用常规 import。如果改文件名为 `ccc_board.py`（或用 `__init__.py` 包），就不需要 importlib hack。

---

#### L-003: 大量函数内 import

```python
# ccc-board.py:1053
def dev_role():
    import subprocess as sp  # 函数内 import

# ccc-board.py:1931
def tester_role():
    import subprocess as sp
```

**Why**: Python 函数内 import 有微小性能开销，且让依赖关系不清晰。

**Suggestion**: 统一到文件顶部 import。

---

#### L-004: `now_iso` 时区不一致

`ccc-board.py` 用 `Asia/Shanghai`，`_board_store.py` 用 UTC。时间戳比较时可能出问题（虽然 ISO 8601 带时区信息，但代码中有 `.replace("Z", "+00:00")` 等手动转换）。

---

#### L-005: 测试文件命名不统一

```
test_ccc_status_smoke.py    # smoke 测试
test_opencode_pool_max_parallel.py  # 功能测试
test_advisory_lock.py       # 红线测试
test_phase_end_to_end.py    # E2E 测试
```

**Suggestion**: 统一前缀规范：`test_unit_*`, `test_integration_*`, `test_e2e_*`。

---

## 红线检查清单

| 红线 | 状态 | 说明 |
|------|------|------|
| R-04 | ✅ 通过 | reviewer 有 advisory lock (O_CREAT\|O_EXCL) |
| R-07 | ✅ 通过 | phases.json 用 fcntl.flock(LOCK_EX) |
| R-08 | ❌ 违反 | 大面积 print() 冒充日志 |
| R-09 | ✅ 通过 | GET /api/* 走 _verify_auth() |
| X1 | ✅ 通过 | opencode-pool Semaphore(3) |
| X2 | ✅ 通过 | try/finally + killpg 级联 |
| X7/R-12 | ✅ 通过 | medium/large LLM fallback → quarantine |

---

## 值得表扬的设计

1. **phase 依赖循环检测** (`_detect_phase_cycle`): DFS 三色标记算法正确，能检测复杂循环依赖
2. **advisory lock** (R-04): O_CREAT|O_EXCL 模式简洁有效，macOS 兼容
3. **原子写入** (`_atomic_write`): tmpfile + os.replace，防止部分写入
4. **进程组 kill** (`killpg`): 级联杀 opencode 孙子进程，不留残留
5. **强收敛机制** (PHASE_MAX_ENGINE_ITER): 多轮不收敛时强制 skipped，防死循环
6. **安全防护**: sanitize_id 防路径穿越、_is_path_in_root 验证、prompt 文件 0o600 权限
7. **结构化校验** (`validate_task_jsonl`): 11 条规则 + strict 模式，协议级保障

---

## 修复优先级建议

| 优先级 | Issue | 预估工作量 |
|--------|-------|-----------|
| P0 | C-003: R-08 print → logger 迁移 | 大（3 核心文件） |
| P0 | C-001: `self.workspace` 缺失 | 小（1 行） |
| P0 | C-002: event 文件无锁 | 中 |
| P1 | H-004: quarantine 格式不匹配 | 中 |
| P1 | H-003: 重复函数统一 | 中 |
| P1 | H-002: 错误吞没加日志 | 大（40+ 处） |
| P2 | H-001: 拆分 ccc-board.py | 大（架构重构） |
| P2 | H-005: 读锁优化 | 中 |
| P3 | M-* 系列 | 各小 |

---

## 对抗性审查补充 (2026-07-12 18:40)

### 修复验证结果

| Issue ID | 修复状态 | 验证结果 |
|----------|----------|----------|
| C-001 | ✅ 已修复 | `self.workspace` 在 `__init__` 中显式保存 |
| C-002 | ✅ 已修复 | `_record_event` 改用 read-modify-write + atomic_write |
| C-003 | ✅ 已修复 | 创建 `_logger.py`，ccc-board.py / _board_store.py 已迁移到 logger |
| H-003 | ✅ 已修复 | 创建 `_utils.py` 统一 sanitize_id / now_iso，时区统一为 UTC |
| H-004 | ✅ 已修复 | 创建 `_iter_quarantine_entries` 辅助函数，兼容文件/目录 |
| H-005 | ✅ 已修复 | `list_tasks` 取消排他锁，新增 `list_tasks_locked` 变体 |

### 对抗性审查发现新问题

**🔴 N-001: quarantine note 字段 None 检查错误** (已修复)

- **文件**: `scripts/_board_store.py:597-600`
- **问题**: `"note" in task` 检查的是 key 是否存在，但 `task.get("note")` 可能返回 `None`。当 task 中有 `"note": None` 时，条件分支走到 `else`，导致 `None += "\n..."` 报错。
- **修复**: 改为 `if not task.get("note"):` 检查值是否为空。

### 验证证据

```bash
# 编译检查
python3 -m compileall -q . # ✅ 0 errors

# 一致性检查
now_iso 一致性: True
sanitize_id 一致性: True

# API 检查
FileBoardStore API OK!
quarantine with None note OK!
```

---

## 下一步

1. **立即修复** C-001（1 行代码）和 H-004（quarantine glob 模式）
2. **本周内** 创建 `_logger.py`，迁移 ccc-board.py 的 print → logger
3. **下周** 统一 `sanitize_id` / `now_iso` 到 `_utils.py`
4. **中期** 规划 ccc-board.py 拆分

> 审查者签名: 火眼眼 👁️  
> 时间戳: 2026-07-12T00:20:00+08:00
