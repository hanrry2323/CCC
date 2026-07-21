# Hub-Shell Phase16 — Desktop 本地优先冷启动（验收记录 · green）

> **状态**：✅ green · Cursor  
> **对齐**：[`hub-shell-phase16-cold-start-brief.md`](hub-shell-phase16-cold-start-brief.md)  
> **版本**：v0.52.1（未 bump）· **日期**：2026-07-21

---

## 一句话

`AppModel.init` 同步灌 `projects-cache` + 选中会话消息/flow；有缓存则立刻 `connected`；Hub/`ensureLocalAgent` 改后台 `refreshProjects(showBusy: false)`，首屏不再假离线、不再全局 busy 转圈。

---

## 改动

| 文件 | 内容 |
|------|------|
| `AppModel.swift` | `hydrateFromDiskSync()`；`hubSyncing`；`bootstrap` 后台刷新；`refreshProjects(showBusy:)` |
| `ContentView.swift` | 有 `projects` 即出侧栏；状态栏 Hub 同步指示 |

**未改**：Phase14 绑定 / Phase15 卡片 / Hub 协议 / Board·Ops 缓存。

---

## 验收

### 自动化

```text
swift build -c release: OK (~28s)
package-baseline + install:
  2026-07-21 14:10 /Applications/CCCDesktop.app/Contents/MacOS/CCCDesktop
  2026-07-21 14:10 …/desktop/.build/CCCDesktop.app/Contents/MacOS/CCCDesktop
pytest -k phase14|flow|snapshot|epic_done|stoploss: 17 passed
check-version-sync: VERSION sync OK (v0.52.1)
```

### 手测

| # | 结果 |
|---|------|
| 有缓存冷启 | init 即 `connected`；侧栏不走 `offlineBlock` |
| Hub 后台 | `hubSyncing` + 状态「本机缓存 · Hub 同步中…」→ 完成后 `updateConnectionStatusText` |
| Hub 断 | 保留缓存；toast「可聊；转任务暂不可用」；`canTransfer` 仍要 hubReachable |
| 无缓存首启 | 行为同前：等 refresh / offline |

---

## 风险

- 后台 `Task` 与手动 `reconnect()` 可能并发 refresh（可接受；HubRequestGate 限流）
- UI smoke 轮询 `hubSyncing` 最多等首轮后台 refresh

---

*实现：Cursor · 终验：规划方*
