# DEV-PACKET: ops-p1-upstream-panel

> 合入权威 = Cursor。做完只提交到指定分支，不要 push main。  
> 先 `git checkout main && git pull`，再开分支。

## 1. 目标（用户可见）

运维页增加折叠区 **「模型通道」**：展示 Hub `GET /api/ops/upstream-daily` 的各上游今日调用摘要（名称、请求数、成功/失败或成功率）。默认折叠，不抢四域首页。

## 2. 分支与提交

- 分支：`draft/ops-p1-upstream-panel`
- 提交：`feat(desktop): folded ops upstream-daily model channel`
- 禁止 push main；禁止 `git add -A`

## 3. 白名单

- `desktop/Sources/CCCDesktop/OpsView.swift`
- `desktop/Sources/CCCDesktop/AppModel.swift`
- `desktop/Sources/CCCDesktop/APIClient.swift`
- `desktop/Sources/CCCDesktop/BoardOpsModels.swift`

## 4. 黑名单

- `scripts/**`
- `docs/product/**`
- `~/.ccc/**`
- 其它未列路径

## 5. 现状锚点

- Hub：`GET /api/ops/upstream-daily`（`scripts/chat_server/routers/ops.py`）返回 `{ ok, upstreams: [...] }`
- Desktop 尚无 `fetchOpsUpstreamDaily`
- OpsView 已有 DisclosureGroup「后勤与舰队」等折叠范式，照抄样式

## 6. 实现步骤

1. `BoardOpsModels`：最小 Codable（字段用可选，兼容缺省）：如 `name`、`requests`/`count`、`ok_rate`/`success_rate`、`errors` 等——以实际 JSON 键为准，解码失败勿崩。
2. `APIClient.fetchOpsUpstreamDaily()` → `api/ops/upstream-daily`
3. `AppModel`：`opsUpstreamDaily` 状态；在 `refreshOps` 末尾顺带拉取（失败则空列表，不抬红）
4. `OpsView`：DisclosureGroup「模型通道」，列表每行 name + 简要数字；空则「暂无用量」
5. `cd desktop && swift build`

## 7. 验收

```bash
cd desktop && swift build
rg -n "upstream-daily|UpstreamDaily|模型通道" desktop/Sources/CCCDesktop/
```

## 8. 做完回报

```
BRANCH: draft/ops-p1-upstream-panel
FILES:
- …
TESTS:
- swift build → …
RESIDUAL:
- …
```
