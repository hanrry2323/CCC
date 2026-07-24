# 2026-07-24 Test-Repair 交付总结

**状态**：✅ 完成  
**基线 commit**：`8dee4c6`（41 个稳定性 commit）  
**修复 commit**：本次提交  
**生产代码改动**：0 行  
**测试改动**：10 个文件，+150 / -73

---

## 1. 问题背景

今日 41 commit 稳定性工程（`8dee4c6..HEAD`）拆分了 `ccc-engine.py` 与 `ccc-board.py`：

- `ccc-engine.py` 4691 → 3333 行（−29%），新增 7 个 `engine/*` 子模块（restart_log, tick, process, upstream, notify, task_registry, discover）
- reviewer / dev helpers 从 `ccc-board.py` 迁到 `board/roles/{reviewer,dev}.py`
- 闸门收紧：`validate_transfer_payload` 强制 allowlisted intent probe；`_workspace_isolation.require_cwd` 严格

测试树分两处：

- `tests/scripts/`（102 文件，**全绿**）
- `scripts/tests/`（37 文件，**25 个红**）
- `tests/integration/test_intake_pipeline.py` collection crash（**+14 解锁**）

合并跑：23 failed / 973 passed（compact 摘要误差，精确数字为 **25 red + 1 collection crash = 26 problems**）。

---

## 2. 根因分类（5 类）

| 类别 | 数量 | 描述 |
|---|---|---|
| **A. Refactor-orphan 符号** | 13 | 测试 import 老模块后访问已迁移/重命名的私有符号（`AttributeError`） |
| **B. Intent probe 新规未同步 fixture** | 5 | `validate_transfer_payload` 拒绝缺 allowlisted probe 命令的 acceptance/plan |
| **C. 环境/路径硬编码** | 3 | `_WS = "/Users/apple/program/xianyu"` 在测试机上不存在 |
| **D. Skill 发现失效** | 1 | `discover_skills()` 默认 `include_engine=False`，隐藏 `ccc-dev` |
| **E. 行为/常量漂移** | 7 | `sys.modules` 漏注、re-export 引用快照、`from X import name` 不响应 monkeypatch、commit-gate DoD 行为变更、prompt 文案精简、role_lock 强制校验 |

---

## 3. 修复方案（3 批）

### Batch 1 — Refactor-Orphan 符号重定向（11 tests）

13 个 AttributeError，把 `engine._xxx` / `board._xxx` 重定向到：

- `engine.tick._loop_heartbeat_path`、`engine.tick._last_tick_mono`
- `engine.upstream._health_cache`
- `board.roles.reviewer._reviewer_fallback_mode`、`_apply_reviewer_llm_fallback`
- `board.roles.dev._capture_task_pre_head`、`_require_task_commit_for_testing`、`_find_task_commit_hash`

**意外发现**：`test_commit_gate_rejects_without_task_commit` 实际是 **真业务变更** —— `_require_task_commit_for_testing` 从"必须显式提交"改为"工作区干净时 DoD auto-commit"（`scripts/board/roles/dev.py:548-588`）。更新断言以对齐新行为。

### Batch 2 — Fixture / 行为漂移（13 tests，6 文件）

| 子项 | 文件 | 改动 |
|---|---|---|
| 2A intent probe | test_desktop_api.py + test_desktop_transfer_gate.py | 5 处 `acceptance` / `plan_md` 改用 allowlisted probe（`python3 -m pytest` / `pytest tests/ -q`） |
| 2C tmp_path | test_dev_prompt_v411.py | `_WS` 全局硬编码 → 3 处 `tmp_path` 注入；`include_engine=True` |
| 2D sys.modules | test_engine_concurrency_caps.py + test_product_inflight_cap.py | `_load_engine()` 末尾 `sys.modules.setdefault("ccc_engine", mod)` |
| 2E re-export | test_product_inflight_cap.py | 23 处 `engine._product_inflight` 改走 `engine.task_registry._product_inflight`（直访源模块） |
| 2F monkeypatch seam | test_engine_concurrency_caps.py + test_review_lock_stale.py | 直访 `_tr.git_head_for_task` / `_reviewer.get_workspace`（不在 `_ctx` 上 patch） |

### Batch 3 — Collection Crash Shim（13 tests 解锁）

`tests/integration/test_intake_pipeline.py:21` collection 阶段 `AttributeError: 'ccc_board' has no attribute '_classify_task_intake'`。`_classify_task_intake` / `_intake_failsafe` 在 `board/roles/audit.py`，`ccc-board.py:348-353` 未 re-export。

**修复**：测试仅 shim 到 `board.roles.audit`，**零生产 shim**。

---

## 4. 关键发现（维护备忘）

### 4.1 `from X import name` 拷贝本地命名空间

```python
# scripts/board/roles/reviewer.py:27
from board.context import get_workspace

# 测试不能 monkeypatch 源：
monkeypatch.setattr(_ctx, "get_workspace", lambda ws)  # ✗ 不生效
# 必须 patch 下游模块：
monkeypatch.setattr(_reviewer, "get_workspace", lambda ws)  # ✓
```

### 4.2 `importlib.util.spec_from_file_location` 不自动注册 `sys.modules`

```python
spec = importlib.util.spec_from_file_location("ccc_engine_caps", "ccc-engine.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
# engine.active_tasks._eng() 通过 sys.modules 找 "ccc_engine"，找不到
# 必须 setdefault：
sys.modules.setdefault("ccc_engine", mod)
```

### 4.3 `from X import global_dict` 是引用快照

```python
# scripts/engine/task_registry.py
_product_inflight: dict = {}    # module-level

def rebuild_product_inflight(...):
    global _product_inflight
    _product_inflight = rebuilt   # 重绑 task_registry 自己的变量

# engine._product_inflight = task_registry._product_inflight   ← 拷贝引用
# rebuild 后 engine._product_inflight 仍指向旧 dict！
# 测试必须直访源模块：
from engine import task_registry as _tr
_tr._product_inflight.keys()
```

### 4.4 `VERIFY_CMD_ALLOW_PREFIXES` 是 startswith 匹配

`scripts/_intent_probe.py:18-40` 用 `startswith`：
- ✅ `"pytest "`（带空格+路径）
- ✅ `"python3 -m pytest"`
- ❌ `"pytest"`（单独）

### 4.5 `assert_role_executor` 强制校验

`reviewer_role()` 入口 `assert_role_executor("reviewer", "claude-code")` 会抛 `RoleLockViolation`。测试需 `CCC_ROLE_LOCK_BYPASS=1`。

### 4.6 DoD Auto-Commit

`scripts/board/roles/dev.py:548-588`：`_require_task_commit_for_testing` 工作区干净但缺 task_id commit 时**先自动 commit** 再验收。原测试期望"拒绝"已过时。

### 4.7 Prompt 文案精简

"弱模型友好"字面量在 v0.41.1 后期文案精简中已移除。原断言已 outdated。

---

## 5. 行为变更摘要（test-only）

| 测试 | 重构前期望 | 重构后实际 | 对齐方式 |
|---|---|---|---|
| `test_commit_gate_rejects_without_task_commit` | ok=False | ok=True（DoD auto-commit） | 更新断言 |
| `test_prompt_includes_scope_and_pytest_fail` | 含"弱模型友好" | 不含 | 删除该 assertion |

---

## 6. 验证

```bash
python -m pytest scripts/tests/ tests/scripts/ tests/integration/
# 1016 passed, 2 skipped in 111.67s

ruff check scripts/ tests/
# All checks passed!

python -m py_compile scripts/ccc-engine.py
# OK
```

**生产代码 0 改动**：`git diff --stat` 仅显示 10 个测试文件。

---

## 7. 修复文件清单

```
scripts/tests/test_engine_tick_watchdog.py        +6 / -1
scripts/tests/test_pipeline_fixes_v401.py        +12 / -7
scripts/tests/test_pipeline_gates_h1_h2.py       +34 / -18
scripts/tests/test_desktop_api.py                +4 / -4
scripts/tests/test_desktop_transfer_gate.py      +2 / -2
scripts/tests/test_dev_prompt_v411.py           +20 / -12
scripts/tests/test_engine_concurrency_caps.py   +12 / -4
scripts/tests/test_product_inflight_cap.py      +34 / -21
scripts/tests/test_review_lock_stale.py         +15 / -7
tests/integration/test_intake_pipeline.py        +5 / -3
```

合计 **+150 / -73**，10 文件。

---

## 8. 维护 runbook（供后续）

**未来若再加 `engine/*` 子模块**：

1. 顶层 re-export 在 `ccc-engine.py:200-260`（当前 7 个全局 + 7 个函数）
2. 私有 helpers（如 `_xxx`）只在子模块本地，不 re-export
3. 测试访问私有 helpers 时：**直访子模块**，不要走 re-export

**若测试 importlib 加载 `ccc-engine.py`**：

```python
sys.modules.setdefault("ccc_engine", mod)   # 让 _eng() 找到
```

**若测试修改 `module_level_dict`**：

```python
from engine import task_registry as _tr   # 直访源模块
_tr._product_inflight.clear()            # 不用 engine._product_inflight
```

**若测试调用 `reviewer_role()` / `product_role()`**：

```python
monkeypatch.setenv("CCC_ROLE_LOCK_BYPASS", "1")  # 跳 assert_role_executor
```

**若 fixture 涉及 workspace**：

- 用 `tmp_path` 而非硬编码路径
- `require_cwd` 严格校验"必须是已存在目录"，不要求 `.ccc/` 子目录

**若 fixture 涉及 intent probe**：

- 用 `python3 -m pytest` 或 `pytest tests/ -q`（allowlist startswith 匹配）
- 单独 `pytest` / `grep` / `x` 不被接受

---

## 9. 后续 deferred（不在本次范围）

- CHANGELOG.md 补 `Unreleased` 段（审计 + 拆分 + test-repair 三阶段汇总）
- commit message 加 `ccc-task-id=` 标记（流程红线回归）
- ccc-engine.py 剩余 3333 行（如未来要进一步拆分，需先引入 context 对象）
- scripts/tests/ 与 tests/scripts/ 双目录统一（路径漂移历史包袱）

---

**结论**：25 个红测试 + 1 个 collection crash 全部修复；1016 passed / 2 skipped / 0 failed；零生产代码改动。工程可立即合入 main。