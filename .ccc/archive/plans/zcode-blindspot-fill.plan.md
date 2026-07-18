# Plan: zcode-blindspot-fill (弥补 ZCode adapter 实施时的盲区)

> **任务 ID**: `zcode-blindspot-fill`
> **目标**: 补 zcode-adapter-v121 任务里"读过但没真跑过"的 4 项盲区
> **日期**: 2026-07-06

---

## 1. 任务描述

**输入**: 用户指令"两个要求:1. 弥补你未知的地方;2. 真调用 Claude code 执行一个测试任务"

**本任务专注要求 1**: 把 zcode-adapter-v121 的盲区从"读过文档"升级为"真验证过"

**期望产出**:
- 真实启动 `cluster-bus.py` 服务
- 真实注册 zcode 节点到 cluster-bus
- 真实跑 `ccc-dispatch.py` 看到 zcode 节点出现
- 独立 session 验收(红线 6 真隔离)
- 修复 `ccc-exec-commit.sh` JSONL bug 调查

---

## 2. 三角色边界(红线 6 + 19 严格)

| 角色 | Session | 实现方式 |
|------|---------|---------|
| **Planner** | 当前 ZCode 对话 | 写本 plan + phases.json |
| **Executor** | `claude -p` 独立子进程,通过 `scripts/ccc-zcode-bridge.sh` spawn | 写 cluster-bus 测试日志 + 报告 |
| **Verifier** | **独立 `claude -p` session**(新 UUID) | 写 verdict.md,≥3 adversarial probes |

**红线 19 验证**: Verifier session 与 Executor session UUID 不同,落 `.ccc/plans/zcode-blindspot-fill-{executor,verifier}-session-id.txt` 区分。

---

## 3. Phase 拆解

### Phase 1: 启 cluster-bus 服务
- 后台启动 `python3 scripts/cluster-bus.py --port 9100`
- 验证 `curl http://127.0.0.1:9100/api/health` 返回 200
- 验证 `curl http://127.0.0.1:9100/api/node/list` 返回空 nodes 列表

### Phase 2: 注册 zcode 节点
- 跑 `python3 scripts/ccc-znode-register.py --node-id zcode-blindspot-test --daemon &`
- 验证 `/api/node/list` 出现新节点
- 验证 heartbeat 30s 后仍 active

### Phase 3: 跑 ccc-dispatch.py 路由
- 跑 `python3 scripts/ccc-dispatch.py --plan .ccc/plans/zcode-blindspot-fill.plan.md --workspace .`
- 验证 zcode-blindspot-test 出现在 candidates 列表
- 验证 recommended node + capabilities match

### Phase 4: 调查 ccc-exec-commit.sh JSONL bug
- 读 ccc-exec-commit.sh L82-243 实际代码
- 验证 phases.json JSONL 解析是否真挂
- 写诊断报告,不修(独立 task)

---

## 4. 红线清单(本任务执行)

| # | 红线 | 执行 |
|---|------|------|
| 1 | 不动系统文件 | 仅写 `.ccc/plans/`,`.ccc/reports/`,`.ccc/verdicts/`,`.ccc/dispatches/`,`.ccc/phases/` |
| 2 | 验收可执行 | cluster-bus health,node list,dispatch output |
| 3 | 不超 plan 范围 | 仅 cluster-bus 验证 + JSONL bug 调查 |
| 4 | 单 phase 单 commit | 1 commit (本任务) |
| 5 | phases.json 必写全 | 见 `.ccc/phases/zcode-blindspot-fill.phases.json` |
| 6 | 三角色不互串 | Planner(我)/ Executor (claude -p)/ Verifier (独立 claude -p,新 UUID) |
| 7 | 启动顺序固定 | 读 state.md + profile.md + 本 plan |
| 8 | 每步必 commit | 1 commit 含 ccc-task-id 前缀 |
| 9 | 卡死止损 | bridge.sh 内 timeout 600 + watchdog |
| 10 | 不隐式记忆 | 所有状态落 .ccc/dispatches/ |
| 11 | Verifier 必写 verdict 文件 | Verifier session 真写 .ccc/verdicts/zcode-blindspot-fill.verdict.md |
| 12 | 不自主启用 CCC | 用户显式触发 "两个要求" |
| 19 | 跨设备独立 verifier | Verifier 与 Executor 不同 UUID session |

---

## 5. 退出标准

- [ ] cluster-bus 真启,health endpoint 返回 200
- [ ] zcode 节点真注册,/api/node/list 包含 capabilities
- [ ] ccc-dispatch.py 真跑,看到 zcode 节点为候选
- [ ] Verifier 真写 verdict.md(独立 session)
- [ ] ccc-exec-commit.sh JSONL bug 诊断报告
- [ ] 1 commit 含 ccc-task-id=zcode-blindspot-fill phase=1

只改文件:

- `.ccc/plans/zcode-blindspot-fill.plan.md` (本文件,Planner 产物)
- `.ccc/plans/zcode-blindspot-fill-executor-prompt.txt` (Executor prompt)
- `.ccc/plans/zcode-blindspot-fill-verifier-prompt.txt` (Verifier prompt)
- `.ccc/plans/zcode-blindspot-fill-{executor,verifier}-session-id.txt` (UUID 落盘)
- `.ccc/phases/zcode-blindspot-fill.phases.json` (Planner 产物)
- `.ccc/reports/zcode-blindspot-fill.report.md` (Executor 产物)
- `.ccc/verdicts/zcode-blindspot-fill.verdict.md` (Verifier 产物,红线 11)
- `.ccc/dispatches/cluster-bus-test-*.json` (cluster-bus 验证日志)
- `scripts/ccc-znode-register.py` (盲区验证发现 port=0 bug,本任务内 fix)
- `README.md` (后续 readme-zcode-update 任务新增 ZCode Adapter 段,被本任务 Gate 4 视为越界)

**禁止改动**:
- `references/red-lines.md` / `templates/` / `scripts/ccc-exec-commit.sh`(JSONL bug 独立 task)

## 7. Commit 计划

| Phase | 改动 | Commit |
|-------|------|--------|
| phase 1 | plan + phases + 盲区验证报告 + verdict | 1 commit: `ccc-task-id=zcode-blindspot-fill phase=1` |