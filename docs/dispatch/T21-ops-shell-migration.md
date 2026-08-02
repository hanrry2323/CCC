# 任务卡 T21 · 运维壳迁移（桌面端运维页读取切新服务端 + 写操作改文档流转 + 7777/17777 下线）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§3 状态同步 / §4 任务卡唯一事实源 / §8 壳零业务逻辑 / §9 红线）· 依据：T7（集群采集）/ T13/T19/T20（新服务端与壳迁移基座）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-02
> 放行确认：老板 2026-08-02 明确「继续出下一步指令」；T20 遗留（reopen 走旧 Hub 写接口）为**本卡强制前置**，一并收口。

## 目标

桌面端运维页（OpsView）读取从旧 Hub 链路（`17777` 隧道 → `7777` chat-server，当前已断）**切换到新服务端 `server/web/server.py`（7788）只读接口**；运维写操作（日审/采纳/意图稳定/重开）全部改为**文档流转提示**（契约 §4/§8，含 T20 遗留 reopen 收口）；随后 `7777`（M1 本地 chat-server）与 `17777`（hub-tunnel SSH 隧道）下线。完成后 M1 旧 Hub 全部退净，桌面端只剩新服务端一条链路。

## 红线（先看）

1. **M1 4100/4102、2017 6100/6102 零接触**；2017 仓/进程零接触（2017 7777 已于 T18 停止，本卡不再涉及）。
2. **写操作一律不接新写接口、不直接改任务卡**：日审（runDailyReview）、采纳（adopt）、意图稳定（markMindGoalStable）、重开（reopenBoardTask/reopenOpsTask）在 `useNewServer` 下全部改为 toast 提示，由执行体回写/Engine 派发流转。
3. 新服务端只加**只读**运维接口；数据源复用 `server/engine/cluster.py` 采集（nodes/services/collected_at）+ 看板派生（severity 灯/生成时间），不重建旧 Hub 的 20+ 字段大汇总。
4. 零硬编码：端口/地址走 env；`cluster.py` 的 `DEFAULT_SERVICES` 若继续使用须登记或走配置（本卡不强制重构，登记在案）。
5. 不读不写外脑；归档区零改动；完成必须提交（真实 commit）；验收标准不可自行解释；工作树只允许预存 2 个无关改动。

## 范围

- `server/web/server.py`：新增只读接口 `GET /ops/summary`（Bearer 鉴权）——数据来自 cluster 采集 + board 派生，输出对齐桌面端 `OpsSummary` 可消费子集：`overview.machines`（节点/可达/存活端口数）、`down_ports`（不可达端口）、`generated_at`、`severity`（绿/黄/红灯）、`human_line`；字段缺失容错（旧 Hub 大字段一律置空/省略，桌面端容错）。
- `server/tests/test_http_api.py`：`/ops/summary` 用例（200 + 数据形状 + 401）。
- 桌面端 `APIClient.swift`：`fetchOpsOverview`/`fetchOpsRisks`/`fetchOpsSummary` 增加新服务端分支（复用 `newServerBaseURL`/token）；写方法（`runDailyReview`/`adopt` 等）不再走旧 Hub。
- 桌面端 `AppModel.swift`：`refreshOps` 走新服务端分支；`runDailyReview`/`adoptInboxProposal`/`adoptSuggestion`/`markMindGoalStable`/`reopenBoardTask`/`reopenOpsTask` 在 `useNewServer` 下改 toast 提示（T20 遗留收口）；`refreshOpsIntentGoals` 在 `useNewServer` 下置空并提示「意图收口走文档流转」（旧 Hub 已断）。
- `OpsView.swift`：只读展示适配新结构（空字段隐藏/降级），写按钮点击走提示；`swift build` 通过。
- M1 运行面：核实 `7777` 进程归属（无 launchd 则手动进程）→ 停止；`launchctl bootout gui/$(id -u)/com.ccc.hub-tunnel`（17777 隧道）→ 确认 `7777`/`17777` 清空、`7788` 正常。
- 不动：`7788`（新服务端）、`com.ccc.web-server`、2017、4100/4102/6100/6102。

## 步骤

### A. 新服务端只读运维接口（M1 仓，代码）

1. `server/web/server.py` 新增 `GET /ops/summary`：调用 cluster 采集（配置化 `CLUSTER_TARGETS`）→ 节点/服务状态映射为 `overview.machines`（host/ip/reachable/alive_ports/port_count）；不可达节点 → `down_ports`；`generated_at` = 采集时间；`severity` 按可达性/服务运行数派生（全正常=green、部分=amber、全断=red）；`human_line` 一句人话概览。
2. 缺采集配置或采集失败：返回 200 + 空结构 + `error` 字段（容错，不 500）。
3. 测试：`/ops/summary` 200 + 数据形状（machines 数组、generated_at、severity ∈ green|amber|red）+ 无 token 401；全量 `pytest server/tests/ -q` 全绿（现 184）。

### B. 桌面端运维页切换（M1 仓，代码）

4. `APIClient.swift`：`fetchOpsOverview`/`fetchOpsSummary` 走新服务端（`useNewServer` 时）；`fetchOpsRisks`/`fetchOpsUpstreamDaily` 在 `useNewServer` 下返回空（旧 Hub 字段不重建）。
5. `AppModel.swift`：
   - `refreshOps`：`useNewServer` 时只调新服务端 `/ops/summary`，映射 OpsSummary（overview/down_ports/severity/human_line），其余字段置空；
   - `runDailyReview`/`adoptInboxProposal`/`adoptSuggestion`/`markMindGoalStable`/`reopenBoardTask`/`reopenOpsTask`：`useNewServer` 下 toast「由执行体回写/文档流转，壳不直接改」（**T20 遗留 reopen 收口**）；
   - `refreshOpsIntentGoals`：`useNewServer` 下清空并提示。
6. `OpsView.swift`：只读区（概览/风险灯/节点表）适配；写按钮保留但走提示；缺失字段隐藏；`swift build` 通过。

### C. M1 运行面：7777 + 17777 下线（有回滚）

7. 核实：`ps aux | grep ccc-chat-server` + `launchctl list | grep -iE 'hub|chat|ccc'` 确认归属。
8. 备份：若 7777 有 launchd plist 先备份；hub-tunnel plist 备份 `com.ccc.hub-tunnel.plist.bak-ops-mig`。
9. 停 7777：确认由 `ccc-chat-server.py` 占用后停止该进程；`lsof -iTCP:7777` 清空。
10. 停 17777：`launchctl bootout gui/$(id -u)/com.ccc.hub-tunnel`；`lsof -iTCP:17777` 清空。
11. 确认 7788 正常：`/health` 200 + `/ops/summary` 带 token 200。

### D. 验证（全部必跑）

12. `pytest server/tests/ -q` 全绿（无回归）。
13. 运行面：7777/17777 已清空；7788 正常；4100/4102（node 63542）/6100/6102（node 69311）/2017 零接触（PID 对比）。
14. `rg` 三扫描：S1 用户路径 / S2 字面端口 / S3 模型名 / S4 工具名 + 明文密钥 + 外脑依赖 → 生产代码零命中（env 占位与文档除外）。
15. `git status`：仅剩预存 2 项。

### E. 提交 + 回写

16. 提交：`chore(ops-shell): T21 运维壳迁移 — 运维页读取切新服务端 + 写操作改文档流转 + 7777/17777 下线`
17. 回写：卡头 `状态：待分派 → 已回写`，回写区填完（真实 commit hash、各步结果、验收自检表）。

## 回滚

- 桌面端：`useNewServer` 关回旧分支（保留兼容代码）→ 运维页回旧链路（注：旧 Hub 已下线则不可用，回滚仅限代码层）。
- 7777/17777：恢复备份 plist → `launchctl bootstrap`；或重启原进程（代码未删）。
- 代码回滚：`git revert` 本卡提交。
- 触发条件：`/ops/summary` 冒烟失败 / 桌面端运维页不可读 / 7788 中断 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `/ops/summary` 只读接口带 token 200、无 token 401、数据形状正确（machines/generated_at/severity）、缺配置容错不 500。
2. 桌面端运维页读取走新服务端（代码 + `swift build`）；全部写操作（日审/采纳/意图稳定/**reopen**）在 `useNewServer` 下为文档流转提示，不调旧 Hub 写接口。
3. `7777` 与 `17777` 进程清空（plist 有备份）；7788 正常；4100/4102/6100/6102/2017 零接触。
4. `pytest` 全绿（184+新增）；三扫描零命中。
5. 真实提交；工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-02

### 结果摘要

（执行后填写）

### 执行明细

（执行后填写：A–E 各步结果）

### 验收自检

（执行后填写：对照验收标准逐条勾选）
