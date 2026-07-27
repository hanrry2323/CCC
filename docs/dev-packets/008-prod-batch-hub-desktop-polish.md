# DEV-PACKET: prod-batch-hub-desktop-polish

> **大包长任务**：一次会话做完下方全部 Phase，只回报一次。  
> 合入权威 = Cursor。做完只提交到指定分支，**不要 push main**。  
> 先：`git checkout main && git pull`，再开分支。

## 1. 总目标（用户可见）

把「网页运维已停更」对齐到看板入口，并做一轮 Desktop 运维抛光，减少半成品感：

1. 网页 Hub `#/board` 也改为 Desktop-first 提示（与 `#/ops` 同风格；**保留** `#/console`）  
2. 标题栏或明显位置能看到运维红点（若侧栏已有角标，标题栏再补一点即可）  
3. 运维集群区 Hub chip **不要**在只有 `hub_port_7777` 时谎称「隧道 :17777」；隧道状态以 `serverURLString` / 隧道行准  

做完后 `swift build` + `node --check` 相关 js 全绿。

## 2. 分支与提交

- 分支：`draft/prod-batch-hub-desktop-polish`
- **可以多个 commit**（按 Phase），最后一次会话结束时分支干净可审  
- 建议 commit messages：
  - `feat(hub-spa): Desktop-first notice for web #/board`
  - `feat(desktop): titlebar ops severity cue`
  - `fix(desktop): Hub chip not pretend tunnel from :7777 ok`
- 禁止 push main；禁止 `git add -A`（每次只 add 本 Phase 白名单文件）

## 3. 白名单（整包允许）

- `scripts/chat_server/frontend/js/pages/boardPage.js`
- `scripts/chat_server/frontend/js/app.js`（标题文案等最小改）
- `scripts/chat_server/frontend/js/router.js`（若需要）
- `desktop/Sources/CCCDesktop/OpsView.swift`
- `desktop/Sources/CCCDesktop/AppModel.swift`（仅标题栏/状态暴露需要时）
- `desktop/Sources/CCCDesktop/TitlebarUsageAccessory.swift`
- `desktop/Sources/CCCDesktop/ContentView.swift`（仅接线需要时）
- `desktop/Sources/CCCDesktop/Theme.swift`（仅颜色需要时）

## 4. 黑名单

- `scripts/_ops_probe.py`、`scripts/ccc-engine.py`、`scripts/engine/**`
- `docs/product/loop-engineer-authority.md`
- `~/.ccc/**`、真密钥、plist
- `relay/upstreams.json`
- 其它未列路径

---

## Phase A — 网页 `#/board` Desktop-first（约 30–60 分钟）

**参照**：`scripts/chat_server/frontend/js/pages/opsPage.js` 的 `mountOps` 静态提示页。

**做：**

1. 改 `boardPage.js` 的 `mountBoard`：不要再拉完整看板 SPA 主 UI（或入口即替换为提示页）。  
2. 中文文案建议：  
   - 标题：看板已迁入 CCC Desktop  
   - 正文：网页看板停更。请在 CCC Desktop 左侧选项目 / 看板查看。  
   - 链：`#/console` 兜底；可选链回对话说明（不要链回已停更的 ops 当主路径）  
3. `unmountBoard` 清掉 timer/listener（若有）。  
4. `app.js` 里 board 路由标题改为含「停更，请用 Desktop」类似 ops。  
5. `node --check` 改过的 js。

**Phase A 自检：**

```bash
node --check scripts/chat_server/frontend/js/pages/boardPage.js
node --check scripts/chat_server/frontend/js/app.js
rg -n "Desktop|停更|mountBoard" scripts/chat_server/frontend/js/pages/boardPage.js scripts/chat_server/frontend/js/app.js
```

---

## Phase B — 标题栏运维红点（约 45–90 分钟）

**现状**：侧栏 SoftRow「运维」已有 `opsDisplayAlertCount` 角标；`TitlebarUsageAccessory` 目前偏用量。

**做：**

1. 读 `TitlebarUsageAccessory.swift` + 它在 `ContentView` / 窗口的挂载点。  
2. 当 `model.opsDisplaySeverity == "red"` 或 `opsDisplayAlertCount > 0` 时，在标题栏配件显示小红点或「运维 N」短标记（点击可 `selectDestination(.ops)` 若方便）。  
3. 绿/无红时不打扰（不显示或极淡）。  
4. 不要重做整个 Titlebar；最小改动。  
5. `cd desktop && swift build`

**Phase B 自检：**

```bash
cd desktop && swift build
rg -n "opsDisplaySeverity|opsDisplayAlertCount|运维" desktop/Sources/CCCDesktop/TitlebarUsageAccessory.swift desktop/Sources/CCCDesktop/ContentView.swift
```

---

## Phase C — Hub chip 不再假冒隧道（约 20–40 分钟）

**现状**：`OpsView.clusterSummarySection` 里 Hub chip 在 `hubOk` 时 subtitle 写「隧道 :17777」，但 `hubOk` 来自 `hub_port_7777`，语义错位。隧道行已用 `serverURLString.contains(":17777")`。

**做：**

1. Hub chip：  
   - 通：`编排 :7777` 或 `Hub 通`  
   - 不通：`7777 异常`  
2. **隧道**只由隧道状态行 / tunnelOk 表达（已有）。  
3. `swift build`

**Phase C 自检：**

```bash
cd desktop && swift build
rg -n "隧道 :17777|hub_port_7777|tunnelOk" desktop/Sources/CCCDesktop/OpsView.swift
# Hub chip 行不应在 hubOk 时写死「隧道 :17777」
```

---

## 4. 整包验收（全部 Phase 完成后跑）

```bash
git checkout main && git pull  # 仅确认你已从最新 main 开的分支；不要混用
git status
cd desktop && swift build
node --check scripts/chat_server/frontend/js/pages/boardPage.js
node --check scripts/chat_server/frontend/js/pages/opsPage.js
node --check scripts/chat_server/frontend/js/app.js
rg -n "停更|Desktop|opsDisplay|编排 :7777|tunnelOk" \
  scripts/chat_server/frontend/js/pages/boardPage.js \
  scripts/chat_server/frontend/js/app.js \
  desktop/Sources/CCCDesktop/OpsView.swift \
  desktop/Sources/CCCDesktop/TitlebarUsageAccessory.swift
```

## 5. 做完回报（只交一次）

```
BRANCH: draft/prod-batch-hub-desktop-polish
COMMITS:
- …（列出）
FILES:
- …
PHASES:
- A: pass/fail + 一句
- B: pass/fail + 一句
- C: pass/fail + 一句
TESTS:
- swift build → …
- node --check → …
RESIDUAL:
- …
```

## 6. 纪律提醒

- 同一工作树：只 add 白名单文件；提交前 `git status` 确认无混入。  
- 遇不确定 API/字段：选保守实现（不崩、不抬红），写在 RESIDUAL。  
- 不要改权威文档、不要动 2017 生产配置。
