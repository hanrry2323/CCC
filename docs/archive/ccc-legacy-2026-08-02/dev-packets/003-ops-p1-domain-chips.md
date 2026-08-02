# DEV-PACKET: ops-p1-domain-chips

> 合入权威 = Cursor。做完只提交到指定分支，不要 push main。  
> 先 `git checkout main && git pull`，再开分支。

## 1. 目标（用户可见）

运维域 chip（Engine / Hub / 宕口 / Agent / MCP / Relay / 容量等）支持 **绿 / 橙 / 红 / 灰** 四态，不再只有绿/红二值。  
**Relay fail-open（`relay.ok == false` 且仍在跑）必须显示橙**，不是红。

## 2. 分支与提交

- 分支：`draft/ops-p1-domain-chips`
- 提交：`feat(desktop): ops domain chips green/amber/red/gray`
- 禁止 push main；禁止 `git add -A`

## 3. 白名单

- `desktop/Sources/CCCDesktop/OpsView.swift`
- `desktop/Sources/CCCDesktop/CCCTheme.swift`（或现有主题文件；仅当缺 amber 色时加一个常量）

## 4. 黑名单

- `scripts/_ops_probe.py`
- `docs/product/**`
- `~/.ccc/**`
- 其它未列路径

## 5. 现状锚点

- `OpsView.domainChip(title:ok:subtitle:)`（约 L590）—— `ok: Bool` → 仅绿/红
- `agentMcpRelaySection` / `clusterSummarySection` 调用处
- Relay 文案已有 `fail-open 直连`（搜 `fail-open`）

## 6. 实现步骤

1. 新增枚举或等价：`enum DomainChipTone { case green, amber, red, gray }`
2. 把 `domainChip(title:ok:subtitle:)` 改为 `domainChip(title:tone:subtitle:)`（可保留 `ok:` 包装转调，避免大面积机械改漏）
3. 映射建议：
   - Engine 停 / Hub 不通 / 宕口>0 / Agent 挂 / MCP 明确失败 → **red**
   - Relay `ok == false`（fail-open）→ **amber**
   - 探测中 / 未知 → **gray**
   - 正常 → **green**
4. amber 颜色：若主题无现成色，用偏橙但不刺眼的 Color（勿引入新依赖）
5. `cd desktop && swift build`

## 7. 验收

```bash
cd desktop && swift build
rg -n "DomainChipTone|tone:|\.amber|fail-open" desktop/Sources/CCCDesktop/OpsView.swift
```

## 8. 做完回报

```
BRANCH: draft/ops-p1-domain-chips
FILES:
- …
TESTS:
- swift build → …
RESIDUAL:
- …
```
