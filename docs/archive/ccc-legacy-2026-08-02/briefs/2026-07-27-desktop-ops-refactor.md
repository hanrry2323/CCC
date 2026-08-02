# Desktop Ops 重构拆卡（2026-07-27）

> 权威摘要已写入 `docs/product/loop-engineer-authority.md`「Desktop Ops 重构拆卡」。  
> **本 brief = 下程 Swift/探针实现清单**；勿当平行真理。冲突以 authority 为准。

## 问题

Desktop [`OpsView.swift`](../../desktop/Sources/CCCDesktop/OpsView.swift) 已有总灯与「交给 Agent」，但首页仍偏工程师控制台：看板计数/失败账/非红 risks 抢叙事；MCP 占位「后续接入」；部分 Hub envelope ↔ Swift schema 漂移（ports `alive` vs `ok`、docs `findings` vs `items`、资源字段）。

## 产品目标

打开运维 = **四域灯板**：绿敢开发 / 橙可忽略 / 红一键交 Agent。不以舰队数卡为主叙事。

## P0（已合入 · 2026-07-27）

1. **信息架构** ✓ above-the-fold 四域壳  
2. **契约修复** ✓ ports `ok` / docs `items` / resources  
3. **MCP 探针** ✓ `domains.agent_mcp` + 红告警  
4. **全局红点** ✓ 侧栏 severity 轮询  

下一程 P1 指令包：[`../dev-packets/001-ops-p1-copy-vs-handoff.md`](../dev-packets/001-ops-p1-copy-vs-handoff.md) · [`../dev-packets/002-ops-p1-tunnel-row.md`](../dev-packets/002-ops-p1-tunnel-row.md)。  
总路线：[`2026-07-27-ccc-production-readiness.md`](./2026-07-27-ccc-production-readiness.md)。

## P1

5. 域 chip：绿 / 橙 / 红 / 灰；relay fail-open = **橙**。
6. 折叠「模型通道」：接 `/api/ops/upstream-daily`、`/upstream-efficiency`。
7. 显式 Hub 隧道 `127.0.0.1:17777` + launchd 行。
8. 告警按钮拆「仅复制」与「交给 Agent」；handoff 模板区分 infra vs 板面 abnormal。

## P2

9. `~/.ccc/alerts/` / authority-patrol 进红条。
10. `agent_minds` 折叠摘要。
11. 网页 `#/ops` 彻底降级（Desktop SSOT）。
12. 重建 App 二进制：三档 `flash/pro/code` picker + 运维 UI 一并发布。

## 验收

- 无红：告警区空；大灯绿 + 一句人话。
- 有红：一键复制可交当前项目或 `ccc` 会话。
- MCP 坏必见红；schema 测绿。
- 不以各仓 backlog 列计数为首页主叙事。
