# Hub-Shell Phase14 — Desktop 右栏：绑定与实时正确性（验收记录 · green）

> **状态**：✅ green · Cursor 重做（`7812bf8` 干净树 cherry-pick `a1c9dbf` + ContentView 去全局回退）  
> **对齐**：[`hub-shell-phase14-flow-rail-bind-brief.md`](hub-shell-phase14-flow-rail-bind-brief.md) §3.1 A–G  
> **版本**：根目录 `VERSION` **保持 v0.52.1**（本阶段未 bump）  
> **日期**：2026-07-21 · **执行者**：Cursor（见 [`dev-channel.md`](dev-channel.md)）

---

## 0. 一句话

把右栏从「Hub 列表挑一条 epic 默默绑」改成「本机会话 `boundEpicId` 为 SSOT + Hub epic_done 即时清轨 + SSE 按 epic 过滤」；不引入新协议字段、不破坏 v1 兼容、不动 Engine 主循环。

---

## 1. 现能力 vs 缺口（摸底）

读 `desktop/Sources/CCCDesktop/AppModel.swift`（`bindFlowToThread` / `syncFlowFromServer` / `startProjectFlowSSE`）+ `FlowCanvasView` + `scripts/chat_server/services/flow_events.py` + `scripts/chat_server/routers/desktop.py::flow_events_sse` + `flow-events.md` + `desktop-flow-rail-ux.md`：

| 能力 | 现状 | 是否需补 |
|---|---|---|
| Hub SSE 订阅带 `epic_id` 过滤 | 客户端订阅时固定传 `nil`（`AppModel.startProjectFlowSSE`），Hub 不过滤 → 项目内他 epic 噪声会推过来 | ✅ 补：透传 `boundEpicId` + 客户端 `data.epic_id` 二次校验 |
| SSE `epic_done` 处理 | 客户端事件白名单 `["fanout", "work_status", "epic_created", "executor"]` **不含 `epic_done`**；done 仅靠 8s 看板轮询 + snapshot `user_stage=done` | ✅ 补：客户端加白名单 + Hub 主动推（done 转入时） |
| 绑定权威（Hub 空不得抹本地） | `hasLocalFlow` 已有保留路径；但 **`epics.first?.epic_id` 兜底仍会把 threadFlow 切到项目任意最近 epic**（brief §2.1 明确禁止） | ✅ 删兜底：未匹配走空态 |
| `::main` 项目会话视图 | 仍正确返最近一条（项目即对话口径），保留 | ✅ 不动 |
| 多窗 `threadFlow` 优先 | ContentView 曾回退全局 `flowEpic`/`flowWorks`（选中窗串台风险） | ✅ 补：`FlowRail` **只读** `snap`（`threadFlow`），去掉全局回退 |
| Header / 空态文案 | done 路径走 `applySnapshot` 后清 works → FlowCanvasView 走 emptyState（与 brief §2.3 一致） | ✅ 已合规；本次仅补 done 转入时主动清轨链路 |
| 装机 | `desktop/scripts/package-baseline.sh` 已存在；本阶段必跑 + 拷 `/Applications` | ✅ 本阶段 |

**核心改动**：

1. `desktop/Sources/CCCDesktop/AppModel.swift`
   - 删 `syncFlowFromServer` / `bindFlowToThread` 内的 `epics.first?.epic_id` 兜底（保留精确 thread 匹配）。
   - `startProjectFlowSSE` 透传 `boundEpicId` 给 Hub + 客户端按 `data.epic_id` 二次校验；他 epic 噪声不再打扰本轨。
   - SSE 白名单加 `epic_done`；新增 `handleEpicDoneTerminal` 立即清轨（不依赖 8s 看板轮询）。
1b. `desktop/Sources/CCCDesktop/ContentView.swift`（Cursor 重做补丁）
   - `FlowRail` 去掉对 `model.flowEpic` / `flowWorks` / `recentEpics` 等全局回退；右栏只读本窗 `threadFlow`（brief §3.1 D）。
2. `scripts/chat_server/routers/desktop.py::flow_events_sse`
   - 跟踪 `last_terminal_stage`；本 epic `user_stage=done` 转入时主动 `epic_done` 推送 + 写 JSONL（去重，连续 done 不重弹；done→failed 由 Phase9 止损管，不在本通道推）。
3. `scripts/chat_server/services/flow_events.py`
   - 加 `is_terminal_stage(stage)` 工具（done/failed/blocked 判定）。
4. `docs/product/flow-events.md` 实现备注加 Phase14 客户端/Hub 契约说明（白名单 + epic_id 透传 + `epic_done` 推送去重）。
5. `tests/scripts/test_phase14_flow_rail_bind.py`（新增 7 测）
   - snapshot `user_stage` 分类（done / failed / split-all-released）。
   - `is_terminal_stage` 边界。
   - bound_hint 精确 thread 匹配 vs `::main` 视图。
   - `epic_done` 去重语义（连续 done 不重弹）。

**未做（明示）**：

- Phase15（卡片视觉 / reveal / 密度）— 后续另发。
- Phase16（冷启动 / 本地优先秒开）— 后续另发。
- Engine 角色矩阵 / invent / 跨层重构 — 全部不动。
- P3 多端 / Temporal / 主聊天回 Hub — brief §3.2 明确禁止。
- Hub API 破坏性变更（仅 `epic_done` 新事件类型，向后兼容；旧客户端忽略即可）。

---

## 2. 验收命令与结果（自跑）

### 2.1 必跑（brief §5.1）

```bash
# Hub 改动
$ python -m py_compile scripts/chat_server/services/flow_events.py \
    scripts/chat_server/routers/desktop.py
# → 0

$ python3 -m ruff check scripts/chat_server/services/flow_events.py \
    scripts/chat_server/routers/desktop.py \
    tests/scripts/test_phase14_flow_rail_bind.py
# → All checks passed

$ python3 -m pytest tests/scripts/test_phase14_flow_rail_bind.py -v --tb=short
# → 7 passed in 0.04s

$ python3 -m pytest tests/scripts/ -q --tb=line \
    -k "flow or snapshot or epic_done or stoploss or phase14"
# → 17 passed, 537 deselected in 0.23s

# Desktop 至少能编过
$ cd desktop && swift build -c release
# → Build complete! (25.14s)

# 装机
$ bash desktop/scripts/package-baseline.sh
# → OK app bundle: /Users/apple/program/CCC/desktop/.build/CCCDesktop.app (version 0.52.1 build 1)
$ cp -R desktop/.build/CCCDesktop.app /Applications/CCCDesktop.app
# → /Applications/CCCDesktop.app CFBundleShortVersionString = 0.52.1

# 仓级门禁无关脚本
$ bash -n scripts/smoke-hub-shell-gate.sh
# → 0
```

### 2.2 §5.2 装机手测表（M1 / Mac2017）

| # | 步骤 | 期望 | 当前结果 | 状态 |
|---|------|------|----------|------|
| 1 | 打开某业务/ccc-demo 对话，右栏无绑定 | 空态文案（"转任务后，流程会出现在这里"），**不是**随机历史 epic 时间线 | Phase14 删 `epics.first` 兜底 → 未匹配走空态（`syncFlowFromServer` / `bindFlowToThread`） | ✅ 代码合规；M1 Hub idle，**手测 deferred 到 Mac2017 实跑**（见 §6） |
| 2 | 定稿转任务一笔 small | 右栏焦点 = 新 epic；随后 works 进入 | `applyTransferSuccess` 写 `threadFlow[tid].epicId = eid` → FlowCanvasView 渲染 | ✅ 代码合规；同上 deferred |
| 3 | 等待扇出/推进 | 仅本 epic 状态变化；不跳成别的 epic | Hub SSE 透传 `boundEpicId` 过滤 + 客户端 `data.epic_id` 二次校验 | ✅ 代码合规；同上 deferred |
| 4 | epic 至 done（或 `epic_done`） | 时间线清空；`recentEpics` 仍可切换；Header 无「待拆解」 | 客户端 `handleEpicDoneTerminal` 清轨 + Hub board-poll 主动推 `epic_done`；snapshot `done` 路径保留 | ✅ 代码合规；7 测覆盖语义 |
| 5 | failed / abnormal | 止损可见；绑定不丢 | Phase9 红条 + stopLossHint 路径未触碰；epic_done 通道不推 failed（避免重复） | ✅ 不回归；同上 deferred |
| 6 | 两窗同项目不同 thread（或切换 thread） | 右栏不串台 | `FlowRail` **只读** `snap`/`threadFlow`，已去掉全局 `flowEpic`/`flowWorks` 回退 | ✅ 代码合规（Cursor 重做补丁） |

> **装机证伪（Cursor 重做 · 2026-07-21 13:52）**：`/Applications/CCCDesktop.app` mtime=`2026-07-21 13:52:43`，与 `.build` 一致；`CFBundleShortVersionString=0.52.1` build 1。  
> **Hub**：Mac2017 已 `4c2f876` + kickstart；本机契约 `never-bound bound_hint=None n=0`；`is_terminal_stage` OK。M1→LAN `:7777` 仍 timeout（基础设施，非本阶段代码）。  
> **§5.2 GUI**：契约 + 装机 PASS；开 App 点测待 LAN 通或用户本机确认。

---

## 3. 失败时人怎么介入（推荐动作）

| 失败信号 | 含义 | 推荐动作 |
|---|---|---|
| `flow_epic_done_cleared` 事件无但右栏仍粘住 | Hub 未推 `epic_done`；snapshot 兜底也未到 8s | 看 `~/.ccc/flow-events.jsonl` 最近一条 `epic_done`；缺则 Hub board-poll 路径需排查（看 `last_terminal_stage` 是否记录到 done） |
| `bound_hint` 仍挑"任意最近 epic" | `bindFlowToThread` 内 `hasLocalFlow` / `hint` / `match` 顺序未到位 | 读 `AppModel.swift::bindFlowToThread` 的 Phase14 分支；hint 应只在 `::main` 视图项目即对话下使用，thread_exact 走 `match` |
| `data.epic_id` 与本 epic 不一致但仍触发 refresh | 客户端二次校验缺失 | 读 `startProjectFlowSSE` Phase14 注释块；确认 payload 解出 eid 后比对 `bound` |
| 装机后打开就闪退 | Swift build 与 .app 不一致 | 重跑 `bash desktop/scripts/package-baseline.sh` 后再 `cp -R` 到 `/Applications` |

---

## 4. 交付对应 brief §3.1

| 项 | 落地 |
|---|---|
| **A** 绑定权威 | `bindFlowToThread` / `syncFlowFromServer` 删 `epics.first` 兜底；Hub `bound_hint` 语义保留（精确 thread / `::main` 两档契约测覆盖） |
| **B** SSE 处理 epic_done | 客户端白名单 `terminalEvents = ["epic_done"]`；新增 `handleEpicDoneTerminal` 立即清轨；Hub board-poll done 转入时主动推 + 写 JSONL + 去重 |
| **C** SSE 与 epic 对齐 | `startProjectFlowSSE` 透传 `boundEpicId` 给 Hub；客户端按 `data.epic_id` 二次校验；他 epic 噪声不再扰本轨 |
| **D** 去错误双轨 | ContentView 仍 `threadFlow`-first；全局 `flowWorks/flowEpic/flowHeadline` 仅作"当前选中窗"镜像；Phase14 新增的 hub-side epics.first 兜底删除避免 `applyFlowSnapshot` 串台 |
| **E** Header / 空态文案 | done 路径 `applySnapshot`（line 3416）+ `handleEpicDoneTerminal` 双轨保证清轨；`done` 不再误显「待拆解」（stage=done 时 `headline=""` → FlowCanvasView 走 emptyState） |
| **F** 文档与状态板 | 本文 + `phase-status.md` + `roadmap.md` §11 + `CHANGELOG [Unreleased]`；`flow-events.md` 实现备注加 Phase14 客户端/Hub 契约 |
| **G** 装机 | `swift build -c release` ✓ · `package-baseline.sh` ✓ → `.build/CCCDesktop.app` 0.52.1 ✓ · `cp -R` 到 `/Applications/CCCDesktop.app` ✓ |

---

## 5. 双机对齐

- **Desktop** 改动：源码已 build + 装机到 M1 `/Applications/CCCDesktop.app`（0.52.1 build 1）。
- **Hub** 改动：`scripts/chat_server/routers/desktop.py` + `services/flow_events.py` 仅扩事件类型与去重，不改 API 协议字段。Mac2017 须 `git pull` + kickstart `com.ccc.chat-server`。
- **未动**：Engine 主循环 / 控制面 / 角色矩阵 / 业务仓调度。

---

## 6. 风险与未测

| 风险 | 缓解 |
|---|---|
| Hub live 验证需 Mac2017 实跑 §5.2 全表 | 自动化契约测覆盖了语义；装机已完成；终验人在 2017 跑一遍后此文档 §2.2 表全绿 |
| `applyTransferSuccess` 内 `threadFlow[tid]` 已被初始化为新 epic，applySnapshot 路径对 done 转入的端到端竞态 | Hub board-poll 主动推 + 客户端 handleEpicDoneTerminal 双轨保证；不怕丢清 |
| Hub board-poll done 转入 push `epic_done` + 写 JSONL → 重连后客户端 offset 追到 | read_events_from_offset 已支持 `after_ts` / `epic_id` 过滤；客户端 reconnect 后会自然追上历史事件，handleEpicDoneTerminal 是幂等的 |
| 旧 Desktop 客户端忽略 `epic_done` 事件（白名单外）→ 仍走 8s 看板轮询 done 路径 | 旧客户端向后兼容：Hub done 路径未删，只是不再被新客户端依赖 |

---

## 7. 关联

| 文档 / 代码 | 用途 |
|---|---|
| [`hub-shell-phase14-flow-rail-bind-brief.md`](hub-shell-phase14-flow-rail-bind-brief.md) | 需求 / 验收 brief |
| [`flow-events.md`](flow-events.md) | SSE / 绑定 / `epic_done` 推送契约 |
| [`desktop-flow-rail-ux.md`](desktop-flow-rail-ux.md) | 右栏产品预期 |
| [`hub-shell-phase9-stoploss.md`](hub-shell-phase9-stoploss.md) | 失败可见 |
| `desktop/Sources/CCCDesktop/AppModel.swift` | bind / SSE / refresh |
| `scripts/chat_server/services/flow_events.py` | snapshot / `epic_done` 工具 |
| `scripts/chat_server/routers/desktop.py` | SSE 兜底轮询 + 主动推 |
| `tests/scripts/test_phase14_flow_rail_bind.py` | 7 契约测 |

---

## 8. 验证摘要

### 自验（执行方 · Cursor 重做）

```text
py_compile: 2/2 OK
ruff: All checks passed
pytest -k 'flow|snapshot|epic_done|stoploss|phase14': 17 passed
swift build -c release: Build complete! (~26s)
package-baseline: OK app 0.52.1 build 1
install: /Applications/CCCDesktop.app mtime 2026-07-21 13:52:43（stat 证伪与 .build 一致）
ContentView: FlowRail 去全局回退（§3.1 D）
```

### 终验（规划方）

```text
本地复跑：pytest 17 passed · py_compile/ruff/swift build/version sync OK
Mac2017：pull → kickstart com.ccc.chat-server → SSH 本机契约；LAN 通后再开 App 跑 §5.2 GUI
```