# Hub-Shell Phase17 — Desktop 对话模型快选（验收记录 · green）

> **状态**：✅ green · Cursor  
> **对齐**：[`hub-shell-phase17-model-picker-brief.md`](hub-shell-phase17-model-picker-brief.md) · [`dev-channel.md`](dev-channel.md)  
> **版本**：v0.52.2 · **日期**：2026-07-21

---

## 一句话

Composer + Settings 短列表选对话模型逻辑名；默认 **MiniMax-M3**（`flash`）；`@AppStorage("ccc.preferredModel")` 持久化；按请求传 sidecar。上游出口仍由 sidecar plist 定；不碰 shell / 个人 Claude；**不含**默认 118。

---

## 改动

| 文件 | 内容 |
|------|------|
| `StreamSessionController.swift` | `modelPickerOptions` / `modelDisplayName`；`minimax-m3`→`flash` |
| `ContentView.swift` | Composer + Settings 共用短列表；切换 toast |
| `AppModel.swift` | 默认 `flash` 注释对齐 MiniMax-M3 |
| `ccc-agent-sidecar.py` | `/health` `model_labels`；`model_per_request` 已有 |
| `install-agent-sidecar-plist.sh` | 头注释：UI 覆盖 vs plist 默认 |

**未改**：Engine OpenCode 选型；个人 Claude / `~/.zshenv`；默认启用 118。

---

## UI vs plist

| 层 | 职责 |
|----|------|
| Desktop `ccc.preferredModel` | 请求体 `model`（逻辑名 flash/code/sonnet/haiku） |
| sidecar launchd plist | `ANTHROPIC_BASE_URL` / key → 现网 MiniMax 出口 |
| 个人 Claude Code | **无关** |

---

## 验收

### 自动化

```text
swift build -c release + package-baseline + /Applications install:
  2026-07-21 14:17 /Applications/CCCDesktop.app/Contents/MacOS/CCCDesktop
  2026-07-21 14:17 …/desktop/.build/CCCDesktop.app/Contents/MacOS/CCCDesktop
  CFBundleShortVersionString=0.52.2
check-version-sync: VERSION sync OK (v0.52.2)
sidecar /health: model_labels + model_per_request=true（重装 plist 后）
```

### 手测表

| # | 结果 |
|---|------|
| 默认 | 新装/空偏好 → MiniMax-M3（flash） |
| 切换 | Composer/Settings 改选 → toast「对话模型：…」；下条消息带所选 `model` |
| 重启 | 仍记住 `ccc.preferredModel` |
| 失败 | sidecar/Agent 错误路径既有 toast（未改协议） |

---

*实现：Cursor · 终验：规划方*
