# DEV-PACKET: ops-p2-local-patrol-alerts

> 合入权威 = Cursor。做完只提交到指定分支，不要 push main。  
> 先 `git checkout main && git pull`，再开分支。

## 1. 目标（用户可见）

运维红灯区合并 **本机** `~/.ccc/alerts/` 下最新的权威巡查告警（`*-L3-authority-patrol.md` 或目录内 `.md`）。有文件则进红条，带「仅复制 / 交给 Agent」；无文件不抬红。

## 2. 分支与提交

- 分支：`draft/ops-p2-local-patrol-alerts`
- 提交：`feat(desktop): merge local authority-patrol alerts into Ops red bar`
- 禁止 push main；禁止 `git add -A`

## 3. 白名单

- `desktop/Sources/CCCDesktop/AppModel.swift`
- `desktop/Sources/CCCDesktop/BoardOpsModels.swift`（若需扩展 `OpsHealthDisplay.alerts`）
- `desktop/Sources/CCCDesktop/OpsView.swift`（仅当必须；优先改 Display 合并逻辑）

## 4. 黑名单

- `scripts/**`
- `docs/product/**`
- `~/.ccc/**` 本身（只读，勿写入）

## 5. 现状锚点

- 巡查写入：`~/.ccc/alerts/{timestamp}-L3-authority-patrol.md`（人话 markdown）
- `OpsHealthDisplay.alerts(summary:agentOk:)` 已合并 Hub + sidecar + MCP
- `OpsHealthAlert`：title / detail / copy_payload / source

## 6. 实现步骤

1. 读 `FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".ccc/alerts")`
2. 列出 `*.md`，按修改时间取最近 ≤5 个；读正文前 ~2KB
3. 转成 `OpsHealthAlert`：title 取首个 `#` 标题或文件名；detail 截断；`copy_payload` = 全文或截断 4KB；`source = "authority-patrol"`
4. 并入 `OpsHealthDisplay.alerts`（按 title 去重）
5. 在 `refreshOps` / `recomputeOpsDisplay` 路径刷新本地告警（失败静默）
6. `cd desktop && swift build`

## 7. 验收

```bash
cd desktop && swift build
rg -n "authority-patrol|ccc/alerts|localPatrol" desktop/Sources/CCCDesktop/
```

## 8. 做完回报

```
BRANCH: draft/ops-p2-local-patrol-alerts
FILES:
- …
TESTS:
- swift build → …
RESIDUAL:
- …
```
