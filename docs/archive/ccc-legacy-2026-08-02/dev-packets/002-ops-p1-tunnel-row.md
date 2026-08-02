# DEV-PACKET: ops-p1-tunnel-row

> 复制本文件全文发给**个人 Claude Code CLI**（非 Desktop Agent）。  
> 合入权威 = Cursor。做完只提交到指定分支，**不要 push main**。

## 1. 目标（用户可见）

运维「集群与服务」里，Hub 相关展示以 **本机隧道 `127.0.0.1:17777`** 为主叙事（符合 Hub SSH 隧道硬共识），而不是只写「7777 通」。用户能一眼看到隧道端口 + `com.ccc.hub-tunnel` 提示。

## 2. 分支与提交

- 分支：`draft/ops-p1-tunnel-row`
- 提交：`feat(desktop): surface Hub tunnel :17777 on Ops cluster strip`
- **禁止** push main；**禁止** `git add -A`

## 3. 白名单（只许改这些）

- `desktop/Sources/CCCDesktop/OpsView.swift`
- `desktop/Sources/CCCDesktop/BoardOpsModels.swift`（仅当需要为 cluster 增加可选字段解码时；优先不改模型）

## 4. 黑名单（碰了就停）

- `scripts/_ops_probe.py`（本包不做后端；Hub 真探活留给 Cursor）
- `docs/product/loop-engineer-authority.md`
- `~/.ccc/**`
- 其它未列路径

## 5. 现状锚点

- `OpsView.clusterSummarySection`（约 L331+）
- 现有 Hub chip：`hub_port_7777` → 文案「7777 通」
- 已有弱提示一行：`本机 Hub 隧道默认 127.0.0.1:17777（launchd com.ccc.hub-tunnel）`（约 L368）

## 6. 实现步骤

1. 将 Hub chip 副标题改为突出隧道：例如主文案 `隧道 :17777`，副文案保留 launchd 名；7777 仅作次要（「编排环回」）或不在 chip 抢戏。
2. 把 L368 弱提示升级为与其它 chip 同级的信息行或第四枚 chip「隧道」，**不要**再只靠灰色小字。
3. **不要**在本包用本机 `nc`/launchctl 写死探活到模型层（无 API 字段时，用文案 + `AppModel.serverURLString` 是否含 `17777` 做弱状态即可）。
4. `cd desktop && swift build`。

## 7. 验收（必须跑）

```bash
cd desktop && swift build
rg -n "17777|hub-tunnel|隧道" desktop/Sources/CCCDesktop/OpsView.swift
# 集群区应出现 17777 / 隧道 字样，且不仅是一行 faint caption
```

## 8. 做完回报（固定格式）

```
BRANCH: draft/ops-p1-tunnel-row
FILES:
- …
TESTS:
- swift build → …
RESIDUAL:
- …
```
