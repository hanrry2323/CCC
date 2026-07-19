---
name: ccc-audit
description: CCC 审计工程师 — 跨 workspace 扫描 lint/mypy，分类后自动修或投 backlog
---

# CCC 审计工程师 — ccc-audit

## 阶段与看板（Engine 能力包）

审计工程师是**跨 workspace** 角色，扫描近 N 小时（默认 2h）的 commit + 静态分析结果，按严重度分类处理：可自动修的（`auto`）直接 ruff --fix 提交，需审查的（`review`）也尝试自动修，需要决策的（`decision`）受 intake failsafe 保护后投 backlog。

与单 workspace 角色不同：audit 调度入口是 `_audit_should_run()`（Engine 自动）或 CLI 显式调用，不在 ROLES 字典中（独立分支）。

### 职责边界

| 做 | 不做 |
|---|------|
| 跨多 workspace 并行扫 git log + ruff + mypy | 不审 plan/验收（那是 reviewer） |
| 分类：`auto` / `review` / `decision` | 不修 bug 的根因（只跑 ruff --fix 安全规则） |
| `auto`/`review` 直接 ruff --fix + git commit | 不写 verdict.md（那是 reviewer） |
| `decision` 类受 intake failsafe 保护后投 backlog | 不在 `_ccc_control.may_invent()=False` 时投 backlog |
| 写审计报表 `.ccc/audit-reports/{date}.md` | 不删 released 里的 task |

## 基线流程

1. **取 git log**：`git log --since="2 hours ago" --oneline --no-merges`
2. **lint + mypy 门禁**：
   - `ruff check .`（workspace 根目录）
   - `mypy {src|app|.}`（动态检测 mypy 目标目录）
3. **AI 分类**（启发式，v0.22）：
   - lint 输出含 "error" → `review`
   - lint 输出无 "error" → `auto`
   - mypy 含 "error:" → `review`（取前 5 行前 120 字符）
4. **auto 路径**：`ruff check --fix --exclude src .`（v0.22 安全约束：只改 tests/ + 配置/文档）
5. **review 路径**：`ruff check --fix .`（v0.34 起含 src/，类型标注在源码里）
6. **decision 路径**：
   - intake failsafe 检查（同类 abnormal 占比 > 60% → 熔断）
   - `_ccc_control.may_auto_inject_tasks() AND may_invent()` 守护（v0.42.4 起永久禁用）
   - 通过守护 → 投 backlog；不通过 → 跳过
7. **写报表**：`.ccc/audit-reports/{date}.md`（含 Auto / Auto-Fixed / Review / Decision / Build Gate / mypy 附录）
8. **更新 last-run**：`~/.ccc/audit-last-run.{ws_slug}.json`

## 多 workspace 并发（v0.24.2+）

- 单 ws：串行（保持原行为）
- 多 ws：`ThreadPoolExecutor(max_workers=min(len, 2))`（v0.24.3 OOM 防护，避免 4×(ruff+mypy) 同时跑）
- 单 ws 超时 120s（v0.24.3：单 ws 卡死不阻塞整个 audit 角色）

## evolve 扫描（可选）

`CCC_EVOLVE_ON_AUDIT=1` 且 `may_invent()=True` 时，audit 结束后追加 `_evolve_run_one(ws)` 扫描健康+安全 → 去重排序 → 投 backlog。

**v0.42.3 起**：`INVENT_HARD_DISABLED=True` 使 `may_invent()` 永远 False，evolve 路径永久禁用。

## 红线

- ❌ 在 `may_invent()=False` 时投 backlog（红线：受 invent 硬禁用约束）
- ❌ 跳过 intake failsafe 熔断检查（避免 abnormal 雪崩）
- ❌ ruff --fix 改 scope 外文件（只跑 `--fix`，不写新代码）
- ❌ 跳过 `.ccc/state.md` 读取（红线 10）
- ❌ 不写审计报表（必须落盘 `.ccc/audit-reports/{date}.md`）

## 已知陷阱

- **intake failsafe 阈值 60%**：同类 `audit-{category}` abnormal 占比 > 60% 即熔断；阈值可能过严，需观察
- **mypy 目标目录动态检测**：`src/` → `app/` → `.` 三级 fallback；无 .py 文件时跳过 mypy
- **ruff --fix 安全范围**：v0.22 仅改 tests/+配置；v0.34 起扩到 src/（类型标注场景）
- **mypy 截断**：review 段只取前 5 行 × 120 字符，完整输出在附录（5KB 上限）
- **并发度上限 2**：v0.24.3 修复 OOM，单 ws timeout 120s
- **last-run 文件**：单进程写 `~/.ccc/audit-last-run.{ws_slug}.json`，多 ws 并发时 ws_slug 区分

## CLI 入口

```bash
# 全量 audit（扫所有 WORKSPACES）
python3 scripts/ccc-board.py audit

# 指定 workspace + 时间窗口
python3 scripts/ccc-board.py audit --workspace /path/to/ws --since "4 hours ago"
```

## 代码参考

- `scripts/ccc-board.py` `audit_role()` — 入口（多 ws 并发调度）
- `scripts/board/roles/audit.py` `_audit_run_one(ws, since)` — 单 ws 处理链
- `scripts/board/roles/audit.py` `_audit_lint(ws)` — ruff + mypy 门禁
- `scripts/board/roles/audit.py` `_audit_classify(ws, commits, lint_out, mypy_out)` — 启发式分类
- `scripts/board/roles/audit.py` `_intake_failsafe(ws, category)` — abnormal 熔断
- `scripts/board/roles/audit.py` `_audit_post_backlog(ws, items, category)` — 投 backlog（受 may_invent 守护）
- `scripts/board/roles/audit.py` `_audit_write_report(...)` — 写审计报表
- `scripts/_ccc_control.py` `may_invent()` / `may_auto_inject_tasks()` — invent 守护（v0.42.3 起硬禁用）
