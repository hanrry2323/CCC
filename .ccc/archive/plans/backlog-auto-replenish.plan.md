# Plan: backlog-auto-replenish — backlog 为空时自动触发 audit_role 补充

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

- **入口/核心文件**：`scripts/ccc-engine.py`（Engine 主循环 + `_audit_should_run` + `_process_backlog`）、`tests/scripts/test_audit_role.py`（已有 audit 测试集）
- **当前结构要点**：
  1. Engine 主循环（`ccc-engine.py:1385-1409`）：先消费 `planned`（dev_role）→ 无可消费时从 `backlog` 取 via `_process_backlog` → 两者都空时 `did_something=False`，break 进入空闲模块
  2. 空闲模块（`ccc-engine.py:1411-1461`）：当 `not active_tasks` 时逐个 workspace 检查 `_audit_should_run(str(ws))`。该函数有 2h 硬间隔（`ccc-engine.py:1487-1504`），导致 backlog+planned 都空时 Engine 要等最多 2h 才触发 audit_role 去补充任务
  3. `_process_backlog`（`ccc-engine.py:608-679`）只是消费已有 backlog item（调 `product_role` 拆 plan），**不负责生成新任务**——生成新任务靠 `audit_role`（`ccc-board.py:3024`）扫描 git diff 产生
  4. `audit_role` 自身会写 `~/.ccc/audit-last-run.<ws>.json` 时间戳；`_audit_should_run` 依赖该文件判断是否该跑——这是 2h 等待的根源
- **待改动点**：
  - `scripts/ccc-engine.py`：
    - 新增模块级变量 `_last_empty_replenish`（per-workspace 冷却，避免空转时无限触发 audit_role）
    - 新增 `_auto_replenish_backlog()` 函数（在 `_process_backlog` 附近）
    - 在空闲模块 (L1432 之后) 插入调用
  - `tests/scripts/test_audit_role.py`：
    - 追加 4 个测试（触发 / backlog 不空跳过 / planned 不空跳过 / cooldown）

---

## 范围

- **目标**：backlog + planned 都为空时，立即触发 audit_role 补充新任务，不再依赖 2h 定时窗口
- **只改文件**：`scripts/ccc-engine.py`，`tests/scripts/test_audit_role.py`
- **不改文件**：`scripts/ccc-board.py` 及任何其他文件不动
- **执行方式**：`manual`
- **Phase 数**：1

---

## 改动 1：backlog+planned 为空时自动补充

### 做什么

Engine 空闲时（`not active_tasks`），当前只依赖 `_audit_should_run`（2h 间隔）触发 audit_role。如果 backlog 和 planned 列都为空，Engine 可能空转 2h 才有新任务进来。

改为：在空闲模块中，`_audit_should_run` 正常检查之后，额外判断 backlog + planned 是否都为空。如果都为空，立即调用 `ccc_board.audit_role(workspace=str(ws))`，不受 2h 定时限制。同时加 per-workspace 5min 冷却，避免 audit_role 连续空转（空项目、无 git 变更等场景）。

### 怎么做

**1. 模块级变量**（`scripts/ccc-engine.py`，约 L99，紧随 `PHASE_PARALLEL_DISABLED` / `_stores` / `_parallel_phases` 之后）：

```python
# backlog+planned 为空时的补充冷却（per-workspace，单位秒）
_last_empty_replenish: dict[str, float] = {}
```

**2. 新增函数**（放在 `_process_backlog` 之后、phase 并行调度之前，约 L681）：

```python
def _auto_replenish_backlog(ws: Path, store, program_dir: Path) -> bool:
    """backlog + planned 都为空时，立即触发 audit_role 补充新任务。
    
    绕过 _audit_should_run 的 2h 间隔，但有 5min per-workspace 冷却
    避免 audit_role 在无变更的项目上空转。
    
    Returns: True 表示触发了 audit_role
    """
    if store.list_tasks("backlog"):
        return False
    if store.list_tasks("planned"):
        return False
    
    now = time.time()
    ws_key = str(ws)
    last = _last_empty_replenish.get(ws_key, 0.0)
    if now - last <= 300:
        return False
    
    _last_empty_replenish[ws_key] = now
    label = _ws_label(ws, program_dir)
    engine_log(f"[{label}] backlog+planned 均为空，立即触发 audit_role 补充")
    try:
        ccc_board.audit_role(workspace=str(ws))
    except Exception as exc:
        engine_log(f"[{label}] audit_role 异常: {exc}")
    return True
```

**3. 空闲模块插入调用**（`scripts/ccc-engine.py` L1432 之后、L1434 `_retry_abnormal_dev_failures` 之前）：

```python
                    # backlog+planned 为空时立即补充（绕过 2h 间隔，5min 冷却）
                    _auto_replenish_backlog(ws, _store2, program_dir)
```

注：`_store2` 已在 L1416 `_get_store(ws)` 获得；`program_dir` 已在 L1253 定义，在本作用域内可用。

### 验收清单

- [ ] 验收条件 1：backlog 和 planned 都为空时，`_auto_replenish_backlog` 调用了 `ccc_board.audit_role`
- [ ] 验收条件 2：backlog 不为空时，跳过 audit_role
- [ ] 验收条件 3：planned 不为空时，跳过 audit_role
- [ ] 验收条件 4：5min 冷却期内重复调用不会再次触发 audit_role
- [ ] 边界场景：刚恢复的 workspace 没有 .ccc/board/ 目录（`store.list_tasks` 返回 `[]`，触发 audit_role）
- [ ] 错误处理：`audit_role` 抛异常时被捕获，Engine 不崩溃
- [ ] 安全相关：无

### 验收

- [backlog 空触发] `uv run pytest tests/scripts/test_audit_role.py -k test_replenish_triggers -v` PASSED
- [backlog 不空跳过] `uv run pytest tests/scripts/test_audit_role.py -k test_replenish_skips -v` PASSED
- [cooldown 生效] `uv run pytest tests/scripts/test_audit_role.py -k test_replenish_cooldown -v` PASSED
- [全绿] `uv run pytest tests/scripts/test_audit_role.py -v` 全部 PASSED（原有 10 + 新增 4 = 14）
- [编译通过] `python3 -m compileall -q scripts/ccc-engine.py tests/scripts/test_audit_role.py`

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 新增 `_auto_replenish_backlog` + 空闲模块调用 + 4 个测试 | `feat(engine): backlog+planned 为空时自动触发 audit_role 补充 (phase 1/1)` |

---

## 全局验收清单

- [ ] 编译零错误（`python3 -m compileall -q scripts/ccc-engine.py tests/scripts/test_audit_role.py`）
- [ ] `test_audit_role.py` 全部 14 test passed
- [ ] diff 范围仅限白名单 2 个文件
- [ ] 1 个 commit（phase 1/1）
- [ ] phases.json 与 plan phase 数一致（1 phase）
- [ ] Plan 中所有验收意图全部达成

---

## 后续步骤

无。单 phase 改动，部署后 Engine 重启即可生效。无需迁移或配置变更。