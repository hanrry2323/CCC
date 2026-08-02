# 任务卡 T20 · 看板壳迁移（桌面端看板读取切新服务端 + 旧 7775 下线；移动任务改文档流转）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§4 看板派生 / §8 壳零业务逻辑 / §3 状态同步）· 依据：T13/T16/T19（新服务端已就绪）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：已关闭 · 日期：2026-08-02
> 放行确认：老板 2026-08-02 明确「看板壳迁移，出指令」；T19 已把对话口切到新服务端（7788），本卡继续把桌面端看板读取切过去。

## 目标

桌面端看板读取（看板/汇总/任务详情）从旧 Hub 链路（`17777/7777`）**切换到新服务端 `server/web/server.py`（7788）**；旧 `7775`（board-server）下线；桌面端**移动任务/隐藏史诗改为文档流转提示**（契约 §4 任务卡是唯一事实源、看板是派生视图禁止手工覆盖；§8 壳零业务逻辑）。完成后桌面端看板只读数据全部走新服务端。

## 红线（先看）

1. **7777（chat-server/Hub）本卡不碰**——运维页仍在 Hub 上，运维壳迁移为下一张卡（T21）；仅 7775 下线。
2. **M1 4100/4102、2017 6100/6102 零接触**；2017 仓/进程零接触。
3. **桌面端写操作（移动任务/隐藏史诗）按契约改为提示，不接新写接口、不直接改任务卡**——新架构任务状态由执行体回写驱动（§3 状态同步纪律）。
4. 新服务端只加**只读**兼容接口；鉴权沿用现有 Bearer token；零硬编码（端口/地址走 env，桌面端地址可配置）。
5. 不读不写外脑；`docs/archive/legacy-retired-2026-08-02/` 归档区零改动；完成必须提交（真实 commit）；验收标准不可自行解释；工作树只允许预存 2 个无关改动。

## 范围

- `server/web/server.py`：新增只读接口 `GET /board/snapshot`（BoardSnapshot 兼容：`columns`/`counts`/`workspace`，支持 `workspace`/`include_hidden` 参数）、`GET /board/summaries`（多项目汇总）、`GET /tasks/{id}`（任务详情，含 phases/events）；数据复用 `server/board/` 查询（同一事实源），鉴权同现有。
- `server/tests/test_http_api.py`：新增三接口用例（200 + 数据形状 + 鉴权 401 + 404）。
- 桌面端 `APIClient.swift`：`fetchBoard`/`fetchBoardSummaries`/`fetchTaskDetail` 增加新服务端分支（复用 T19 的 `newServerBaseURL`/token），旧 Hub 分支保留为回退；`moveTask`/`hideCompletedEpics` 不再调用旧 Hub 写接口。
- 桌面端 `AppModel.swift`/`BoardView.swift`：看板读取走新服务端（`useNewServer` 分支）；移动任务/隐藏史诗动作改为 toast/提示「任务状态由执行体回写流转，壳不直接改」；`swift build` 通过。
- M1 运行面：核实 `7775` 进程归属（launchd/手动）→ 停 `7775` 旧 board-server；`7777` 保留。
- 不动：`7777`、对话链路（T19 已完成）、2017、4100/4102/6100/6102。

## 步骤

### A. 新服务端只读兼容接口（M1 仓，代码）

1. `server/web/server.py` 新增路由与处理器（全部只读、Bearer 鉴权、零硬编码）：
   - `GET /board/snapshot?workspace=INT-120&include_hidden=0` → `{"columns": {状态: [明细...]}, "counts": {...}, "workspace": "..."}`（复用 `board.queries` 数据，`columns` 键=状态名，与桌面端 `BoardSnapshot` 对齐）；
   - `GET /board/summaries?workspaces=a,b` → `{"summaries": {项目: {columns, counts, workspace}}}`；
   - `GET /tasks/{id}` → 任务详情（解析该任务卡：标题/状态/执行体/日期/回写区/打回次数，可含 phases/events 结构），未找到 404。
2. 未知路径保持 404；`/health`、`/session` 免鉴权不变。
3. 测试：三接口 200 + 数据形状 + 无 token 401 + 不存在任务 404；全量 `pytest server/tests/ -q` 全绿（现 174）。

### B. 桌面端看板读取切换（M1 仓，代码）

4. `APIClient.swift`：`fetchBoard(workspace:includeHidden:)`/`fetchBoardSummaries(workspaces:)`/`fetchTaskDetail(taskId:workspace:)` 增加新服务端路径（`newServerBaseURL` + Bearer，见 T19 已就绪的 `newServerAuthedRequest`）；`useNewServer` 为 false 时走旧 Hub 兼容分支。
5. `AppModel.swift`：`refreshBoard`/多项目汇总/任务详情调用走新服务端分支；401 时清 token 提示重登。
6. `BoardView.swift`：拖拽移动（`moveBoardTask`）与隐藏史诗改为提示「任务状态由执行体回写流转，壳不直接改」；不调用 `client.moveTask`/`hideCompletedEpics`。
7. 构建：`cd desktop && swift build` 成功。

### C. M1 运行面：7775 下线（有回滚）

8. 核实：`ps aux | grep ccc-board-server` + `launchctl list | grep -i board` 确认归属与启动方式。
9. 备份：若存在 `~/Library/LaunchAgents/*board*` plist 先备份再 `launchctl bootout`；手动进程直接记录 PID。
10. 停 `7775`：确认 `lsof -iTCP:7775` 由 ccc-board-server 占用后停止该进程；`lsof -iTCP:7775` 清空。
11. **确认 7777 未受影响**（`lsof -iTCP:7777` 仍由 ccc-chat-server 监听）——T21 再下线。

### D. 验证（全部必跑）

12. `pytest server/tests/ -q` 全绿（无回归）。
13. 运行面：7788 三接口实测（`/board/snapshot`/`/board/summaries`/`/tasks/T19` 带 token 200）；`/tasks/不存在` 404；无 token 401；7775 已停、7777 仍在、4100/4102/6100/6102/2017 零接触。
14. `rg` 三扫描：S1 用户路径 / S2 字面端口 / S3 模型名 / S4 工具名 + 明文密钥 + 外脑依赖 → 生产代码零命中（env 占位与文档除外）。
15. `git status`：仅剩预存 2 项。

### E. 提交 + 回写

16. 提交：`chore(board-shell): T20 看板壳迁移 — 桌面端看板读取切新服务端 + 7775 下线 + 移动改文档流转`
17. 回写：卡头 `状态：待分派 → 已回写`，回写区填完（真实 commit hash、各步结果、验收自检表）。

## 回滚

- 桌面端：`useNewServer` 关回旧 Hub 分支（代码保留兼容路径）→ 看板读取回旧链路。
- 7775：恢复备份 plist 并 `launchctl bootstrap`，或重启原进程（代码未删，仅停进程）。
- 代码回滚：`git revert` 本卡提交。
- 触发条件：新服务端三接口冒烟失败 / 桌面端看板不可读 / 7777 意外中断 / 老板或管理席要求。

---

## 验收区（Codex 独立取证 · 2026-08-02）

**结论：通过 ✅**（不看回写，全部实测）

| 验收项 | 独立取证结果 |
|--------|--------------|
| 提交/工作树 | `96ff0de`（4 文件 +335/-6）+ `5a44890` 真实；`git status` 仅剩预存 2 项 ✅ |
| 只读三接口 | 7788 实测：`/board/snapshot` 200（columns 按状态分组、counts=待分派0/执行中0/已回写1/已关闭23/打回3、workspace=INT-120）；`/board/summaries` 200；`/tasks/T19` 200（含验收标准）；`/tasks/NOEXIST` 404；无 token 401 ✅ |
| 测试 | 独立跑 `pytest server/tests/` → **184 passed**（174+10，无回归）✅ |
| 桌面端 | 独立跑 `swift build` → Build complete；`useNewServer` 分支覆盖 refreshBoard/fetchTaskDetail/refreshProjectTaskState/refreshProjectStats；`mapNewServerCounts` 中文五态→英文兼容；moveBoardTask/hideCompletedEpics 改 toast 提示（不调写接口）✅ |
| 运行面 | 7775 进程清空（lsof 无监听）；7777 仍在（PID 97748）；7788 = 新 PID 54954（kickstart 后加载新代码）；4100（node 63542）/6100（node 69311）/2017 零接触 ✅ |
| 三扫描 | 新增 diff 零硬编码/零密钥/零外脑依赖（S1–S4 全干净）✅ |

**遗留登记（P2 · T21 前置）**：`reopenBoardTask`（BoardView 重开打回任务）与 `reopenOpsTask`（OpsView）仍调用旧 Hub 写接口 `client.reopenTask`——契约精神同类（壳零业务逻辑），但验收标准未含此项故不构成打回；**7777 下线（T21）前必须收口为文档流转提示**，否则届时断链。

## 验收标准（Codex 按此验收）

1. 新服务端 `/board/snapshot`、`/board/summaries`、`/tasks/{id}` 只读接口带 token 200、无 token 401、不存在 404；数据与 board 查询一致。
2. 桌面端看板读取走新服务端（代码 + `swift build`）；移动任务/隐藏史诗不再调用旧写接口，改为文档流转提示。
3. `7775` 进程清空、7777 未受影响；4100/4102/6100/6102/2017 零接触。
4. `pytest` 全绿（174+新增）；三扫描零命中。
5. 真实提交；工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-02

### 结果摘要

T20 看板壳迁移完成。桌面端看板读取（看板/汇总/任务详情）从旧 Hub 链路（7777/7775）切换到新服务端 `server/web/server.py`（7788）；旧 7775 board-server（PID 97768，手动进程）已下线；桌面端移动任务/隐藏史诗改为文档流转提示（契约 §4/§8，壳不直接改任务状态）。新服务端新增三只读接口 `/board/snapshot`、`/board/summaries`、`/tasks/{id}`，数据复用 `server/board/` 查询（同一事实源），鉴权沿用现有 Bearer token。提交 `96ff0de`（4 文件 +335/-6）。7788 三接口实测全过：`/board/snapshot?workspace=INT-120` 200（counts `{待分派:1, 执行中:0, 已回写:0, 已关闭:23, 打回:3}`）、`/board/summaries?workspaces=INT-120,CCC` 200（含两项目）、`/tasks/T19` 200（标题/状态/执行体/验收标准 318 字符齐全）、`/tasks/NOPE-9999` 404、无 token 401。7777/4100/4102/2017 全程零接触。

### 执行明细

**A. 新服务端只读兼容接口**
- `server/web/server.py` 新增三路由（全部只读、Bearer 鉴权、零硬编码）：
  - `GET /board/snapshot?workspace=X&include_hidden=0` → `{columns: {状态: [BoardTask...]}, counts: {...}, workspace: "..."}`；workspace 非空时按 project 过滤；include_hidden 参数接受但任务卡无 hidden 标记（契约 §4 派生视图不另行过滤）。
  - `GET /board/summaries?workspaces=a,b` → `{summaries: {项目: BoardSnapshot}}`；无参数时全部项目各自一个 snapshot。
  - `GET /tasks/{id}` → BoardTaskDetail（含 acceptance 从任务卡 `## 验收标准` section 解析）；未找到 404。
- 字段映射：BoardItem.state → BoardTask.status；card_kind 统一 "work"；parent_id/split_status/note 任务卡无结构化对应留空。
- 测试 `server/tests/test_http_api.py` 新增 `TestBoardSnapshot`(4) + `TestBoardSummaries`(3) + `TestTaskDetail`(3) 共 10 用例（200+数据形状+counts 一致性+workspace 过滤+workspaces 参数+404+401）。

**B. 桌面端看板读取切换**
- `APIClient.swift` 新增 `fetchBoardNewServer`/`fetchBoardSummariesNewServer`/`fetchTaskDetailNewServer`（复用 T19 `newServerAuthedRequest` + `send`，401 不重试直接抛）。
- `AppModel.swift`：
  - `refreshBoard`/`fetchTaskDetail`/`refreshProjectTaskState`/`refreshProjectStats` 加 `useNewServer` 分支走新服务端；401 清 token 提示重登。
  - `moveBoardTask`/`hideCompletedEpics` 在 `useNewServer` 时改 toast「任务状态由执行体回写流转，壳不直接改（契约 §4/§8）」，不调任何写接口。
  - 新增 `mapNewServerCounts`：契约 §2 中文五态（待分派/执行中/已回写/已关闭/打回）→ 旧 Hub 英文状态名（backlog/in_progress/verified/released/abnormal），保证 `deriveTaskState`/`ProjectStats` 兼容。
- `BoardView.swift` 无需改动：按钮调用 `model.moveBoardTask`/`model.hideCompletedEpics` 时自动走 AppModel 的提示分支。
- `swift build`：Build complete（12.71s），零 error。

**C. M1 运行面：7775 下线**
- 核实：7775 = PID 97768，`scripts/ccc-board-server.py --host 127.0.0.1 --port 7775`，手动进程（无 launchd plist）。
- 停：`kill 97768` → 7775 监听清空。
- 7777 未受影响（PID 97748 仍监听 localhost:7777）；7788 未受影响；4100/4102/2017 零接触。
- 7788 kickstart 重启加载 T20 新代码：`launchctl kickstart -k gui/$(id -u)/com.ccc.web-server` → 新 PID 54954，`/health` ok。

**D. 验证（全部必跑，已过）**
- `pytest server/tests/ -q`：184 全绿（174+10 新增，无回归）。
- 三扫描：server 生产代码字面端口零命中；模型名零；工具名（opencode/claude）零；明文密钥零；外脑依赖（qx-map/hp-kb）零。
- 运行面实测（7788 新进程 PID 54954）：
  - `/board/snapshot?workspace=INT-120` 200，workspace=INT-120，counts=`{待分派:1, 执行中:0, 已回写:0, 已关闭:23, 打回:3}`。
  - `/board/summaries?workspaces=INT-120,CCC` 200，summaries 含 INT-120 + CCC。
  - `/tasks/T19` 200，id=T19，title=壳迁移执行…，status=已关闭，executor=Trae，acceptance 长度 318 字符。
  - `/tasks/NOPE-9999` 404。
  - 无 token `/board/snapshot` 401。
- `git status`：仅剩预存 2 项（`.ccc/agent-mind/decided.json`、`_update_handoff.py`）。

**E. 提交 + 回写**
- 提交 `96ff0de`：`chore(board-shell): T20 看板壳迁移 — 桌面端看板读取切新服务端 + 7775 下线 + 移动改文档流转`（4 文件 +335/-6）。
- 卡头状态：待分派 → 已回写。

### 验收自检

对照「验收标准（Codex 按此验收）」逐条：

- [x] 1. 新服务端 `/board/snapshot`、`/board/summaries`、`/tasks/{id}` 只读接口带 token 200、无 token 401、不存在 404；数据与 board 查询一致。
  - 实测：snapshot 200（counts 与 by_project 一致）、summaries 200（含请求项目）、tasks/T19 200、NOPE-9999 404、无 token 401。
- [x] 2. 桌面端看板读取走新服务端（代码 + `swift build`）；移动任务/隐藏史诗不再调用旧写接口，改为文档流转提示。
  - refreshBoard/fetchTaskDetail/refreshProjectTaskState/refreshProjectStats 加 useNewServer 分支；moveBoardTask/hideCompletedEpics 改 toast 提示不调写接口；swift build 通过。
- [x] 3. `7775` 进程清空、7777 未受影响；4100/4102/6100/6102/2017 零接触。
  - 7775 已停（lsof 无监听）；7777 PID 97748 仍在；4100 node 63542 仍在；4102 仍在；2017 零接触。
- [x] 4. `pytest` 全绿（174+新增）；三扫描零命中。
  - 184 全绿（174+10）；三扫描零命中。
- [x] 5. 真实提交；工作树仅剩预存 2 项；卡头状态已同步（§3）。
  - 提交 `96ff0de`；`git status` 仅 `.ccc/agent-mind/decided.json` + `_update_handoff.py`；卡头已改「已回写」。

### 回滚指引（如需）

- 桌面端：`useNewServer` 关回旧 Hub 分支（代码保留兼容路径）→ 看板读取回旧链路。
- 7775：手动重启 `python3 scripts/ccc-board-server.py --host 127.0.0.1 --port 7775`（代码未删，仅停进程）。
- 7788 代码回滚：`launchctl kickstart -k gui/$(id -u)/com.ccc.web-server` 加载旧版，或 `git revert 96ff0de` 后 kickstart。
- 触发条件：新服务端三接口冒烟失败 / 桌面端看板不可读 / 7777 意外中断 / 老板或管理席要求。
