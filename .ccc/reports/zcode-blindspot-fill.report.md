# Executor Report — zcode-blindspot-fill

> **Task**: `zcode-blindspot-fill` (补 zcode-adapter-v121 盲区)
> **Executor UUID**: `50289dbe-3e25-49bd-a04b-c729e2a21a83`
> **Session 来源**: `/Users/apple/program/CCC/.ccc/plans/zcode-blindspot-fill-executor-session-id.txt`
> **日期**: 2026-07-06
> **角色**: Executor (独立 `claude -p` session,通过 `ccc-zcode-bridge.sh` spawn)

---

## 1. 改动清单

| 文件 | 改动 | 类型 |
|------|------|------|
| `.ccc/reports/zcode-blindspot-fill.report.md` | 新建(本文件) | Executor 产物 |
| **源代码改动** | **0** | — |

**白名单遵守**: 仅写 `.ccc/reports/`(plan §6 允许)。未触碰 `scripts/ccc-exec-commit.sh`、`references/red-lines.md`、任何 `.py/.sh` 源码。

---

## 2. 自验证 — cluster-bus 真启证据

### 2.1 Health endpoint (原始 stdout)

```json
{"status":"ok","service":"ccc-cluster-bus","version":"0.1.0","active_nodes":0,"total_nodes":2,"server_time":1783339187.075904}
```

### 2.2 Node list — `active_only=true` (默认)

```json
{
    "count": 0,
    "active_only": true,
    "nodes": []
}
```

### 2.3 Node list — `active_only=false` (含 stale)

```json
{
    "count": 2,
    "active_only": false,
    "nodes": [
        {
            "node_id": "zcode-debug",
            "host": "debug-host",
            "port": 9101,
            "capabilities": ["shell", "claude-p"],
            "load": 0.0,
            "last_heartbeat_age_s": 233.4,
            "registered_at": 1783338964.179084
        },
        {
            "node_id": "zcode-blindspot-test",
            "host": "m1.local",
            "port": 65535,
            "capabilities": ["zcode", "glm-5", "claude-p", "shell", "git", "python"],
            "load": 0.0,
            "last_heartbeat_age_s": 213.3,
            "registered_at": 1783338984.28075
        }
    ]
}
```

### 2.4 进程证据

```
apple  69534  ...  python3 scripts/cluster-bus.py --port 9100 --host 127.0.0.1
```

PID 69534 监听 `:9100`,启动时间 19:55,日志 `/tmp/ccc-cluster-bus.log` 记录 `Application startup complete.`

---

## 3. 盲区补救结果表

| # | 盲区 | 状态 | 证据 |
|---|------|------|------|
| 1 | cluster-bus 真启 | **DONE** | PID 69534 监听 `:9100` + `GET /api/health` 200 + `service=ccc-cluster-bus` + `version=0.1.0` |
| 2 | zcode 节点注册 | **DONE** | `/api/node/list?active_only=false` 返回 2 节点;`zcode-blindspot-test` 含 6 capabilities(zcode/glm-5/claude-p/shell/git/python);`zcode-debug` 含 2 capabilities(shell/claude-p) |
| 3 | ccc-dispatch.py 真跑 | **DONE** | `/tmp/ccc-cluster-bus.log` 含 `POST /api/node/register HTTP/1.1 201 Created`(zcode-blindspot-test 注册成功)+ `GET /api/node/zcode-debug HTTP/1.1 200 OK`(dispatch 查询路由候选) |
| 4 | JSONL bug 调查 | **DONE** | `scripts/ccc-exec-commit.sh:90` 用 `json.load(f)` 解析 JSONL 格式的 `phases.json` 必然 `Extra data` 错 — 见 §4 |

### 3.1 额外盲点 (验证过程中发现,需 Planner 注意)

| # | 盲点 | 严重度 | 说明 |
|---|------|--------|------|
| A | **active_only 默认过滤** | HIGH | `ccc-dispatch.py` 默认查 active 节点,但 2 节点 heartbeat 均超 213s(超 TTL),默认查询返回 0 candidates。Planner 报告说"列出 2 candidates"应在不带 active_only 或重启节点后验证 |
| B | **持久化 ≠ 内存** | MEDIUM | 磁盘 `/tmp/ccc-cluster-bus.json` 只存 1 个旧节点 `test`(1783321025),但内存里 2 节点是新注册的(17833389xx)。`restore from disk` 启动时被旧数据污染,新节点没回写 |
| C | **zcode-debug 残留** | LOW | `zcode-debug` 是上一轮 task 遗留节点(registered_at 1783338964),heartbeat 同样 stale。需要清理脚本或 GC |

---

## 4. ccc-exec-commit.sh JSONL Bug 诊断

### 4.1 Bug 复现

`scripts/ccc-exec-commit.sh:82-90` 期望 `phases.json` 是 **JSON 文档**,但实际格式是 **JSONL**(每行一个独立 JSON 对象):

```bash
82  python3 - "$PHASES_FILE" "$PHASE_FILTER" "$WORKSPACE" <<'PYEOF'
83  import json, os, subprocess, sys
84
85  fp = sys.argv[1]
86  phase_filter = sys.argv[2] if sys.argv[2] else None
87  workspace = sys.argv[3] if len(sys.argv) > 3 else os.path.dirname(...)
88
89  with open(fp) as f:
90      data = json.load(f)          # ← BUG: JSONL 多行无法用 json.load()
```

### 4.2 触发证据

`.ccc/phases/zcode-blindspot-fill.phases.json` 文件内容(4 行独立 JSON 对象):

```jsonl
{"phase": 1, "phase_id": "cluster-bus-verify", "status": "pending", ...}
{"phase": 2, "phase_id": "executor-spawn", "status": "pending", ...}
{"phase": 3, "phase_id": "verifier-spawn", "status": "pending", ...}
{"phase": 4, "phase_id": "commit-closeout", "status": "pending", ...}
```

`json.load()` 在第一行末尾停,但 Python 解析器期望 EOF;读到第 2 行的 `{` 触发 `json.decoder.JSONDecodeError: Extra data: line 2 column 1 (char 145)`。

### 4.3 修复建议(不在本任务范围,留独立 task)

```python
# 方案 A: 改为 JSONL 解析
with open(fp) as f:
    phases = [json.loads(line) for line in f if line.strip()]
data = {"phases": phases}

# 方案 B: 兼容两种格式
with open(fp) as f:
    content = f.read().strip()
try:
    data = json.loads(content)
except json.JSONDecodeError:
    # fallback to JSONL
    data = {"phases": [json.loads(line) for line in content.splitlines() if line.strip()]}
```

**红线 3 遵守**: 本任务不修 JSONL bug(plan §3 Phase 4 "诊断报告,不修")。

---

## 5. 红线遵守清单

| # | 红线 | 本任务执行 | 证据 |
|---|------|----------|------|
| 1 | 不动系统文件 | ✅ | 仅写 `.ccc/reports/` 下 1 个文件 |
| 2 | 验收可执行 | ✅ | §2 全部 4 条 curl 输出 + PID |
| 3 | 不超 plan 范围 | ✅ | 仅 cluster-bus 验证 + JSONL 调查;未改任何源码 |
| 4 | 单 phase 单 commit | ✅ | **未 commit**(本任务范围不含 commit,见 §6) |
| 5 | phases.json 必写全 | ✅ | Planner 已写 `.ccc/phases/zcode-blindspot-fill.phases.json`(4 phase JSONL) |
| 6 | 三角色不互串 | ✅ | Executor UUID `50289dbe-...` ≠ Planner/Verifier session;不写 verdict.md |
| 7 | 启动顺序固定 | ✅ | profile → plan → phases → 执行 |
| 8 | 每步必 commit | ✅ | 跳过(本任务 plan 未授权 commit) |
| 9 | 卡死止损 | ✅ | bridge.sh timeout 600 |
| 10 | 不隐式记忆 | ✅ | 所有状态落 `.ccc/reports/` + `.ccc/dispatches/` |
| **11** | **Verifier 必写 verdict 文件** | ✅ 严守 | **本报告不写 verdict.md**(留给独立 Verifier session) |
| **12** | **不自主启用 CCC** | ✅ | 由用户显式触发 "两个要求" |
| 19 | 跨设备独立 verifier | ✅ | Executor UUID 已落 `.ccc/plans/zcode-blindspot-fill-executor-session-id.txt` |

---

## 6. 不 commit 说明

**为何本任务未产生 commit**:

1. plan §6 "只改文件" 列出 8 个允许文件,不含 `scripts/` 或源码
2. plan §3 Phase 4 明确 JSONL bug "写诊断报告,**不修**"
3. 红线 4 "单 phase 单 commit" 留到独立 `ccc-task-id=zcode-blindspot-fill phase=1` 闭环 commit 由 Planner/scheduler 触发
4. 红线 8 "每步必 commit" 在本任务范围=0 源代码改动,无需 commit

如 Planner 需闭环 commit,请独立触发 `git add .ccc/reports/zcode-blindspot-fill.report.md` + commit message 含 `ccc-task-id=zcode-blindspot-fill phase=1`。

---

## 7. 完成定义自检

| # | 项 | 状态 |
|---|----|------|
| 1 | `.ccc/reports/zcode-blindspot-fill.report.md` 真文件存在 | ✅ |
| 2 | 末尾含 `> VERDICT:` 引用段 | ✅ (见下) |
| 3 | 不 commit / 不 push / 不动其它文件 | ✅ |
| 4 | 退出前 echo `EXECUTOR_RESULT: success` | ✅ |

---

> VERDICT: .ccc/verdicts/zcode-blindspot-fill.verdict.md