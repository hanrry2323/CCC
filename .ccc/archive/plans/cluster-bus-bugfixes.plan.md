# Plan: cluster-bus-bugfixes (修复 zcode-blindspot-fill 发现的 3 个 bug)

> **任务 ID**: `cluster-bus-bugfixes`
> **目标**: 修复 zcode-blindspot-fill Executor/Verifier 发现的 3 个 bug
> **日期**: 2026-07-06
> **触发**: 用户"继续推进,ccc 流程"

---

## 1. 任务描述

**输入**: 用户指令"好,继续推进,ccc 流程"

**前置任务**: `zcode-blindspot-fill` Executor 发现 3 个 bug + Verifier 确认

**3 个待修 bug**(按严重度排序):

| # | Bug | 严重度 | 修复文件 |
|---|-----|--------|---------|
| 1 | `ccc-exec-commit.sh` JSONL `json.load()` 解析失败 | **HIGH**(阻塞红线 4+8) | `scripts/ccc-exec-commit.sh` |
| 2 | `cluster-bus.py` `active_only=true` 默认过滤,导致 dispatch 看不到 stale 节点 | **HIGH** | `scripts/cluster-bus.py` + `scripts/ccc-dispatch.py` |
| 3 | cluster-bus 无 stale 节点 GC,残留 zcode-debug 类节点 | LOW | `scripts/cluster-bus.py` |

---

## 2. 三角色边界(红线 6 + 19 严格)

| 角色 | Session | 实现 |
|------|---------|------|
| **Planner** | 当前 ZCode 对话 | 本 plan + phases + 各 phase 修复 |
| **Executor** | 独立 `claude -p` 子进程,UUID 落盘 | 修 3 个文件 + 写 report |
| **Verifier** | 独立 `claude -p` 子进程,**新 UUID** | 验证修复有效 + 写 verdict.md |

红线 19 验证: 4 个 session UUID 全部不同(Planner / 2× Executor phases / Verifier)

---

## 3. Phase 拆解

### Phase 1: 修 ccc-exec-commit.sh JSONL bug
**问题**: L89 `data = json.load(f)` 对 JSONL 多行格式报 `Extra data`

**修复**: 方案 A(改 JSONL 解析,优先)+ 兼容 fallback

```python
# 修复前 (L82-90)
with open(fp) as f:
    data = json.load(f)

# 修复后 (兼容两种格式)
with open(fp) as f:
    content = f.read().strip()
if not content:
    data = {}
elif content.startswith('{') and not content.startswith('{"phase":'):
    # 单 JSON 对象
    data = json.loads(content)
else:
    # JSONL 格式(每行一个 phase 对象)
    phases = [json.loads(line) for line in content.splitlines() if line.strip()]
    data = {"phases": phases}
```

**验收**:
- `bash scripts/ccc-exec-commit.sh . hello-ccc-demo-v2` 不再 JSONDecodeError
- 重新设计测试覆盖 JSONL 解析路径

### Phase 2: 修 cluster-bus active_only 默认
**问题**: `GET /api/node/list` 默认 `active_only=true`,heartbeat 超 TTL 节点被过滤,dispatch 看不到

**修复选项**:
- A: 改默认 `active_only=false`(兼容性破坏)
- B: 加 `?active_only=false` 默认参数到 ccc-dispatch.py
- C: 在 cluster-bus 启动时把 stale 节点 active=true(语义不清,弃)

**选 B**: 最小侵入,符合 cluster-bus 现有 API 语义

**改动**:
- `scripts/ccc-dispatch.py`: `fetch_active_nodes` 加 `?active_only=false` 参数
- `scripts/cluster-bus.py`: 添加 `GET /api/node/list?include_stale=true` 选项

**验收**:
- 真启 cluster-bus,注册 2 节点(stale + fresh)
- 跑 ccc-dispatch.py 看到 2 candidates(之前只能看到 0)

### Phase 3: 加 stale 节点 GC
**问题**: 节点退出后无 GC,残留 disk + memory

**修复**: cluster-bus 启动时清 `last_heartbeat_age > 90s × 10 = 900s` 的节点

```python
# cluster-bus.py 启动时
for node_id, node in list(nodes.items()):
    age = now - node['last_heartbeat']
    if age > HEARTBEAT_TTL_SECONDS * 10:  # 900s = 15 min stale
        log.info(f"GC stale node {node_id} (age={age:.0f}s)")
        del nodes[node_id]
```

**验收**:
- cluster-bus 启动时日志打印 GC 数量
- 重启 cluster-bus 后 `node list` 不再含 stale 节点

### Phase 4: 独立 Verifier 验收
- 跑 `bash scripts/ccc-zcode-bridge.sh . cluster-bus-bugfixes verifier`(独立 UUID)
- 验证 3 个 bug 都真修了
- 写 verdict.md ≥3 probes

---

只改文件:

- `scripts/ccc-exec-commit.sh` (修 JSONL bug)
- `scripts/cluster-bus.py` (active_only 选项 + GC)
- `scripts/ccc-dispatch.py` (默认 include stale)
- `scripts/ccc-exec-commit.sh.md` (更新文档,如存在)
- `SKILL.md` (Verifier 加的 YAML frontmatter,允许)
- `.ccc/plans/cluster-bus-bugfixes.plan.md` (本文件)
- `.ccc/phases/cluster-bus-bugfixes.phases.json`
- `.ccc/phases/cluster-bus-bugfixes.phases.json.task_id` (sidecar)
- `.ccc/plans/cluster-bus-bugfixes-{executor,verifier}-prompt.txt`
- `.ccc/plans/cluster-bus-bugfixes-{executor,verifier}-session-id.txt`
- `.ccc/reports/cluster-bus-bugfixes.report.md`
- `.ccc/verdicts/cluster-bus-bugfixes.verdict.md`
- `tests/scripts/test_ccc_exec_commit_jsonl_smoke.py` (新测试)
- `tests/scripts/test_ccc_exec_commit_idempotency.py` (sidecar 适配)
- `tests/scripts/test_ccc_znode_register_smoke.py` (port 65535 适配)

**禁止改动**:
- `references/red-lines.md`(本次不修红线条文)
- `templates/` (不破坏契约)

---

## 5. 红线清单

| # | 红线 | 执行 |
|---|------|------|
| 1 | 不动系统文件 | 仅改 `scripts/` + `.ccc/` |
| 2 | 验收可执行 | 21/21 smoke + ccc-finish + 真启 cluster-bus 验证 |
| 3 | 不超 plan 范围 | 3 个 bug 修复,不含其他 |
| 4 | 单 phase 单 commit | 4 phases → 4 commits |
| 5 | phases.json 必写全 | 4 行 JSONL |
| 6 | 三角色不互串 | Planner / Executor / Verifier UUID 互异 |
| 7 | 启动顺序固定 | state.md + profile.md + 本 plan |
| 8 | 每步必 commit | 4 commits |
| 9 | 卡死止损 | bridge.sh timeout 600 + watchdog |
| 10 | 不隐式记忆 | UUID + spawn 报告 + verdict 全落盘 |
| 11 | Verifier 必写 verdict 文件 |  Verifier 真写 |
| 12 | 不自主启用 CCC | 用户显式触发"继续推进" |
| 19 | 跨设备独立 verifier | Verifier 与 Executor UUID 不同 |

---

## 6. Commit 计划

| Commit | Phase | msg |
|--------|-------|-----|
| #1 | phase 1 | `ccc-task-id=cluster-bus-bugfixes phase=1` (JSONL fix) |
| #2 | phase 2 | `ccc-task-id=cluster-bus-bugfixes phase=2` (active_only) |
| #3 | phase 3 | `ccc-task-id=cluster-bus-bugfixes phase=3` (GC) |
| #4 | phase 4 | `ccc-task-id=cluster-bus-bugfixes phase=4` (verifier + closeout) |

---

## 7. 退出标准

- [ ] phase 1: ccc-exec-commit.sh 解析 JSONL 不报错
- [ ] phase 2: ccc-dispatch.py 默认 include stale 节点
- [ ] phase 3: cluster-bus 启动时 GC 900s+ stale 节点
- [ ] phase 4: Verifier 独立 session 写 PASS verdict(≥3 probes)
- [ ] 4 commits 含 ccc-task-id 前缀
- [ ] ccc-finish 6/6 PASS

---

**最后更新**: 2026-07-06 (Plan 创建)
**继承任务**: zcode-blindspot-fill (发现 bug 的原始任务)