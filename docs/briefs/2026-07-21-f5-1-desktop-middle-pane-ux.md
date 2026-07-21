# F5-1 · 桌面端中栏渲染与工具调用体验修复

## 元信息

| 字段 | 填写 |
|------|------|
| brief_id | `F5-1-20260721-desktop-middle-pane-ux` |
| 波次 | F5（流畅基线后 UX 打磨） |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |

## 1. 目标

修复桌面端中栏（对话区）七项渲染/体验缺陷：Markdown 失真、工具调用绿勾过早、工具调用闪烁、工具调用无过程摘要、缺进度条式展示、新对话首条位置不佳、对话切换漂移。

## 2. 非目标

- 不改右栏 Flow / 看板 / 运维。
- 不改 sidecar / Hub API 契约。
- 不改消息持久化 schema（`ChatMessage` Codable 字段不动）。
- 不引入第三方 Markdown 库；继续用 `MarkdownText.swift` 自实现。
- 不动 `scripts/`（编排面资产）。

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| transfer-gate | 无 | |
| flow-events | 无 | |
| hub-api-v1 | 无 | |
| 其它 docs | 无 | 纯 UI 行为修复，无契约 |

## 4. 缺陷定位与修复方案（架构已定位根因）

### 缺陷 A · Markdown 格式失真

**根因**：`desktop/Sources/CCCDesktop/Components/MarkdownText.swift`
- 第 286 行：`**bold**` 渲染用 `.system(size: 14.5, weight: .regular)` —— weight 是 `.regular`，粗体不粗。
- 第 96–100 行：heading 字体也是 `.regular` weight —— 标题不突出。
- italic 分支（第 305 行）weight 正常，但 bold 分支错误。

**修复**：
- bold 分支改为 `.system(size: 14.5, weight: .semibold)`（与正文 `.regular` 拉开档位）。
- heading 字体：`level 1 → .bold`，`level 2 → .semibold`，`level 3 → .medium`，其余 `.regular`；size 保持现值。
- 验证：含 `**粗体**`、`## 标题`、`` `code` ``、`*斜体*` 的回复渲染后视觉可区分。

### 缺陷 B · 工具调用绿勾过早出现（核心 bug）

**根因**：`desktop/Sources/CCCDesktop/AppModel.swift` 第 2684–2688 行，`.toolResult` 事件处理：
```swift
let allDone = !msgs[idx].toolSteps.isEmpty
    && msgs[idx].toolSteps.allSatisfy { $0.status != .running }
if allDone {
    msgs[idx].toolsFinished = true   // ← BUG：工具间空隙也命中
}
```
agent 连续调用多个工具时，每个 toolResult 后、下一个 toolUse 前的瞬间 `allDone=true` → `toolsFinished=true` → `ToolProgressRail` 走 `finishedBlock`（绿勾）。下一个 toolUse 又把它翻回 `false`。绿勾在工具间反复闪烁，误导用户以为已完成。

**修复**：
- 删除 `.toolResult` 分支里 `if allDone { msgs[idx].toolsFinished = true }` 这段。
- `toolsFinished` **只**在 `.done`（turn 结束）事件里置 `true`（第 2696–2702 行已正确，保留）。
- 个别 toolResult 只更新该 step 的 `.status`（`.done`/`.error`），不动 `toolsFinished`。
- 同理核查第 2479–2487、2539–2542、2740–2743 行其它 done/cancel 路径：那些是 turn 终态，保留置 true。

**验收**：连续 3+ 工具调用过程中，绿勾**全程不出现**；只有 turn 真正结束后才打勾。

### 缺陷 C · 工具调用每次刷新闪一下

**根因**：`desktop/Sources/CCCDesktop/Components/ToolProgressRail.swift`
- 第 158 行 `.animation(.easeOut(duration: 0.15), value: steps.count)` —— 每次追加 step 触发整块动画重布局。
- `@State expanded` + `onAppear { expanded = !finished }` —— 父视图 body 重求值时 DisclosureGroup 重建可能闪。
- `runningBlock` 里 `steps.last` 变化 + 「先前 N 步」DisclosureGroup 随 count 出现/消失。

**修复**：
- 移除 `.animation(..., value: steps.count)`；改为只对 `finished` 做单次折叠动画（`.animation(.easeOut(duration: 0.2), value: finished)`）。
- `expanded` 初值仍 `!finished`，但用 `.onChange(of: finished)` 单向收敛（完成后折叠），**不**在 onAppear 反复重算。
- 「先前 N 步」DisclosureGroup 用稳定 `id`（如 `prior-steps`），避免 count 变化时销毁重建。
- stepList 用 `ForEach(list, id: \.id)`（已有），确保 step 追加是 insert 不是 rebuild。

**验收**：连续追加 5 个 toolStep，rail 不闪、不跳高度；只在新 step 出现时平滑插入一行。

### 缺陷 D · 工具调用缺过程摘要 / 轮播

**现状**：`runningBlock` 只显示 `steps.last` 的 label（如「查阅文件 · foo.swift」），完成 step 不可见结果。

**修复**：
- `runningBlock` 顶部增加「当前调用」一行：调用时显示 `ToolProgressHelper.humanLabel` 简介；toolResult 后追加一句结果摘要（成功/失败 + 文件名或命令尾 36 字）。
- 结果摘要来源：`.toolResult` 事件目前只有 `ok: Bool`，无 payload。**不改 sidecar 契约**；改为在 `ToolStep` 里存 `resultHint: String?`，由 `AppModel` 在 toolResult 时根据 step.name + 已知 input 推断一句（如 Write → `已写入 foo.swift`，Bash → `命令完成`，Grep → `搜索完成`）。失败统一 `调用失败`。
- 「先前 N 步」展开后，每步显示 `label` + `resultHint`（如有），形成可读的过程流。
- 不做自动轮播动画（会再引入闪）；用「当前行 + 可展开历史」即可。

**验收**：3 个工具调用后，rail 顶部显示最新一句结果；展开可见每步简介 + 结果。

### 缺陷 E · 缺进度条式展示

**参考**：旧 http 页用横向进度条段表示已完成工具数 / 总数。

**修复**：在 `runningBlock` 与 `finishedBlock` 的摘要行下方，加一条**细进度轨**（高 3pt）：
- 段数 = `steps.count`；每段宽度均分；`.done` 填 `CCCTheme.nodeDone`，`.running` 填 `CCCTheme.accent`（带 ProgressView 微动），`.error` 填 `CCCTheme.nodeFail`，未到达段填 `CCCTheme.hover`。
- turn 未结束（`!finished`）时显示；`finished` 后折叠进 finishedBlock 摘要即可（不强制展示轨）。
- 用 `HStack(spacing: 2)` + `RoundedRectangle` 即可，不引入新依赖。

**验收**：5 步工具调用中，轨上有 3 绿 1 蓝（进行中）1 灰（未达）；视觉即知进度。

### 缺陷 F · 新对话首条用户消息位置

**现状**：`messageArea` 底部有 `Spacer().frame(height: max(geometry.size.height * 0.35, 120))`，把内容整体上推。但新对话只有 1 条 user 消息时，它贴在最顶，下方留白过大、上方无留白。

**修复**：
- 当 `displayMessages.count == 1 && displayMessages.first?.role == "user" && !paneStreaming` 时（首轮已发、未回或刚回），在 `LazyVStack` 顶部插入 `Spacer().frame(height: max(geometry.size.height * 0.28, 140))`，把首条 user 气泡压到中上区。
- 一旦 assistant 开始 streaming（`paneStreaming` 或 `displayMessages.count > 1`），移除该顶部 Spacer，恢复正常钉底。
- 用条件 View 切换，**不**用动画（避免首条弹跳）。

**验收**：发首条消息后，user 气泡位于中上区，下方留足空间给回复；回复开始后气泡序列正常从上往下、钉底。

### 缺陷 G · 对话切换漂移 / 闪屏

**现状**：`beginPaneSwitchTransition()` 已做 opacity 0 + spinner 320ms。但用户仍见「对话在对话框漂移显示一下」—— 因为 opacity 恢复后 `scroll()` 的 `needsInstantBottomPin` 走 `withTransaction(disablesAnimations)` 钉底，但 LazyVStack 在 opacity 恢复瞬间可能先以顶对齐渲染一帧再跳底。

**修复**：
- 在 `beginPaneSwitchTransition` 里，**先** `pinBottomOnNextScroll()` + 立刻对 `proxy` 做一次 `withTransaction(disablesAnimations)` 钉底（此时 opacity=0，用户看不见），再等 320ms 恢复 opacity。
- 即把「钉底」提前到遮罩期内完成，而不是恢复 opacity 后再钉。
- 恢复 opacity 时 `paneContentOpacity` 用 `withTransaction(disablesAnimations)` 直接置 1（不要 easeOut 0.42，那会让人看到从上滑下）。
- 切换后 `lastScrollTargetId` 直接设为最后一条消息 id，避免 scroll() 再判 streaming 节流。

**验收**：从会话 A 切到会话 B（B 有 20 条消息），不出现「从顶滚到底」的漂移；直接显示末条附近。

## 5. 分工白名单

| 面 | 是否参与 | 允许改动的路径 | 禁止 |
|----|----------|----------------|------|
| 壳 | 是 | `desktop/Sources/CCCDesktop/Components/MarkdownText.swift` · `desktop/Sources/CCCDesktop/Components/ToolProgressRail.swift` · `desktop/Sources/CCCDesktop/ContentView.swift`（仅 `CodexChatPaneBody` / `messageArea` / `beginPaneSwitchTransition` / `scroll`） · `desktop/Sources/CCCDesktop/AppModel.swift`（仅 `.toolResult` 事件分支 + `ToolStep` resultHint 相关） · `desktop/Sources/CCCDesktop/Models.swift`（仅 `ToolStep` 加 `resultHint` 字段，Codable 向后兼容） | 改 sidecar / Hub / scripts |
| 过桥 | 否 | — | |
| 编排 | 否 | — | |
| 架构 | 验收 | 本 brief | |

## 6. 验收清单（架构照单勾）

- [ ] Markdown：`**bold**` 视觉为 semibold；`## 标题` 视觉重于正文；`` `code` `` 有底色。
- [ ] 工具调用绿勾：连续 3+ 工具过程中**无**绿勾；turn 结束后才出现。
- [ ] 工具调用闪烁：追加 5 step，rail 不闪不跳。
- [ ] 工具过程摘要：rail 顶部显示当前调用一句；展开见每步简介 + 结果。
- [ ] 进度轨：多步调用时可见分段进度（done/running/error/未达）。
- [ ] 新对话首条：user 气泡在中上区；回复开始后正常钉底。
- [ ] 对话切换：A→B（B 20 条）无漂移，直接显示末条附近。
- [ ] 命令：`bash scripts/ccc-self-check.sh`（期望：全通过）
- [ ] 命令：`cd desktop && swift build`（期望：编译通过；若本机无 swift 工具链，跳过并备注）
- [ ] 白名单外无改动
- [ ] 边界基线未破（对话/编排分离；不对 orch 投 backlog）

## 7. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 壳 | | | |
| 过桥 | | | |
| 编排 | | | |

## 8. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | 通过 / 打回 |
| 缺口 | |
| 验收日 | |
