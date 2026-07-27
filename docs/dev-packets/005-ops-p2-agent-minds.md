# DEV-PACKET: ops-p2-agent-minds

> 合入权威 = Cursor。做完只提交到指定分支，不要 push main。  
> 先 `git checkout main && git pull`，再开分支。  
> **P1 已全部合入；本包起 P2。**

## 1. 目标（用户可见）

运维页增加折叠区 **「项目心智」**：展示 Hub `/api/ops/summary` 里已有的 `agent_minds.items`（短列表）。默认折叠，解码失败不崩、不抬红。

## 2. 分支与提交

- 分支：`draft/ops-p2-agent-minds`
- 提交：`feat(desktop): folded ops agent_minds digest`
- 禁止 push main；禁止 `git add -A`

## 3. 白名单

- `desktop/Sources/CCCDesktop/BoardOpsModels.swift`
- `desktop/Sources/CCCDesktop/OpsView.swift`

## 4. 黑名单

- `scripts/**`（Hub 已吐字段，本包不改后端）
- `docs/product/**`
- `AppModel.swift` / `APIClient.swift`（数据已在 `opsSummary`）
- `~/.ccc/**`

## 5. 现状锚点

- Hub `ops.py`：`out["agent_minds"] = {"ok": True, "items": minds}`
- Desktop `OpsSummary` **尚未**解码 `agent_minds`
- OpsView 已有 DisclosureGroup「模型通道」可参照

## 6. 实现步骤

1. 用 curl 或读 Hub 代码确认 `items[]` 字段（常见：project_id / id / title / summary / updated）。全部 Optional。
2. `OpsSummary` 增加 `agent_minds: OpsAgentMindsResp?`
3. OpsView：`DisclosureGroup("项目心智")`，空则「暂无心智摘要」；每行项目 id + 一句摘要（截断）
4. `cd desktop && swift build`

## 7. 验收

```bash
cd desktop && swift build
rg -n "agent_minds|AgentMind|项目心智" desktop/Sources/CCCDesktop/
```

## 8. 做完回报

```
BRANCH: draft/ops-p2-agent-minds
FILES:
- …
TESTS:
- swift build → …
RESIDUAL:
- …
```
