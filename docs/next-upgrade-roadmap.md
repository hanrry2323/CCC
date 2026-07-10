# CCC v0.21/v0.22 → v0.23 升级路线图

> 基于 hp-kb 知识库经验（V9 Review Standard / Charter / Loop Engineering / Fact Reset）与当前代码状态的交叉分析。
> 优先级分三级：P0（必做）、P1（建议做）、P2（可选）。

---

## 附录：CCC 执行模型深度分析

### 当前串行/并行模型

**引擎模型**（`ccc-engine.py`）：
- **串行驱动**：任何时刻只维持 1 个 `in_progress` 任务，engine_loop 串行轮询驱动 backlog→released
- **并行潜力**：多个 task 的 opencode-runner.sh 子进程是独立的 shell 进程（Popen + start_new_session=True），但 engine 不并行调度，而是串行检查 status
- **关键结论**：**逻辑串行，物理并行**（多任务可同时跑，但 engine 一次只盯一个）

---

### 卡死/失败场景分析（20 个 planned 任务）

#### 场景 1：第 5 个任务卡死（opencode 挂起）

| 时间轴 | 行为 |
|--------|------|
| t0 | engine 启动 task-5（in_progress） |
| t1 | task-5 的 opencode-runner.sh 跑飞（死循环、无限等待） |
| t2 | engine 每 3s 轮询 check_complete，task-5 状态持续 `running` |
| t3 | _check_stale() 扫描到 task-5 updated_at > cfg.max_stale_hours（默认 6h） |
| t4 | task-5 → abnormal（隔离），engine 继续检查 planned |

**结论**：不会卡死队列。stale 机制默认 6h 后自动隔离。

---

#### 场景 2：第 5 个任务失败（exitcode ≠ 0）

| 时间轴 | 行为 |
|--------|------|
| t0 | engine 启动 task-5 |
| t1 | opencode-runner.sh 完成，exitcode=1 |
| t2 | engine check_complete 发现 failed，retry=1 |
| t3 | 启动 relaunch，重试 |
| t4 | 重试 MAX_RETRY 次（默认 3）全部失败 → quarantine |

**结论**：失败任务最多重试 MAX_RETRY 次（3 次），然后隔离到 abnormal，后续任务继续。

---

#### 场景 3：第 5 个任务依赖 task-1 完成

**当前问题**：引擎不感知任务依赖关系，只按 board 顺序执行。如果 task-5 的 plan 依赖 task-1 的输出，但 task-1 卡死，task-5 会照常启动，最终因缺失依赖而失败。

**潜在改进**：在 `dev_role_launch` 前检查依赖列：
```python
# 拓扑排序 + 依赖检查
def _check_dependencies(task):
    deps = task.get("depends_on", [])
    for dep_id in deps:
        if not _task_completed(dep_id):
            return False, f"依赖 {dep_id} 未完成"
    return True, None
```

---

### 当前机制总结

| 维度 | 现状 |
|------|------|
| **调度模型** | 串行引擎（一次一个 in_progress） |
| **子进程模型** | 并行执行（Popen start_new_session=True） |
| **失败恢复** | 重试 3 次 → quarantine |
| **卡死检测** | stale 机制（默认 6h）→ abnormal |
| **依赖感知** | ❌ 不感知 |
| **并行调度** | ❌ 不支持多个 in_progress |

---

### v0.23 建议：有限并行

**目标**：保留引擎串行调度的稳定性，同时允许多任务并行执行（依赖满足前提下）。

**方案 A：并行度 3 + 依赖检查**
1. 允许最多 3 个 `in_progress` 任务并行
2. 每次从 planned 取任务前，检查依赖是否都 → verified/released
3. 用 `asyncio.Semaphore(3)` 控制并发

**方案 B：优先级队列 + 拓扑排序**
1. planned 按拓扑排序（依赖靠前）
2. engine 串行调度，但依赖满足的任务可并行启动

**推荐**：方案 A 简单可控，适合 v0.23。

---

## P0 — 必须修

### U1. 删除重复 audit 触发块 + 死函数

**现状问题**：`ccc-engine.py` 中 audit 触发逻辑出现在两个分支里：
- 第 167-176 行：idle 分支内（无活跃 task 且无 planned 时）
- 第 187-194 行：主循环末尾（每次 tick 都检查一次）

两段做同一件事——调用 `audit_role()`——但主循环版本在有活跃 task 时也会跑 audit（虽然 `_audit_should_run` 会拦，但逻辑不清晰）。

`_audit_record_run()` 是空函数（pass），是死代码。

**知识库对照**：V9 Charter 明确要求「零死代码」；V9 Review Standard 的 4 red line 之一是「不动 core」。

**修复方案**：
```python
# 合并为单一入口，只在 idle 分支触发
if running_task_id is None:
    _check_stale()
    _write_heartbeat(workspace, None)
    if _audit_should_run():
        engine_log("触发 audit_role（全项目扫描）")
        try:
            ccc_board.audit_role()
        except Exception as exc:
            engine_log(f"audit_role 异常: {exc}")
    time.sleep(cfg.engine_idle_sleep)
    continue  # 跳过主循环末尾的重复检查
```
删除 `_audit_record_run()` 和主循环末尾的重复块。

---

### U2. 修复 N1：`_audit_post_backlog` 缺少 workspace 存在性检查

**现状问题**：`_audit_post_backlog` 直接用 `cfg.workspace` 创建 backlog task，未检查该目录是否存在或可写。多 workspace 场景下，如果某个 workspace 不存在，会抛异常导致整个 audit 中断。

**知识库对照**：V9 Review Standard 的「业务不混 core」原则——audit 不应因 workspace 缺失而崩溃。

**修复方案**：
```python
def _audit_post_backlog(...):
    n = 0
    for ws in cfg.audit_workspaces:
        ws_path = Path(ws)
        if not ws_path.exists():
            engine_log(f"跳过不存在的 workspace: {ws}")
            continue
        if not os.access(ws_path, os.W_OK):
            engine_log(f"跳过不可写的 workspace: {ws}")
            continue
        # ... 原有逻辑
```

---

### U3. 修复 N3：mypy 报告截断

**现状问题**：audit report 中的 mypy 输出被截断（可能是终端宽度限制或字符串长度限制），长输出丢失关键信息。

**修复方案**：写入文件而非打印到 stdout，或使用 `rich` 面板自动换行。

---

## P1 — 建议做

### U4. reviewer_role 按变更量分级审查（动态审项）

**现状问题**：reviewer_role 对所有变更统一走完整 LLM 语义审查，无论变更大小。小改动（<10 行）花同样的时间和 token。

**知识库对照**：V9 Review Standard 明确规定「动态审项 by change volume」：
- ≤10 行 → 快速语法检查（git diff | grep -E）+ 必要警告
- 10-50 行 → LLM 语义审查（当前行为）
- >50 行 → 完整审查 + impact radius 分析

**修复方案**：
```python
def _review_by_volume(diff_text: str) -> dict:
    lines = len(diff_text.splitlines())
    hunks = sum(1 for block in diff_text.split('\n@@') if block.strip().startswith('+'))
    total_changes = sum(len(h.split('\n')) for h in hunks)
    
    if total_changes <= 10:
        return _quick_syntax_check(diff_text)  # 仅 warning，不走 LLM
    elif total_changes <= 50:
        return _llm_review(diff_text)  # 当前行为
    else:
        return _full_review(diff_text)  # + impact analysis
```

**预期收益**：日常小改动审查时间从 ~30s LLM 调用降到 <2s，token 消耗降低 80%+。

---

### U5. audit 多 workspace 并行化

**现状问题**：当前 audit 串行遍历 `cfg.audit_workspaces`，每个 workspace 单独调 `_audit_recent_commits`、`_audit_lint`、`_audit_classify`。5 个 workspace 就是 5 倍串行时间。

**知识库对照**：Loop Engineering 指出「Workflow 模式适合单线程引擎，但多 workspace 审计天然并行」。

**修复方案**：
```python
async def _audit_workspace(ws: str) -> AuditResult:
    """单个 workspace 审计（轻量，纯本地操作）"""
    commits = await run_cmd(["git", "-C", ws", "log", "--since=2h", "--oneline"])
    lint_result = run_cmd(["ruff", "check", "--fix", "--exclude", "src", "."], cwd=ws)
    return classify(commits, lint_result)

async def audit_all_workspaces():
    tasks = [_audit_workspace(ws) for ws in cfg.audit_workspaces]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return aggregate(results)
```

注意：`audit_role()` 本身需要写 board（JSONL + fcntl 锁），这部分仍需串行。建议将「读 git log + ruff lint + AI 分类」拆成异步，只把最终结果同步写入 board。

---

### U6. I3 决策数据化

**现状问题**：second review 发现的 N4：I3 声称「投入产出比不高」，但没有 benchmark 数据支撑。

**修复方案**：在 audit report 中增加计时统计：
```python
import time
t0 = time.monotonic()
# ... audit work ...
elapsed = time.monotonic() - t0
report["timing"] = {"total": elapsed, "per_workspace": {}}
```
同时记录每次 audit 的实际 token 消耗（通过 LLM API response usage field），用于后续 ROI 分析。

---

## P2 — 可选优化

### U7. LLM 调用容错层

**现状问题**：`claude -p` 调用 `127.0.0.1:4000` relay 无重试、无熔断。120s 超时硬编码，不同任务类型不需要同样长的超时。

**改进方向**：
- 超时自适应：简单任务 60s，复杂任务 180s
- Relay 失败时 fallback 到本地模型（如 Ollama）做基础语法检查
- 添加 circuit breaker：连续 3 次失败后暂停 5 分钟再试

---

### U8. Fact Reset 模式应用到 progress.md / findings.md

**现状问题**：`progress.md` 和 `findings.md` 没有结构化的事实重置机制。每次升级后这些文件的状态不清晰。

**知识库对照**：hp-kb v19 master fact-reset 模式——master-baseline.md + STATE.md + BASELINE.md + INDEX.md 四件套同步更新。

**适配方案**（简化版）：
```markdown
<!-- progress.md -->
## Last Updated: 2026-07-09T12:00:00Z
## Version: v0.22.x
## Changelog:
- v0.22.1 (2026-07-09): U1-U3 修复计划
```

---

## 升级顺序建议

```
v0.23.0 (bug fix + 稳定性)
├── U1: 删除重复 audit 块 + 死函数
├── U2: 修复 N1 workspace 检查
└── U3: 修复 N3 mypy 截断

v0.23.1 (效率提升)
├── U4: reviewer_role 分级审查
└── U6: I3 决策数据化

v0.23.2 (架构演进)
├── U5: audit 多 workspace 并行化
└── U7: LLM 容错层

v0.23.3 (维护性)
└── U8: Fact Reset 模式
```

---

*生成时间：2026-07-09 | 基于 hp-kb V9 Review Standard / Charter / Loop Engineering / v19 fact-reset*
