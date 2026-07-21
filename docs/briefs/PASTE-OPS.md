# PASTE-OPS · 工厂派单板（用户只复制）

> 架构窗维护本文件。用户：**不讨论、不加需求**，按序把「粘贴包」贴进对应窗。  
> 模型路由：[`../product/cursor-model-routing.md`](../product/cursor-model-routing.md)

## 流水线状态

| 序号 | brief | 状态 | 窗 |
|------|-------|------|-----|
| F0 | 建制 | done `94da446` | — |
| F1 | 断线恢复 | done `eeaf388` | — |
| F1-2 | 投递三态零谎报 | done `578e7fe` | — |
| F2-1 | soak N=5 + orphan=0 | done `9af1fb4` | — |
| F2-2 | 双机版本对齐核对 | done `555b9bc` | — |
| F3-1 | qb 业务向闭环 | done `327fd86` | — |
| F3-2 | hp 业务向闭环 | done `6523330` | — |
| F3-3 | xianyu 业务向闭环 | done `1526ca1` | — |

**✅ 流畅基线达成** — [`../product/fluency-baseline-achieved.md`](../product/fluency-baseline-achieved.md)

---

## 下一步候选（按需，无活跃 brief）

| ID | 项 | 窗 | 模型 | 状态 |
|----|----|----|------|------|
| H-1 | `epic_done` 流事件补齐 | 编排 | Auto | **done `461f021`** |
| 版本 bump | v0.52.2 → 流畅基线签 | 架构 | 高级 | **done v0.53.0** |
| F4-1 | 显式 Context Engineering | 编排 | 高级 | **done `1ee2080`** |
| F4-2 | Memory 沉淀（lessons） | 编排 | Auto | **done `4ed4774`** |
| F4-3 | Proactive 触发（CI/hook） | 编排 | 高级 | **done `580dd92`** |
| H-2 | `work_status` 后续阶段流事件 | 编排 | Auto | **done `4d45d74`** |
| **F5-1** | **桌面端中栏渲染 + 工具调用体验** | **壳** | **Auto** | **accepted · 待执行** |

用户点哪条，架构出 brief；否则流水线休眠。

---

## 粘贴包 A · 壳窗（F5-1 · 桌面端中栏 UX 修复）

```
执行 brief：docs/briefs/2026-07-21-f5-1-desktop-middle-pane-ux.md
模型：Auto
白名单（只改这些）：
  desktop/Sources/CCCDesktop/Components/MarkdownText.swift
  desktop/Sources/CCCDesktop/Components/ToolProgressRail.swift
  desktop/Sources/CCCDesktop/ContentView.swift（仅 CodexChatPaneBody / messageArea / beginPaneSwitchTransition / scroll）
  desktop/Sources/CCCDesktop/AppModel.swift（仅 .toolResult 事件分支 + ToolStep resultHint 相关）
  desktop/Sources/CCCDesktop/Models.swift（仅 ToolStep 加 resultHint 字段，Codable 向后兼容）

七项缺陷 brief 第 4 节已逐条定位根因 + 修复方案，照做即可：
  A. Markdown 失真：MarkdownText.swift bold 分支 weight .regular → .semibold；heading weight 分档。
  B. 绿勾过早：AppModel.swift .toolResult 分支删掉 `if allDone { toolsFinished = true }`；只在 .done 置 true。
  C. 工具调用闪：ToolProgressRail.swift 移除 `.animation(value: steps.count)`；只对 finished 动画；DisclosureGroup 稳定 id。
  D. 过程摘要：ToolStep 加 resultHint；AppModel 在 toolResult 推断一句；rail 顶部显示当前 + 展开见历史。
  E. 进度轨：runningBlock 下方加 3pt 分段进度轨（done/running/error/未达）。
  F. 新对话首条位置：displayMessages.count==1 且 user 且未 streaming 时，LazyVStack 顶部插 Spacer 压到中上。
  G. 切换漂移：beginPaneSwitchTransition 里先钉底（遮罩期内）再恢复 opacity；恢复用 disablesAnimations 直跳 1。

自检：
  bash scripts/ccc-self-check.sh
  cd desktop && swift build   # 无工具链则跳过并备注

完成后回贴：commit hash + 自检结果。架构验收。
```

---

## 粘贴包 B · 编排窗

```
H-2 已合入 4d45d74。无活跃 brief。等用户点下一项。
```
