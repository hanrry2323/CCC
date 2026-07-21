# Hub-Shell Phase16 — Desktop 本地优先冷启动（开发 Brief）

> **性质**：需求 / 验收 brief  
> **日期**：2026-07-21  
> **执行者**：**Cursor**（R-15；[`dev-channel.md`](dev-channel.md)）  
> **版本**：`VERSION` = **v0.52.1**（默认不 bump）  
> **前置**：Phase14/15 已 green；本阶段**不改**绑定/SSE/卡片字段逻辑

---

## 目标一句话

**重复启动时：侧栏 + 上次会话消息 + 右栏 flow 从本机缓存秒开；Hub / sidecar 在后台同步，不挡首屏。**

---

## 必须做

| # | 需求 | 成功标准 |
|---|------|----------|
| A | **磁盘优先 hydrate** | `AppModel.init`（或同等同步路径）灌 `projects-cache` + 选中项目 threads/messages/flow |
| B | **首屏不假离线** | 有缓存时 `connected=true`，侧栏立刻出项目卡；禁止等 Hub 才出列表 |
| C | **Hub 后台刷新** | `bootstrap` 不因 `fetchProjects`/`bindFlow` 阻塞首屏；可达时后台覆盖缓存 |
| D | **权威不丢** | Hub 空响应仍不得抹本地消息/flow（既有规则保留） |
| E | **转任务门槛不变** | `canTransfer` 仍要 `hubReachable` |
| F | **文档+装机** | 验收记录 / 状态板 / roadmap / CHANGELOG；`package` + `/Applications` stat 一致 |

## 明确不做

- Board/Ops 本地缓存  
- Phase14/15 绑定与卡片重做  
- 冷启动无缓存时的「假项目」发现  
- 改控制面 / Hub 协议破坏性变更  

---

## 验收

```bash
cd desktop && swift build -c release
bash desktop/scripts/package-baseline.sh
rm -rf /Applications/CCCDesktop.app && cp -R desktop/.build/CCCDesktop.app /Applications/
stat -f '%Sm %N' -t '%Y-%m-%d %H:%M' \
  /Applications/CCCDesktop.app/Contents/MacOS/CCCDesktop \
  desktop/.build/CCCDesktop.app/Contents/MacOS/CCCDesktop
pytest tests/scripts/ -q --tb=short -k 'phase14 or flow or snapshot or epic_done or stoploss'
```

手测：有本机缓存时杀进程重开 → **1s 内**见侧栏项目与上次对话（Hub 可断）；Hub 通后状态栏从「同步中」变为正常；转任务在 Hub 不通时仍禁用。

---

## 完成回复格式

```text
Phase16 DONE
- HEAD / VERSION / Commits
- 装机证伪（两行 stat）
- 自动化 / 手测
- 已知风险 / 下一步
```
