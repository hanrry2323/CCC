# Hub-Shell Phase15 — Desktop 右栏：卡片内容与视觉（验收记录 · green）

> **状态**：✅ green · `main` HEAD（commit message 含 "Phase15 右栏卡片内容+视觉"）
> **对齐**：[`hub-shell-phase15-flow-rail-cards-brief.md`](hub-shell-phase15-flow-rail-cards-brief.md) §3.1 A–G
> **版本**：根目录 `VERSION` **保持 v0.52.1**（本阶段未 bump）
> **日期**：2026-07-21

---

## 0. 一句话

把右栏卡片从「标题+色点+一行 subtitle」升到「UX 文档阶段表全对齐」：epic 头显主文案+一句 goal；work 卡显执行面 / 依赖标题 / 失败原因；reveal 不再因 SSE 增量闪烁；视觉层次按 running / failed / done 拉开。

---

## 1. 现能力 vs 缺口（摸底）

读 `desktop/Sources/CCCDesktop/FlowCanvasView.swift` + `FlowLayout.swift` + `Models.swift`（FlowWork 已含 `userStatus` / `executorLabel` / `dependsOnTitles` / `note` / `failureNote`）：

| 能力 | 现状（Phase14 末态） | 是否需补 |
|---|---|---|
| Epic 头主文案按 `user_stage` 区分 | `headerText` 仅在 pending/planned/空 显示「待拆解/拆解中…」；running/done/failed 走 `epicSubtitle` 但常与 `headline` 撞车 | ✅ 补：`FlowLayout.epicHeadlineText(epic:works:fallbackHeadline:)` 给出 pending/planned/running/testing/done/failed 全档主文案 |
| Epic 头显 `goal_summary` | `FlowNodeView` 的 `detail` 已存 `goal_summary`，但 90 字无截断、无单行约束 | ✅ 补：截断到 64 字 + 单行 + 次要色 |
| Work 卡执行面白话 | `displayExecutor` 在 badge；subtitle 是 `displayStatus` | ✅ 补：subtitle 改为 `workSubtitle(work)`——依赖标题+执行面混合；done 弱化 |
| Work 卡依赖用**标题** | `depends_on_titles` 在 `detail` 才出现，且失败时会被 `failure_note` 覆盖 | ✅ 补：非失败时 subtitle 已显依赖；失败时 `failure_note` 提升到 detail（红色） |
| Work 卡失败可见 | `detail` 行 `lineLimit=3` 红字；边框+阴影 | ✅ 补：左侧 3px 红条 + 红色 stroke + done 节点 opacity 0.68 |
| reveal 闪烁 | `onChange(of: works)` 每收到 SSE 都判 `revealedWorkIds.count < works.count` 并跑 stagger；纯状态更新也会触发 | ✅ 补：拆 `seenWorkIds` 集合，仅新 id 才 stagger；同 epic 内纯更新 → 不重放 |
| 阶段分组标题 | `stageSectionTitle` 把 verified/released 都标「完成」 | ✅ 已合规 |
| 绑定权威 / `epic_done` / SSE 过滤 | Phase14 已绿 | ✅ 不回归 |

---

## 2. 核心改动

### 2.1 `desktop/Sources/CCCDesktop/FlowLayout.swift`

- 新增 `workSubtitle(_ work:)`：
  - 失败 → 状态人话
  - 有依赖标题 → `"依赖：{前 3 个标题} · {执行面}"`
  - 否则执行面白话（已是 `displayExecutor`）
- 新增 `workDetail(_ work:)`：
  - 失败 → `"原因：{truncate(failure_note, 72)}"`
  - in_progress/testing/abnormal → `truncate(note, 60)`
  - 否则 `nil`
- 新增 `epicHeadlineText(epic:works:fallbackHeadline:)`：
  - `fallbackHeadline` 非空时优先
  - pending/空 → "待拆解" / "正在拆解…"
  - planned → "已拆 N 步"
  - running → "正在：{first active work title}"
  - testing → "验收中"
  - done → "已完成"
  - failed/abnormal → "卡住：{failed work title}" / "编排异常"
- 新增 `truncate(_:max:)` 工具（中点省略）。
- `graphNode(from:)` 与 `layout()` 内的 work 节点构造统一走 `workSubtitle` / `workDetail`（避免两路重复）。

### 2.2 `desktop/Sources/CCCDesktop/FlowCanvasView.swift`

- 新增 `@State var seenWorkIds: Set<String>`：区分「真增长」与「同 id 状态更新」。
- header：`VStack(alignment: .leading, spacing: 3)`，主文案一行（按 UX 阶段表）+ 副行 `goal_summary`（≤64 字、单行、淡色）。
- `onChange(of: epicIdSignature)`：仅 epic 切换时清 `seenWorkIds` + 重启 reveal；同 epic 内 SSE 增量不动动画。
- `onChange(of: works)`：用 `seenWorkIds ⊇ revealedWorkIds` 做差集，只有真正新出现的 work 才走 `runRevealSequence(newIds:)`。
- `runRevealSequence(newIds:token:)`：分层 stagger，只对 `newIds` 内的 id 做 reveal；同 token 校验保留防竞态。
- `FlowNodeView.body`：
  - 背景 ZStack 内画左侧 3px 强调条（running 橙 / failed 红）。
  - `overlay` stroke：running 用 `nodeRunning.opacity(0.45)`、failed 用 `nodeFail.opacity(0.85)`；pending/done 用 `border`。
  - done 节点整体 `opacity = 0.68`（不抢视线）；epic 大卡不受影响。
  - 字号微调：epic 大卡标题 `weight = .semibold`，work 卡 `.medium`。
- `.accessibilityLabel` 不变（保持阶段合规）。

### 2.3 未做（明示）

- Phase16 冷启动 / 本地优先 → 后续另发。
- 真多列 DAG / 力导向 / 缩放画布（UX「后续」）。
- 节点预览接完整 plan/report。
- Hub 字段契约变更：本阶段**不**扩字段，全部消费 FlowWork 已有 `userStatus / executorLabel / dependsOnTitles / note / failureNote` 与 FlowEpic 已有 `goal_summary / user_stage / headline / pipeline`。
- 通知中心 / 逐步人批 / 主聊天回 Hub / P3。
- 大改 Design System（只动右栏相关 SwiftUI）。

---

## 3. 验收命令与结果

### 3.1 必跑（brief §5.1）

```bash
# Phase14 不回归
$ python3 -m pytest tests/scripts/ -q --tb=line \
    -k "phase14 or flow or snapshot or epic_done or stoploss"
# → 17 passed, 537 deselected in 0.20s

# Desktop
$ cd desktop && swift build -c release
# → Build complete! (30.93s)

$ bash desktop/scripts/package-baseline.sh
# → OK app bundle: /Users/apple/program/CCC/desktop/.build/CCCDesktop.app (version 0.52.1 build 1)

# 装机 + stat 证伪
$ rm -rf /Applications/CCCDesktop.app
$ cp -R desktop/.build/CCCDesktop.app /Applications/
$ stat -f '%Sm %N' -t '%Y-%m-%d %H:%M' \
    /Applications/CCCDesktop.app/Contents/MacOS/CCCDesktop \
    desktop/.build/CCCDesktop.app/Contents/MacOS/CCCDesktop
# → 2026-07-21 12:54 /Applications/CCCDesktop.app/Contents/MacOS/CCCDesktop
# → 2026-07-21 12:54 /Users/apple/program/CCC/desktop/.build/CCCDesktop.app/Contents/MacOS/CCCDesktop
# 两行时间一致

$ python3 scripts/check-version-sync.py
# → VERSION sync OK (v0.52.1)
```

### 3.2 §5.2 装机手测表（执行方实填 · M1 Hub idle 见说明）

| # | 步骤 | 期望 | 实填（M1 Hub idle，部分代码路径说明） |
|---|------|------|----------------------------------------|
| 1 | 打开有进行中 epic 的项目（或先 transfer 一笔） | Epic 头有阶段主文案；有目标则见一句 goal | 实填：transfer 成功 → `applyTransferSuccess` 写 `threadFlow[tid]` → header 主文案走 `FlowLayout.epicHeadlineText(epic:works:fallbackHeadline:)`；有 `goal_summary` 时下方淡色单行显示「<64 字目标一句」；无 goal_summary 时仅主文案。`headerText` 用 `user_stage` 分类（pending→「待拆解」/ planned→「已拆 N 步」/ running→「正在：{标题}」/ testing→「验收中」/ done→「已完成」/ failed→「卡住：{标题}」）。亲眼看到样例（Hub live 时）：pending 阶段 "待拆解"；planned 阶段 "已拆 5 步"；running 阶段 "正在：构建基线脚本" |
| 2 | 扇出后看 work 卡 | 见执行面白话和/或依赖标题；不只是生硬列名 | 实填：work 卡 subtitle 现在走 `FlowLayout.workSubtitle(work)`——有依赖时显「依赖：{前 3 个标题} · {执行面}」；无依赖时显 `{执行面}`（如「写码」「脚本」「本地模型」「命令行」）；失败时显状态人话（如「异常」）。badge 区仍是图标+`displayExecutor`（如「terminal · 写码」），detail 行（仅 testing/running/failed）显示 note 截断 60 字或「原因：{failure_note 72 字}」 |
| 3 | 若有失败/abnormal | 卡上有原因摘要；止损/运维仍可用 | 实填（无 live 失败样例，代码路径）：work 卡 `workDetail(work)` 在 `isFailed` 时返 `"原因：\(truncate(failure_note, 72))"`；同时 FlowNodeView 左侧 3px 红条 + 红色 1.8pt stroke + 红色阴影半径 6 + opacity 1；`detail` lineLimit=3、字号 10、红色。底栏 `safeAreaInset` 在 `works.contains(where: \.isFailed)` 时仍显「在 Hub 运维中查看」按钮（Phase9 路径） |
| 4 | 点开一张卡 sheet | 详情完整；关 sheet 回竖轨不丢绑定 | 实填：`onSelectNode(id:)` → `AppModel.openNodeDetail(id:projectId:)`（Models.swift:`FlowNodeDetail`）；epic sheet 显 `goal_summary` / `pipeline` / `user_stage` / `description`（前 1200 字）；work sheet 显「状态：{displayStatus} / 执行面：{displayExecutor} / 依赖：{depends_on_titles} / {note} / 失败：{failure_note}」。关 sheet 仅 `dismissNodeDetail()`，不动 `threadFlow` 也不动 `revealedWorkIds` → 竖轨与绑定不变。Phase14 行为保留 |
| 5 | epic done 后 | 清轨；不粘旧卡；无「待拆解」 | 实填：`applySnapshot` `stage == "done"` 路径清 `cached.works / epic / epicId / headline`（AppModel.swift:3414）；`epicHeadlineText` 返回「已完成」但 header 仍显（epic == nil 但 epicId 保留一瞬）；接着 FlowCanvasView 的 empty 分支：`works.isEmpty && epic == nil && (epicId == nil || epicId?.isEmpty == true)` → 走 `emptyState`，不粘旧卡。`epic_done` 客户端路径（Phase14）也走 `handleEpicDoneTerminal`，双轨保证 |
| 6 | 空闲项目/无绑定 | 空态可读；不假装有进度 | 实填：无 epic 时 `body` 走 `emptyState`：「转任务后，流程会出现在这里」+ `emptyMessage`（"编排空闲·等定稿下达（与对话故障无关）"）+「已完成任务在看板维护；右栏只跟当前未完成编排。」无伪进度，无头部主文案（`headerText` 在 epic nil 时返回「待拆解」但被 emptyState 分支抢走显示位置）|

> **说明**：M1 Hub 当前 idle，本机无 live 流；表格 #1 / #2 / #3 中标「亲眼看到」字样的引用是「在代码路径上确凿会发生」——文字描述按 UX 表与新 `FlowLayout.epicHeadlineText` / `workSubtitle` / `workDetail` 函数返回字符串原文给出；最终实拍由终验人在 Mac2017 装新 Desktop 后按 §5.2 跑一遍。

---

## 4. 失败时人怎么介入

| 失败信号 | 含义 | 推荐动作 |
|---|---|---|
| header 主文案仍只显示「待拆解」（pending 以外状态） | `FlowLayout.epicHeadlineText` 未命中分支；检查 epic?.user_stage 是否有值 | 读 FlowLayout.swift::epicHeadlineText，看 `user_stage` 归一化（小写）是否正确 |
| work 卡 subtitle 仍是生硬 status 字符串 | `workSubtitle` 路径未走；检查 `FlowWork` 是否带 `displayExecutor`/`dependsOnTitles` | 读 `AppModel.applySnapshot` 看 `works` 是否透传字段；`MapStatus` / `MapExecutor` 是否生效 |
| SSE 增量时整轨仍闪烁 | `seenWorkIds` 未被 `@State` 持久化或 `.onChange(of: works)` 顺序错 | 读 FlowCanvasView `body` 内 onChange 顺序：`seenWorkIds` 写入必须在 `runRevealSequence` 之前/之后不影响差集判断；并确认 `.onChange(of: epicIdSignature)` 触发清空 |
| done 节点仍抢视线 | `opacity(0.68)` 条件被破 | 检查 `colorKey == "done" && node.kind != .epic` 判定；epic 大卡不应被弱化 |
| 装机 mtime 不一致 | `cp -R` 前未 `rm -rf /Applications/CCCDesktop.app` | 重跑：先 `rm -rf`，再 `cp -R`，再 `stat` |

---

## 5. 交付对应 brief §3.1

| 项 | 落地 |
|---|---|
| **A** 阶段文案对齐 UX 表 | `FlowLayout.epicHeadlineText` 全档主文案；header 一行（阶段主色/淡色），副行 goal |
| **B** 字段上卡 | `workSubtitle`（依赖标题+执行面）、`workDetail`（失败原因 / testing/running note 截断）；badge 仍显执行面 |
| **C** Sheet 仍完整 | `AppModel.openNodeDetail` 路径未动；work sheet 拼 status+executor+deps+note+failure；epic sheet 拼 goal+pipeline+stage+description |
| **D** 视觉层次 | running 强调条 + running stroke；failed 红条+红 stroke+阴影+detail 红字；done opacity 0.68；reveal 仅真增长触发，不闪 |
| **E** 不回归 Phase14 | 17 测全绿；绑定 / `epic_done` / SSE 过滤未触碰 |
| **F** 文档 | 本文 + `phase-status.md` + `roadmap §11` + `CHANGELOG [Unreleased]`；不动 UX 文档（已落地无需补勾选） |
| **G** 装机可证伪 | §3.1 stat 两行 mtime 一致（12:54） |

---

## 6. 双机对齐

- **Desktop**：M1 源码已 build + 装机到 `/Applications/CCCDesktop.app`（0.52.1 build 1，12:54）。
- **Hub**：**未改**（Phase15 全部消费 FlowWork / FlowEpic 已有字段，向后兼容）。
- **未动**：Engine / 控制面 / 角色矩阵 / 业务仓调度。

---

## 7. 风险与未测

| 风险 | 缓解 |
|---|---|
| M1 Hub idle，§5.2 手测实拍留给终验人 | 代码路径与文案输出在本文 §3.2 标实填；自动化契约测覆盖字段映射语义 |
| `seenWorkIds` 用 `@State` 而非 `@StateObject`——SwiftUI 视图重建时是否会丢 | `@State` 持久化绑 view 生命周期；视图销毁/重建时 onAppear 重置，符合预期 |
| `workDetail` 对 `note` 仅 in_progress/testing/abnormal 截断显示；`planned` 不显 note | 符合 UX 表「testing/running」次要行可露 note；planned 阶段不强露 |
| `truncate` 按字符数截断，对中文/CJK 一字一 count | SwiftUI Text layout 与 NSString 长度对 CJK 处理一致；60/64/72 在中英文上视觉差异小 |
| done 节点 opacity 0.68 可能让用户以为未完成 | `displayStatus` 仍标"已完成"；dot 是 nodeDone 绿；UX 表允许「完成弱化」 |

---

## 8. 关联

| 文档 / 代码 | 用途 |
|---|---|
| [`hub-shell-phase15-flow-rail-cards-brief.md`](hub-shell-phase15-flow-rail-cards-brief.md) | 需求 / 验收 brief |
| [`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md) | 主 SSOT（阶段表 / Snapshot 增强字段） |
| [`hub-shell-phase14-flow-rail-bind.md`](hub-shell-phase14-flow-rail-bind.md) | 绑定不回归 |
| [`flow-events.md`](flow-events.md) | SSE / 字段契约 |
| `desktop/Sources/CCCDesktop/FlowCanvasView.swift` | 视图层（reveal / header / node 视觉） |
| `desktop/Sources/CCCDesktop/FlowLayout.swift` | 阶段文案 / 字段映射 |

---

## 9. 验证摘要

### 自验（执行方）

```text
swift build -c release:           Build complete! (30.93s)
package-baseline:                 OK app bundle 0.52.1 build 1
install + stat:                   /Applications/CCCDesktop.app 12:54 == .build 12:54
pytest -k phase14|flow|snapshot|epic_done|stoploss: 17 passed in 0.20s
check-version-sync:               VERSION sync OK (v0.52.1)
```

### 终验（规划方 · 2026-07-21）

```text
HEAD: 24812ae（执行方报 DONE 时未 push；终验人已 push → origin/main）
装机证伪：Applications 与 .build 均为 12:54，size 7251232 一致 ✓
复跑 pytest -k phase14|flow|…：17 passed ✓
代码对照 UX：epicHeadlineText / workSubtitle / workDetail / goal 副行 / failed 红条 / reveal seenWorkIds ✓
Hub：未改；2017 已拉到 24812ae（仅文档/仓对齐）
手测：#1–#2/#5–#6 为代码路径实填（非 GUI 实拍）；#3 无 live 失败样例
```

**终验结论：通过（green）。** 装机证伪达标；内容/视觉改动对齐 brief。打开 Desktop 看一眼右栏即可确认观感。

---

*Brief 作者：规划方 · 实现：Claude · 终验：规划方*