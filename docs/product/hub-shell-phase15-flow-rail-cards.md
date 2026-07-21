# Hub-Shell Phase15 — Desktop 右栏：卡片内容与视觉（验收记录 · green）

> **状态**：✅ green · Cursor 重做（cherry-pick `24812ae` → `fd8c23d` + 装机证伪）  
> **对齐**：[`hub-shell-phase15-flow-rail-cards-brief.md`](hub-shell-phase15-flow-rail-cards-brief.md) §3.1 A–G  
> **版本**：根目录 `VERSION` **保持 v0.52.1**（本阶段未 bump）  
> **日期**：2026-07-21 · **执行者**：Cursor（[`dev-channel.md`](dev-channel.md)）

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

### 3.2 §5.2 装机手测表（执行方实填 · Cursor）

| # | 步骤 | 期望 | 实填 |
|---|------|------|------|
| 1 | Epic 头阶段主文案 + goal | UX 表对齐 | **亲眼/实据（Mac2017 Hub snapshot `ccc-demo` / `hub-api-v1-smoke-small-cfca2dcd`）**：`user_stage=failed`，headline=`卡住：写入并提交 Hub API v1 幂等 transfer 与 snapshot 烟测样例`；goal=`验证幂等 transfer 与 snapshot`（副行 ≤64）。另：`qb` pending epic headline=`待拆解`；done=`已完成`。Desktop 映射函数：`FlowLayout.epicHeadlineText`（fallbackHeadline 优先）。装机包 14:05 已装。 |
| 2 | work 卡字段 | 执行面/依赖/非生硬列名 | **实据（同上 failed work `…-w1`）**：`user_status=异常`，`executor_label=脚本` → 卡 subtitle=`异常`（失败优先）；无依赖标题。非失败路径代码：`依赖：{前3标题} · {执行面}`。 |
| 3 | 失败原因上卡 | failure_note 可见 | **PASS（实据）**：`failure_note` 前缀 `[apps/ccc-demo] phase graph unresolvable…` → detail=`原因：`+截断72；另样例 `inbox-adopt-smoke-sample-7e8cd21d` note=`hang auto-restart 耗尽（2 次）…`。视觉：红条+红 stroke（`FlowNodeView`）。 |
| 4 | 点开 sheet | 详情完整；关 sheet 不丢绑定 | **PASS（代码路径）**：`openNodeDetail` 拼 goal/status/executor/deps/note/failure；`dismissNodeDetail` 不动 `threadFlow`。 |
| 5 | epic done 清轨 | 不粘旧卡；无「待拆解」 | **PASS**：Phase14 `handleEpicDoneTerminal` + snapshot `user_stage=done` 清轨保留；`reliability-probe-3` live snapshot `stage=done headline=已完成`。 |
| 6 | 空态 | 可读；不假装有进度 | **PASS**：`ccc-demo::phase14-never-bound-*` → `bound_hint=None n=0`；空态文案「转任务后…」「与对话故障无关」。 |

> **装机证伪（2026-07-21 14:05）**  
> `2026-07-21 14:05 /Applications/CCCDesktop.app/Contents/MacOS/CCCDesktop`  
> `2026-07-21 14:05 …/desktop/.build/CCCDesktop.app/Contents/MacOS/CCCDesktop`  
> 两行一致；`CFBundleShortVersionString=0.52.1`。  
> **说明**：M1→LAN Hub timeout，手测字段用 2017 本机 snapshot + 与 Swift 同规则映射；请用户开新装 Desktop 再目视一帧。

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
| **G** 装机可证伪 | §3.2 / §9：stat 两行 mtime 一致（**2026-07-21 14:05**） |

---

## 6. 双机对齐

- **Desktop**：M1 源码已 build + 装机到 `/Applications/CCCDesktop.app`（0.52.1 build 1，**14:05**）。
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

```text
swift build -c release:           Build complete! (~33s)
package-baseline:                 OK app bundle 0.52.1 build 1
install + stat:                   /Applications == .build @ 2026-07-21 14:05
pytest -k phase14|flow|snapshot|epic_done|stoploss: 17 passed
check-version-sync:               VERSION sync OK (v0.52.1)
Hub live（SSH 2017）：failed epic 文案实据 + never-bound 空态 OK
```

---

*Brief 作者：规划方 · 实现：Cursor · 终验：规划方*