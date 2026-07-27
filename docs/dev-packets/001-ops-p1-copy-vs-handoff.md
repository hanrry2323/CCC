# DEV-PACKET: ops-p1-copy-vs-handoff

> 复制本文件全文发给**个人 Claude Code CLI**（非 Desktop Agent）。  
> 合入权威 = Cursor。做完只提交到指定分支，**不要 push main**。

## 1. 目标（用户可见）

运维红灯每条有两个按钮：**「仅复制」**（只进剪贴板、不切会话）和 **「交给 Agent」**（复制 + 打开对话并预填，行为与今天单按钮一致）。

## 2. 分支与提交

- 分支：`draft/ops-p1-copy-vs-handoff`
- 提交：`feat(desktop): split ops alert copy vs handoff buttons`
- **禁止** push main；**禁止** `git add -A`

## 3. 白名单（只许改这些）

- `desktop/Sources/CCCDesktop/OpsView.swift`
- `desktop/Sources/CCCDesktop/AppModel.swift`（仅当需要抽出 `copyOpsAlertPayload` 或调整 `opsCopiedHint` 文案时）

## 4. 黑名单（碰了就停）

- `docs/product/loop-engineer-authority.md`
- `scripts/_ops_probe.py`
- `~/.ccc/**`
- 其它未列路径

## 5. 现状锚点

- `OpsView.swift` → `redAlertsSection`（约 L266+）：仅 `Button("交给 Agent")`
- `handoffOpsAlert`（约 L309+）：先写剪贴板再 `model.handoffToOpsAgent` 再切 `.chat`
- `AppModel.handoffToOpsAgent`（约 L2108+）：保持交给 Agent 路径不变

## 6. 实现步骤

1. 把「组装告警文本 + 写剪贴板」抽成私有方法（如 `copyOpsAlertToPasteboard(_:) -> String`），`handoffOpsAlert` 复用它。
2. 红灯行按钮区改为 `HStack`：`仅复制`（bordered）→ 只调用复制方法，设 `opsCopiedHint` 为「已复制」之类短提示；`交给 Agent`（borderedProminent）→ 现有 handoff。
3. 不要改红灯过滤逻辑、不要改 MCP/severity 合并。
4. `cd desktop && swift build` 通过。

## 7. 验收（必须跑）

```bash
cd desktop && swift build
# 目视：OpsView redAlertsSection 有两按钮；仅复制不调用 handoffToOpsAgent
rg -n "仅复制|交给 Agent|copyOpsAlert" desktop/Sources/CCCDesktop/OpsView.swift
```

## 8. 做完回报（固定格式）

```
BRANCH: draft/ops-p1-copy-vs-handoff
FILES:
- …
TESTS:
- swift build → …
RESIDUAL:
- …
```
