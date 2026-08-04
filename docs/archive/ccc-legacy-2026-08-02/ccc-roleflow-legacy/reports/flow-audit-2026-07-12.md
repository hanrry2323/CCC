# CCC 全流程审计 — 老板 2026-07-12 要求

> 老板原话：任务拆分规则你搞定没有？后面就是我给你任务，你来拆分，
> 任务自动执行、审查、纠错、学习飞轮、定时 diff 审查，自动修复，自动进队列。
> 流程你梳理一下。

## 7 段流程落地表

| # | 段 | 状态 | 实现位置 | 触发方式 | 断点 |
|---|----|------|----------|----------|------|
| 1 | **任务拆分**（plan + phases） | ✅ 通 | `ccc-board.py:957 product_role` | `python3 ccc-board.py product --promote <task_id>` | engine 不调 product_role，backlog 不会自动进 planned |
| 2 | **任务自动执行**（dev） | ✅ 通 | `ccc-board.py:1051 dev_role` + `opencode-runner.sh` + `opencode-exec.py` | engine 主循环 in_progress + planned → 启动 opencode | 变更太大（>50 行）large-class LLM 容易 timeout |
| 3 | **审查**（reviewer + tester） | ✅ 通 | `ccc-board.py:1811 reviewer_role` / `1985 tester_role` | dev 完成 → engine 串行触发 | LLM fallback 强制 quarantine (R-12 红线)，小变更走 py_compile pass |
| 4 | **纠错**（retry / quarantine） | ✅ 通 | `dev_role` retry + `_quarantine()` | dev 失败重试 5 次 → quarantine 落 abnormal | reviewer quarantine 路径走 LLM 失败 + 1538 行变更 timeout |
| 5 | **学习飞轮** | 🟡 半通 | `flywheel-scan.sh`（grep 模式）/ `audit_role`（LLM 分类） | flywheel-scan plist 每日 02:00 / audit engine idle 2h | flywheel-scan 只生成候选不写 red-lines（红线 18 强制人工 review） |
| 6 | **定时 diff 审查** | ✅ 通 | `audit_role` + `_audit_should_run(2h)` | engine idle 时检查，2h 间隔 | 跑全项目 git log + ruff + mypy + 报表，单 ws 120s timeout |
| 7 | **自动修复 + 自动进队列** | 🟡 半通 | `audit_role`（auto fix 直修 / 投 backlog）+ `dev_role`（engine 自动消费 planned） | audit 触发后自动写修复 | AGENTS.md 建议走 approve-agents 角色（人工 + 工具配合），不是全自动 |

## 流程图（端到端）

```
[老板发任务]
     │
     ▼
[手工] python3 ccc-board.py product --promote <task_id>
     │
     │  product_role 调 Claude API 拆 plan.md + phases.json
     │  fallback: _generate_fallback_plan（API 不可用时）
     ▼
[backlog] ──── 断点：engine 不消费 backlog ────
     │
     │  ⚠️ 当前必须手工 product --promote
     │
     ▼
[planned]  ← 手工 create_task + 写 plan + phases 后也在此
     │
     │  engine 主循环每 5s 检查 planned
     │  有 plan + phases → dev_role 启动 opencode
     │  缺 plan/phases → quarantine (log: 'engine relaunch: 缺 plan 或 phases 文件')
     ▼
[in_progress]
     │
     │  opencode 跑（loop/code → 4002 → xfyun-code，~40s for small change）
     │  .done / .exitcode 持久化
     │  PID 文件 /Users/apple/program/CCC/.ccc/pids/<task_id>.pid
     │
     ▼ (engine 下一轮轮询 .done 存在)
[testing]
     │
     │  reviewer_role: 取 git diff → _classify_review_size
     │    small (≤10行): py_compile 静态 pass
     │    medium (10-50行): LLM 审查
     │    large (>50行): LLM + impact 分析
     │  size_class=unknown 或 LLM 不可达 → quarantine (R-12 红线)
     │
     │  tester_role: 跑 plan.md ## 验收清单 命令
     │    没写 verify_commands → 静默通过（不动 board）
     │    失败 → 留 testing 下轮 retry
     │
     ▼ (reviewer + tester 都通过)
[verified]
     │
     │  kb_role: 写 CHANGELOG.md + 收集 AGENTS.md 建议 + git tag
     │
     ▼
[released]
     │
     │  regress_role 每日回测
     │    py_compile 全项目（提到循环外 v0.28.0）
     │    git diff HEAD --stat
     │    失败 → 创建 regression-<task>-<date> bug 任务到 backlog
     ▼
[regression bug → backlog] → 回到 planned → dev → ...

[持续后端]
  audit_role (engine idle, 2h 间隔)
    - 全项目 git log + ruff + mypy + 报表
    - auto fix 直修 / review/decision 投 backlog
  flywheel-scan (launchd 每日 02:00)
    - grep .ccc/reports/ + verdicts/ 失败模式
    - 写 flywheel-candidate-<date>.md 候选清单
    - 人工 review 后才合并到 references/red-lines.md（红线 18）
```

## 关键资产

| 路径 | 角色 |
|------|------|
| `scripts/ccc-engine.sh` + `ccc-engine.py` | Engine 入口 + 主循环 (launchd KeepAlive) |
| `scripts/ccc-board.py` | 7 角色：product/dev/reviewer/tester/ops/kb/regress |
| `scripts/_board_store.py` | FileBoardStore (atomic write + O_EXCL lock) |
| `scripts/opencode-exec.py` | opencode 子进程封装 (loop/code → 4002) |
| `scripts/opencode-runner.sh` | 持久化 .done / .exitcode |
| `scripts/ccc-board-server.py` | HTTP API (board-server, launchd KeepAlive) |
| `scripts/audit_role` (ccc-board.py 内) | 全项目审计 (engine idle 触发) |
| `scripts/flywheel-scan.sh` | 失败模式 grep（每日 02:00） |
| `scripts/board-reconcile.py` | zombie 副本清理 |
| `scripts/ccc-notify.sh` | L1/L2/L3 桌面通知 + 告警文件 |
| `references/red-lines.md` | 12 + R-04/R-07/R-08/R-09/R-12/R-14 红线约束 |

## launchd 服务（5 个 engine + 1 board + 1 flywheel）

```
com.ccc.engine         → /Users/apple/program/CCC/scripts/ccc-engine.sh
com.ccc.qx-observer.engine
com.ccc.qx.engine
com.ccc.xianyu.engine
com.ccc.qb.engine
com.ccc.board          → 7777 HTTP API
com.ccc.flywheel-scan  → 每日 02:00 跑 flywheel-scan.sh
```

## 4 断点

1. **🔴 backlog → planned 没人推**（engine 不调 product_role）
   - 当前：backlog 任务永远卡住，必须手工 `python3 ccc-board.py product --promote <tid>`
   - 老板要求："我给你任务，你来拆分" — 需要一个 trigger：
     - 选项 A：engine 启动时跑一次 product_role（无人工干预）
     - 选项 B：监听新建文件（如 .ccc/inbox/*.md）自动入 backlog + product_role
     - 选项 C：HTTP 端点 `POST /api/tasks` 直接入 backlog
   - **建议 A**（最轻）：engine idle 时如果 backlog 非空 → product_role() 直到空

2. **🟡 LLM fallback quarantine 太激进**
   - 当前：medium/large 变更 LLM 不可达 → 强制 quarantine
   - 影响：v0280 1538 行变更 + 1500s timeout → 任务失败
   - 改进：timeout 提到 1800s + 退避重试 1 次（v0.28.0 已升级 default_timeout 1800s）

3. **🟡 flywheel 自动写 red-lines 没接**
   - 当前：flywheel-scan 只生成候选，必须人工 review
   - 红线 18 强制：自动合入 = 1 周内回滚
   - 状态：**合规**（红线要求就是这样），但"学习飞轮"对老板来说可能不够"自动"

4. **🟢 AGENTS.md 建议走人工审批**（approve-agents 角色）
   - 老板要求"自动修复" — 当前 kb_role 收集 + 写 pending-agents-suggestions.md + 人工 approve
   - 风险：自动合并可能污染 AGENTS.md
   - 建议：加 7 天冷却 + 多 reviewer 投票再自动合入

## 老板下一步要做的

1. **拍板 backlog 自动消费**：A / B / C 哪个？
2. **审 4 个断点**：要不要现在就改？
3. **拍板"自动修复"范围**：审计 + 飞轮 + AGENTS.md 三段都要全自动？还是保留红线 18 人工 gate？
