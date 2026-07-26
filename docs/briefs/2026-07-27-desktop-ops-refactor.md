# Desktop Ops 重构拆卡（2026-07-27）

> 权威摘要已写入 `docs/product/loop-engineer-authority.md`「Desktop Ops 重构拆卡」。  
> **本 brief = 下程 Swift/探针实现清单**；勿当平行真理。冲突以 authority 为准。

## 问题

Desktop [`OpsView.swift`](../../desktop/Sources/CCCDesktop/OpsView.swift) 已有总灯与「交给 Agent」，但首页仍偏工程师控制台：看板计数/失败账/非红 risks 抢叙事；MCP 占位「后续接入」；部分 Hub envelope ↔ Swift schema 漂移（ports `alive` vs `ok`、docs `findings` vs `items`、资源字段）。

## 产品目标

打开运维 = **四域灯板**：绿敢开发 / 橙可忽略 / 红一键交 Agent。不以舰队数卡为主叙事。

## P0（下一程编译 Desktop）

1. **信息架构**：above-the-fold = ①总灯人话 ②集群/服务/隧道/端口 ③Agent+MCP+Relay 摘要 ④仅红告警。看板计数、failures、inbox、非红 risks → DisclosureGroup 或链到看板/右栏。
2. **契约修复**：[`scripts/_ops_probe.py`](../../scripts/_ops_probe.py) envelope ports 映射 `alive`→`ok`；docs 统一 `items`（或改 Swift）；资源用 `resources_history` 或对齐 `cpu/mem_pct/disk_pct`；补 [`tests/scripts/test_ops_confidence.py`](../../tests/scripts/test_ops_confidence.py)。
3. **MCP 探针**：填充 `domains.agent_mcp`；坏则红告警 + `copy_payload`；去掉「后续接入」占位。
4. **全局红点**：后台轻量轮询 `severity`；侧栏「运维」角标 / 标题栏点；不必进运维页才知红。

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
