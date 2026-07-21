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
| F5-1 | 桌面端中栏渲染 + 工具调用体验 | 壳 | Auto | **done `0c65257`** |
| **F5-2** | **Cursor 式滚动留白（发消息上推 + 下方空槽）** | **壳** | **Auto** | **accepted · 待执行** |

用户点哪条，架构出 brief；否则流水线休眠。

---

## 粘贴包 A · 壳窗（F5-2 · Cursor 式滚动留白）

```
执行 brief：docs/briefs/2026-07-21-f5-2-cursor-scroll-pad.md
模型：Auto
白名单（只改）：
  desktop/Sources/CCCDesktop/ContentView.swift（仅 CodexChatPaneBody 的 messageArea / scroll / 相关 @State）

根因：scroll() 一律 scrollTo(tipId, anchor: .bottom) → 把底部空 Spacer 钉进视口，用户气泡被顶出，中间只剩空白。
F5-1 首条顶部 Spacer 是半吊子，与钉 tip 冲突，本 brief 删除该条件块。

照做：
1. 底部 Spacer → max(h*0.55, 220)；删 count==1 顶部 Spacer。
2. 重写 scroll()：
   - 切会话/重入：scrollTo(lastMessageId, anchor: .top)（无动画）
   - 刚发送/等首包：scrollTo(本轮 userId, anchor: .top)
   - 流式内容变长：跟滚 last assistant（anchor: .bottom）或 tip 用 .top —— 禁止 scrollTo(tipId, anchor: .bottom)
3. 自检：bash scripts/ccc-self-check.sh
   cd desktop && swift build -c release
   杀旧进程再起 release 二进制，勿测 debug。

完成后回贴：commit hash + 自检结果。架构验收。
```

---

## 粘贴包 B · 编排窗

```
H-2 已合入 4d45d74。无活跃 brief。等用户点下一项。
```
