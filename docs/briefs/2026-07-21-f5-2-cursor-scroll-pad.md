# F5-2 · Cursor 式中栏滚动留白（发消息上推 + 下方空槽）

## 元信息

| 字段 | 填写 |
|------|------|
| brief_id | `F5-2-20260721-cursor-scroll-pad` |
| 波次 | F5（流畅基线后 UX 打磨） |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |

## 1. 目标

对齐 Cursor 聊天区节奏：用户发送后，**最新用户气泡上推到中栏上部**，下方留出大块空白给流式回复；任意会话（含左右切换）底部都有稳定空槽，新内容有空间继续显示。

## 2. 非目标

- 不改工具轨 / Markdown / 绿勾（F5-1 已合）。
- 不改 sidecar / Hub / 消息持久化。
- 不引入第三方滚动库。
- 不改右栏 Flow。

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| transfer-gate | 无 | |
| flow-events | 无 | |
| hub-api-v1 | 无 | |
| 其它 docs | 无 | 纯 UI |

## 4. 根因（架构已定位）

用户反馈：「发送后对话上划、流空白；左右会话都应在中间栏下方留一部分空白」。

当前实现（`ContentView.swift` `CodexChatPaneBody`）：

1. **滚动目标错了**：`scroll()` 一律 `proxy.scrollTo(bottomAnchorId, anchor: .bottom)`。`bottomAnchorId` 在底部大 Spacer **之上**；再 `anchor: .bottom` 等于把整块空 Spacer 钉进视口 → 用户气泡被顶出视口上沿，中间只剩空白（「流空白」体感）。
2. **不是 Cursor 模型**：Cursor 是「最新 **user** 消息 `scrollTo(..., anchor: .top)`」，下方空槽留给 assistant 流式写入；不是「钉 tip 底」。
3. **F5-1 首条顶部 Spacer 是半吊子**：只在 `count==1 && user && !streaming` 插顶部 Spacer；一进 streaming 就撤，且与「一律钉 tip」冲突 → 发送瞬间仍上划空白。
4. **底部留白偏小且语义混**：`max(h*0.35, 120)` 不够 Cursor 感；且 tip 钉底把留白吃进视口当「空屏」，而不是「最新内容偏上 + 下方空」。

## 5. 目标行为（对齐 Cursor）

| 场景 | 期望 |
|------|------|
| 用户刚发送（本轮最新是 user，或 assistant 刚建仍空） | **滚动到该 user 气泡，`anchor: .top`**（略偏上即可）；视口下半大块空白，等回复写入 |
| assistant 流式增长 | 内容未撑满空槽前：**保持 user 在上、不反复钉 tip**；内容逼近/超过空槽下沿时，再跟滚（节流），避免跳动 |
| turn 结束 / 长历史会话 | 最新内容在中上～中部，**底部仍可见稳定空槽**（不贴死输入条） |
| 左右切换会话 | 直接显示「末轮」附近；末条偏上 + 底部空槽；**禁止**顶→底漂移扫历史（延续 F5-1 G） |
| 空会话引导 | 保持现状，不强制上推 |

## 6. 修复方案（壳窗照做）

文件：`desktop/Sources/CCCDesktop/ContentView.swift`（仅 `CodexChatPaneBody` 的 `messageArea` / `scroll` / 相关 `@State`）。

### 6.1 底部空槽加大（常驻）

- 将底部 Spacer 改为 **`max(geometry.size.height * 0.55, 220)`**（常量可抽 `private var bottomPadHeight`）。
- **删除** F5-1 的「首条顶部 Spacer」条件块（`count==1 && user && !streaming`）——改由滚动策略实现，避免与 streaming 互撕。

### 6.2 滚动策略重写 `scroll(_ proxy:)`

引入清晰模式（可用私有枚举或布尔，勿过度设计）：

1. **`needsInstantBottomPin`（切会话/重入）**  
   - 无动画：`scrollTo(lastMessageId, anchor: .top)`（优先末条消息 id，**不要**再 `scrollTo(tip, .bottom)`）。  
   - 这样末条在视口顶部附近，下方空槽自然露出；无漂移。

2. **用户刚发送 / 等待首包**（`displayMessages.last?.role == "user"`，或 last 是 streaming 且 `content.isEmpty && toolSteps.isEmpty`）  
   - 找到本轮 user 消息 id（通常是 `last` 的前一条，或 last 本身若是 user）。  
   - `scrollTo(userId, anchor: .top)`；流式阶段同目标可跳过重复 scroll（防闪）。

3. **assistant 流式且内容已较长**  
   - 仅当内容高度可能超出空槽时跟滚：可继续用 tip，但改用 **`scrollTo(lastAssistantId, anchor: .bottom)`**（跟消息底，不跟 tip 的 `.bottom`），或 `scrollTo(tipId, anchor: .top)` 把 tip 贴在视口顶以下——**禁止** `scrollTo(tipId, anchor: .bottom)`（这是本次根因）。  
   - 节流保留（约每 120 字或 toolStep 变化）。

4. **非流式新消息（如历史加载完成）**  
   - 同切会话：`scrollTo(lastId, anchor: .top)`，无动画。

### 6.3 触发点

- 保持现有 `onChange`（count / content / toolSteps / threadRevision / bottomPinTick）。
- 用户发送后 count 变化应立刻走模式 2（user 上推），不要先钉 tip。

### 6.4 自检

- `bash scripts/ccc-self-check.sh`
- `cd desktop && swift build -c release`（**必须 release**，避免再测到旧二进制）
- 构建后杀旧进程再起：`pkill -f 'CCCDesktop' ; desktop/.build/release/CCCDesktop &`（或等价）

## 7. 分工白名单

| 面 | 是否参与 | 允许改动的路径 | 禁止 |
|----|----------|----------------|------|
| 壳 | 是 | `desktop/Sources/CCCDesktop/ContentView.swift`（仅滚动/留白相关） | 改 AppModel 流事件、ToolProgressRail、MarkdownText、scripts/ |
| 过桥 | 否 | — | |
| 编排 | 否 | — | |
| 架构 | 验收 | 本 brief · PASTE-OPS | |

## 8. 验收清单（架构照单勾）

- [ ] 发一条新消息：user 气泡停在中栏**上部**，下方大块空白（非整屏空、非气泡贴输入条）。
- [ ] 流式回复写入时：先填下方空槽；内容变长后平滑跟滚，**无**「上划后只剩空白」的错误态。
- [ ] 切换到另一长会话：直接末轮偏上 + 底部空槽；无顶→底漂移。
- [ ] 底部空槽高度约视口 55%（目测即可）。
- [ ] 已删除 F5-1 首条顶部 Spacer 条件块。
- [ ] 代码中**不存在** `scrollTo(tipId, anchor: .bottom)`（或等价 tip + `.bottom`）。
- [ ] `swift build -c release` 绿；release 二进制时间戳晚于本 commit。
- [ ] 白名单外无改动。

## 9. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 壳 | 底部空槽 `max(h*0.55,220)`；删 F5-1 首条顶部 Spacer；`scroll()` 改为切会话/末条 `.top`、等首包钉 user `.top`、流式跟 assistant `.bottom`；禁止 tip+`.bottom` | `ccc-self-check` 全通过；`swift build -c release` 绿；已 `pkill` 后起 release 二进制 | ✅ |
| 过桥 | — | — | 不参与 |
| 编排 | — | — | 不参与 |

## 10. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | 通过 |
| 缺口 | 无。`bottomAnchorId` 仍保留作布局锚点，但已无 `scrollTo(tip, .bottom)`；流式跟滚用 `lastId` + `.bottom`，符合 brief |
| 验收日 | 2026-07-21 |

验收照单勾：
- [x] 底部空槽 `max(h*0.55, 220)`
- [x] 已删 F5-1 首条顶部 Spacer
- [x] 切会话/重入：`scrollTo(lastId, .top)`
- [x] 刚发送/等首包：`scrollTo(userId, .top)`（`shouldPinCurrentUserToTop`）
- [x] 流式变长：跟 `lastId` `.bottom` + 节流桶；短内容仍钉 user
- [x] 代码无 `scrollTo(tipId, anchor: .bottom)`
- [x] 白名单：仅 `ContentView.swift` + brief
- [x] `ccc-self-check` 全通过；release 产物 mtime 20:50；已重启 pid 52395

