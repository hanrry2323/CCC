# 编排流程 Runbook — M1 对话 → Mac2017 编排 → 产出

> 架构对齐 2026-07-19。  
> 边界基线：[`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)  
> 拓扑：[`../deploy/topology.md`](../deploy/topology.md)  
> 启动：[`../STARTUP-BRIEF.md`](../../STARTUP-BRIEF.md)

---

## 角色锁（硬约束）

| 阶段 | 执行器 | 机器 | 禁止 |
|------|--------|------|------|
| 对话/意图 | **loop-code**（arm64） | M1 sidecar `:7788` | M1 扇出 work / M1 写业务码 |
| product 扇出 | **Claude Code** | Mac2017 Engine | 用 OpenCode 扇出 |
| dev 写码 | **OpenCode** | Mac2017 Engine | 用 Claude Code 写码 |
| reviewer | **Claude Code** | Mac2017 Engine | 写 plan / 写码 |
| tester | **pytest** | Mac2017 Engine | 写码 |
| kb | **git tag** | Mac2017 Engine | — |

**红线**：product ≠ dev；reviewer 不写码；tester 不写码。详见 [`../../references/red-lines.md`](../../references/red-lines.md) 红线 6。

---

## 完整流程（一次 epic）

### 1. M1 对话定稿

```text
Desktop（M1）↔ sidecar :7788 ↔ loop-code ↔ 2017 Router :4000
  → 对齐基线 → 下一步 → 定稿方案
  → 点「转任务」→ POST /api/desktop/transfer
```

- 对话本机落盘：`~/Library/Application Support/CCCDesktop/sessions/`
- 闲聊全文 **不**过桥；只 transfer 结构化 epic 字段
- 右栏 FlowRail 实时回传编排状态（SSE `/api/desktop/flow/events`）

**新业务仓迁到 2017 / 注册 / Desktop 开项目对话**：  
[`app-migrate-register-desktop.md`](app-migrate-register-desktop.md) · Agent：[`../product/desktop-agent-handoff.md`](../product/desktop-agent-handoff.md)

### 2. Mac2017 收 epic

```text
POST /api/desktop/transfer
  → transfer_gate 校验
  → backlog/<tid>.json (card_kind=epic, split_status=pending)
  → flow event: epic_created
```

验收：`curl -u ccc:ccc http://192.168.3.116:7777/api/board?workspace=<ws>` 出现 epic。

### 3. Engine product 扇出（Claude Code）

```text
Engine 扫 backlog pending epic
  → product 角色（Claude Code）读 epic + plan
  → 扇出 work×N → planned/<tid>.json (card_kind=work)
  → epic split_status=planned（epic 仍留 backlog）
  → flow event: epic_planned, work_created×N
```

### 4. Engine dev 写码（OpenCode）

```text
Engine 调度 planned work
  → dev 角色（OpenCode，--dir <业务仓>）
  → in_progress → testing
  → report.md
  → flow event: work_in_progress, work_testing
```

**cwd 硬约束**：OpenCode 必须在 2017 业务仓 `~/program/apps/<ws>/` 内写码，**禁止** M1 路径。

### 5. reviewer + tester 门禁

```text
testing work
  → reviewer（Claude Code）语义审查 → verdict.md（≥3 probes）
  → tester（pytest）跑验收清单
  → PASS → verified；FAIL → abnormal
  → flow event: work_verified | work_abnormal
```

**红线 11**：verdict 必须落文件，口头 PASS 无效。

### 6. kb 归档

```text
verified work
  → kb 角色：git tag + CHANGELOG → released
  → flow event: work_released
```

### 7. epic 收口

```text
全部子卡 released → epic split_status=done（沉底 backlog）
任子卡 abnormal → epic split_status=failed（仍留 backlog，需人处理）
```

---

## 控制面状态机

`~/.ccc/control.json`（Mac2017）：

| 模式 | Engine | 用途 |
|------|--------|------|
| `disabled` | 关 | 完全离线 |
| `ui` | 关 | 仅 Hub+Board（前端开发） |
| `enabled` | **只消费 app 队列** | 日常生产（保持此项） |
| `invent` | **已退役** | 勿启用 |

```bash
# Mac2017
bash scripts/ccc-autostart-guard.sh enable --start   # 上线
bash scripts/ccc-autostart-guard.sh status           # 查状态
python3 scripts/ccc-failure-report.py --last 20       # 失败账本
```

**红线 12**：禁止 agent 自主启用 CCC；必须用户显式触发。

---

## 故障处理

### epic 卡在 pending 不扇出

1. 查 Engine 是否 `enabled`：`bash scripts/ccc-autostart-guard.sh status`
2. 查 Engine 日志：`tail -50 ~/.ccc/logs/ccc-engine.log`
3. 查 epic 是否有 plan/phases；无 plan 则 product 跳过
4. 手动唤醒：`bash scripts/ccc-autostart-guard.sh enable --start`

### work 卡在 testing 不出 verdict

1. 查 review-lock：`ls .ccc/review-locks/`
2. 查 verdict 是否落文件：`ls .ccc/verdicts/`
3. 红线 11：口头 PASS 无效；必须 `verdict.md`

### work abnormal

1. 查 failure_note：`cat .ccc/board/abnormal/<tid>.json | jq .failure_note`
2. 查失败账本：`python3 scripts/ccc-failure-report.py --last 1`
3. Desktop 看板拖回 planned 重跑，或 `POST /api/tasks/reopen`

### M1 断 Hub

- 对话仍可本机聊（sidecar 活着即可）
- 不能转任务 / 右栏不更新（白话提示）
- 验收 B1：M1 断 Hub 10s 仍可聊

### 2017 Hub 打不开 :7777

1. Server 本机：`curl http://127.0.0.1:7777/`（应 200）
2. 客户端超时 → macOS 防火墙拦 Python 入站
   - 系统设置 → 网络 → 防火墙：关，或允许 Python 传入
   - 或 `sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off`
3. 重装 plist：`bash scripts/install-hub-plist.sh --start`

---

## 验收口径（基线）

| # | 断言 |
|---|------|
| B1 | M1 断 Hub 10s：仍可本机聊；不能转任务时有白话 |
| B2 | 转任务成功：2017 backlog 出现 epic；M1 右栏 ≤15s 见拆分或失败白话 |
| B3 | Engine 写码 cwd = 2017 业务仓，不是 M1 路径 |
| B4 | 闲聊全文不进入 product/dev prompt（仅 gate/plan_md 结构化字段） |
| B5 | 常态无「对话打到 Hub `/api/chat`」（已删路由） |

---

## 日常检查清单

```bash
# Mac2017
bash scripts/ccc-autostart-guard.sh status           # 控制面 = enabled
python3 scripts/ccc-board.py index                    # 看板状态
python3 scripts/ccc-failure-report.py --last 20       # 失败账本
curl -s -u ccc:ccc http://127.0.0.1:7777/api/ops/summary | jq '.risks'  # 风险

# M1
curl -s http://127.0.0.1:7788/health                  # sidecar 健康
bash scripts/smoke-desktop-stable.sh                  # 端到端烟测
```

---

## 相关文档

- 边界契约：[`../product/dialogue-orchestration-boundary.md`](../product/dialogue-orchestration-boundary.md)
- 转任务门禁：[`../product/transfer-gate.md`](../product/transfer-gate.md)
- 执行器：[`../executors/overview.md`](../executors/overview.md) · [`../executors/loop-code.md`](../executors/loop-code.md)
- 红线：[`../../references/red-lines.md`](../../references/red-lines.md)
- 控制面：[`../CONTROL.md`](../CONTROL.md)
- 可观测性：[`../observability.md`](../observability.md)
