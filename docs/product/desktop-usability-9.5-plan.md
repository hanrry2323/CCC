# Desktop 可用性 9.5 — 开发计划 SSOT

> 版本：2026-07-20 · 目标：启发式综合分 **≥ 9.5**（同权重，不刷分）  
> 基线：[可用性评分卡](../../.cursor/projects/Users-apple-program-CCC/canvases/desktop-usability-scorecard.canvas.tsx) **7.2**  
> 执行跟踪：仓库根 `task_plan.md` / `progress.md` / `findings.md`

---

## 一句话

把 Desktop 从「熟手能用的内部工具」做成「首启可自学、半成品收口、热路径无障碍、体感流畅」的产品面，**一次交付、同量尺复评 ≥ 9.5**。

---

## 评分门禁

| 维度 | 权重 | 基线 | 目标 |
|------|------|------|------|
| 信息架构 | 15% | 8.0 | 9.5 |
| 主任务路径 | 20% | 7.5 | 9.6 |
| 状态反馈 | 15% | 8.5 | 9.5 |
| 可学性/首启 | 12% | 5.0 | 9.5 |
| 容错与恢复 | 10% | 7.5 | 9.5 |
| 效率/熟手 | 10% | 7.0 | 9.5 |
| 视觉一致 | 8% | 7.5 | 9.5 |
| 无障碍 | 5% | 4.5 | 9.5 |
| 体感性能 | 5% | 6.0 | 9.5 |
| **综合** | 100% | **7.2** | **≥9.5** |

验收任务（人工 5 分钟）：
1. 冷启 → 看懂空态三步 → 发一句 → 点「定稿」→ 确认转任务 → 右栏出现流程  
2. ⌘F 搜历史消息并点进结果  
3. VoiceOver 能读出：项目卡、发送、转任务、停止  

---

## 工作包（按依赖序）

### WP1 — Trust & Completeness（P0）

| ID | 项 | 文件 | 验收 |
|----|----|------|------|
| T1 | 搜索结果列表可点开线程 | `ContentView` `AppModel` | 点击结果进入对应会话 |
| T2 | 空对话三步引导 | `ContentView` | 无消息时显示：聊目标 → 定稿 → 转任务 |
| T3 | 移除「用户」假入口 | `ContentView` | 侧栏无欺骗性账号行 |
| T4 | 重置对话确认 | `ContentView` | 二次确认后才 reset |
| T5 | 重命名会话 UI | `ContentView` | contextMenu「重命名」弹出可提交 |

### WP2 — Learnability

| ID | 项 | 文件 | 验收 |
|----|----|------|------|
| L1 | 快捷芯片 help | `ContentView` | hover 说明产出 |
| L2 | 「用法」HelpSheet | `ContentView` `AppModel` | 侧栏可打开主路径说明 |
| L3 | 首启 tip（一次） | `AppModel` `@AppStorage` | 首次打开可关闭横幅 |
| L4 | 转任务人话门禁 | `ContentView` | 未就绪时解释缺什么，非灰按钮裸死 |

### WP3 — Power

| ID | 项 | 文件 | 验收 |
|----|----|------|------|
| P1 | 菜单快捷键 | `CCCDesktopApp` | ⌘N ⌘F ⌘1/2/3 ⌘⇧T |
| P2 | 看板/运维回对话 | 已有；补「看编排」提示 | 文案一致 |
| P3 | SoftRow a11y | `Vibrancy.swift` | VoiceOver 读标题与选中态 |

### WP4 — A11y + Perf

| ID | 项 | 文件 | 验收 |
|----|----|------|------|
| A1 | Composer / 发送 / 停止标签 | `ComposerTextView` `ContentView` | VO 可操作发送 |
| A2 | 消息操作条标签 | `ContentView` | 复制/转任务有标签 |
| A3 | Flow 节点 / 空态 | `FlowCanvasView` | 节点可读 |
| A4 | 预热可见反馈 | `AppModel` / status | 冷启不假死；可显示预热 |
| A5 | Board 列标题 a11y | `BoardView` | 列名可读 |

### WP5 — Polish

| ID | 项 | 文件 | 验收 |
|----|----|------|------|
| S1 | Settings 分组人话 | `ContentView` SettingsView | Hub / Agent / 路径分区 |
| S2 | Flow UX 文档对齐竖轨 | `desktop-flow-rail-ux.md` | 不再承诺未实现 DAG |
| S3 | CHANGELOG | `CHANGELOG.md` | 记录可用性冲刺 |
| S4 | 复评 canvas | canvases | 综合 ≥9.5 |

---

## 明确不做

- 真力导向 / 多列 DAG（成本高，改文档）
- 账号系统
- 把 OpenCode 嵌进 Desktop
- 调低评分权重「刷到 9.5」

---

## 工期与一次交付

本计划在**单次 Agent 会话**内实现 WP1–WP5 并复评。若 `swift build` 失败，以修编译为最高优先，再复评。

## 风险

| 风险 | 缓解 |
|------|------|
| ContentView 过大易冲突 | 按区块 StrReplace；少次大改 |
| 多窗串台 | 跳转只经 `WindowChatState` |
| 评分主观 | 固定权重 + 验收任务清单 |

---

## 关联

- 架构：`ccc-desktop-architecture.md`
- 右栏：`desktop-flow-rail-ux.md`
- 性能债：`.trae/documents/desktop-perf-chat-latency-optimization.md`
- 边界：`dialogue-orchestration-boundary.md`
