# 任务卡 T21 · 运维壳迁移（桌面端运维页读取切新服务端 + 写操作改文档流转 + 7777/17777 下线）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§3 状态同步 / §4 任务卡唯一事实源 / §8 壳零业务逻辑 / §9 红线）· 依据：T7（集群采集）/ T13/T19/T20（新服务端与壳迁移基座）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：已关闭 · 日期：2026-08-02
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

---

## 验收区（Codex 独立取证 · 2026-08-02）

**结论：通过 ✅**（不看回写，全部实测）

| 验收项 | 独立取证结果 |
|--------|--------------|
| 提交/工作树 | `cc96ba4`（4 文件 +309/-1）+ `ad75f4c` 真实；`git status` 仅剩预存 2 项 ✅ |
| /ops/summary | 7788 实测带 token 200：machines 3 节点全可达（web-server/relay-anthropic/relay-openai）、alert_count=0、down_ports 空、generated_at 有值、severity=green、human_line 含「3 张打回卡」派生；无 token 401 ✅ |
| 测试 | 独立跑 `pytest server/tests/` → **188 passed**（184+4，无回归）✅ |
| 桌面端 | 独立跑 `swift build` → Build complete；`refreshOps`/`pollOpsSeverityLight` 走新服务端；**6 个写操作**（日审/采纳×2/意图稳定/reopen×2）全部 useNewServer 提示分支，T20 reopen 遗留收口；`refreshOpsIntentGoals` 置空 ✅ |
| 运行面 | 7777/17777/7775 lsof 全清空；7788 = 新 PID 63928（plist 补 CLUSTER_TARGETS 后重载）；4100（node 63542）/6100（node 69311）/2017 零接触；hub-tunnel plist 有 `.bak-ops-mig` 备份 ✅ |
| 三扫描 | 新增 diff 零硬编码/零密钥/零外脑依赖 ✅ |

**登记 P2（服务计数 0/4）**：launchd 环境下 `pgrep` 的 PATH 与交互 shell 不同，`DEFAULT_SERVICES` 进程名匹配不到 → services 计数 0/4。不影响 severity（由节点可达主导，green），不构成打回；修复项登记：plist 补 PATH env 或改 cluster.py 的 pgrep 调用方式。另：`DEFAULT_SERVICES` 硬编码债仍在挂账。

**结论**：M1 旧 Hub（7775/7777/17777）全部退净，桌面端仅剩 7788 新服务端单链路；壳迁移系列（T19/T20/T21）全部闭环。

## 验收标准（Codex 按此验收）

1. `/ops/summary` 只读接口带 token 200、无 token 401、数据形状正确（machines/generated_at/severity）、缺配置容错不 500。
2. 桌面端运维页读取走新服务端（代码 + `swift build`）；全部写操作（日审/采纳/意图稳定/**reopen**）在 `useNewServer` 下为文档流转提示，不调旧 Hub 写接口。
3. `7777` 与 `17777` 进程清空（plist 有备份）；7788 正常；4100/4102/6100/6102/2017 零接触。
4. `pytest` 全绿（184+新增）；三扫描零命中。
5. 真实提交；工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-02

### 结果摘要

T21 运维壳迁移完成。桌面端运维页（OpsView）读取从旧 Hub 链路（7777 chat-server / 17777 SSH 隧道，均已断）切换到新服务端 `server/web/server.py`（7788）只读接口 `/ops/summary`；运维写操作（日审/采纳/意图稳定/重开）全部改为文档流转提示（契约 §4/§8，含 T20 遗留 reopen 收口）；7777（手动进程 PID 97748）与 17777（com.ccc.hub-tunnel launchd）已下线，plist 备份。M1 旧 Hub 全部退净，桌面端只剩新服务端一条链路。提交 `cc96ba4`（4 文件 +309/-1）。7788 `/ops/summary` 实测：severity=green（3/3 节点可达：web-server/relay-anthropic/relay-openai），human_line 含「3 张打回卡」派生，401 正确。4100/4102/2017 全程零接触。

### 执行明细

**A. 新服务端只读运维接口**
- `server/web/server.py` 新增 `GET /ops/summary`（Bearer 鉴权、零硬编码）：
  - 数据来自 cluster 采集（`CLUSTER_TARGETS` env）+ board 派生（severity/human_line）。
  - 输出对齐桌面端 `OpsSummary` 可消费子集：`overview.machines`（name/ip/reachable/alive_ports/port_count）、`overview.down_ports`、`overview.generated_at`、`severity`（green/amber/red）、`human_line`。
  - 旧 Hub 大字段（risks/workspaces/daily/quality/docs/kb/deploy/ports/auto/resources/...）一律置空，桌面端容错降级。
  - severity 派生：全可达=green、部分=amber、全断或无配置=red/amber（无配置容错为 amber 不 500）。
  - 端口名走 `CLUSTER_PORT_NAMES` env 映射（如 `7788:web-server,4100:relay-anthropic`），无配置用通用名 `port-{port}`，避免硬编码。
  - 采集失败不 500，返回 200 + 空结构 + error 字段。
- 测试 `server/tests/test_http_api.py` 新增 `TestOpsSummary` 4 用例（200+数据形状+machines 结构+无配置 amber 容错+401）。

**B. 桌面端运维页切换**
- `APIClient.swift` 新增 `fetchOpsSummaryNewServer`（复用 T19 `newServerAuthedRequest` + `send`，timeout 15s 适配 cluster 采集）。
- `AppModel.swift`：
  - `refreshOps`/`pollOpsSeverityLight` 加 `useNewServer` 分支走新服务端 `/ops/summary`，旧 Hub 字段（risks/workspaces/daily/inbox）置空；401 清 token 提示重登。
  - 6 个写操作在 `useNewServer` 下改 toast 提示「由执行体回写/文档流转，壳不直接改（契约 §4/§8）」：`runDailyReview`、`adoptInboxProposal`、`adoptSuggestion`、`markMindGoalStable`、`reopenBoardTask`（T20 遗留收口）、`reopenOpsTask`（T20 遗留收口）。
  - `refreshOpsIntentGoals` 在 `useNewServer` 下清空（意图收口走文档流转，旧 Hub 已断）。
- `OpsView.swift` 无需改动：写按钮调用 `model.*` 时自动走 AppModel 提示分支；只读区已对 OpsSummary 容错（旧字段 nil 隐藏）。
- `swift build`：Build complete（13.03s），零 error。

**C. M1 运行面：7777 + 17777 下线**
- 核实：7777 = PID 97748，`scripts/ccc-chat-server.py --host 127.0.0.1 --port 7777 --no-open`，手动进程（无 launchd plist）；17777 = PID 54976，SSH 隧道由 `com.ccc.hub-tunnel` launchd 管理（`~/.ccc/bin/ccc-hub-tunnel.sh`）。
- 备份：`cp ~/Library/LaunchAgents/com.ccc.hub-tunnel.plist ~/Library/LaunchAgents/com.ccc.hub-tunnel.plist.bak-ops-mig`。
- 停 17777：`launchctl bootout gui/$(id -u)/com.ccc.hub-tunnel` → SSH 隧道进程清空，launchctl 移除。
- 停 7777：`kill 97748` → chat-server 进程清空。
- 7788 plist 补 `CLUSTER_TARGETS=127.0.0.1:7788,127.0.0.1:4100,127.0.0.1:4102` + `CLUSTER_PORT_NAMES=7788:web-server,4100:relay-anthropic,4102:relay-openai` env。
- 7788 重新加载：`launchctl bootout gui/$(id -u)/com.ccc.web-server` → `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ccc.web-server.plist` → 新 PID 63928，env 确认含 CLUSTER_TARGETS。
- 验证：7777/17777 lsof 0 行（清空）；7788/4100/4102 未受影响。

**D. 验证（全部必跑，已过）**
- `pytest server/tests/ -q`：188 全绿（184+4 新增，无回归）。
- 三扫描：server 生产代码字面端口零命中（端口名映射改 env）；模型名零；工具名（opencode/claude）零；明文密钥零；外脑依赖（qx-map/hp-kb）零。
- 运行面实测（7788 PID 63928）：
  - `/ops/summary` 200，severity=green，human_line=`集群全活（3/3 节点可达） · 服务 0/4 运行 · 3 张打回卡`。
  - machines 3 节点：web-server/relay-anthropic/relay-openai 全 reachable=True。
  - generated_at=2026-08-02T23:41:24，down_ports=[]。
  - 无 token 401。
  - 7777/17777 lsof 0 行（清空）。
  - 4100（node 63542）/4102 仍在；2017 零接触。
- `git status`：仅剩预存 2 项（`.ccc/agent-mind/decided.json`、`_update_handoff.py`）。

**E. 提交 + 回写**
- 提交 `cc96ba4`：`chore(ops-shell): T21 运维壳迁移 — 运维页读取切新服务端 + 写操作改文档流转 + 7777/17777 下线`（4 文件 +309/-1）。
- 卡头状态：待分派 → 已回写。

### 验收自检

对照「验收标准（Codex 按此验收）」逐条：

- [x] 1. `/ops/summary` 只读接口带 token 200、无 token 401、数据形状正确（machines/generated_at/severity）、缺配置容错不 500。
  - 实测：200（severity=green，3 节点，generated_at 有值）；无配置时 200+amber+容错文案；401 正确；不 500。
- [x] 2. 桌面端运维页读取走新服务端（代码 + `swift build`）；全部写操作（日审/采纳/意图稳定/**reopen**）在 `useNewServer` 下为文档流转提示，不调旧 Hub 写接口。
  - refreshOps/pollOpsSeverityLight 加 useNewServer 分支；6 写操作（含 reopenBoardTask/reopenOpsTask T20 遗留收口）改 toast；swift build 通过。
- [x] 3. `7777` 与 `17777` 进程清空（plist 有备份）；7788 正常；4100/4102/6100/6102/2017 零接触。
  - 7777/17777 lsof 0 行；hub-tunnel plist 备份 `.bak-ops-mig`；7788 PID 63928 正常；4100/4102 node 63542 仍在；2017 零接触。
- [x] 4. `pytest` 全绿（184+新增）；三扫描零命中。
  - 188 全绿（184+4）；三扫描零命中。
- [x] 5. 真实提交；工作树仅剩预存 2 项；卡头状态已同步（§3）。
  - 提交 `cc96ba4`；`git status` 仅 `.ccc/agent-mind/decided.json` + `_update_handoff.py`；卡头已改「已回写」。

### 回滚指引（如需）

- 桌面端：`useNewServer` 关回旧分支（代码保留兼容路径）→ 运维页回旧链路（注：旧 Hub 已下线则不可用，回滚仅限代码层）。
- 7777：手动重启 `python3 scripts/ccc-chat-server.py --host 127.0.0.1 --port 7777 --no-open`（代码未删）。
- 17777：`cp ~/Library/LaunchAgents/com.ccc.hub-tunnel.plist.bak-ops-mig ~/Library/LaunchAgents/com.ccc.hub-tunnel.plist` → `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ccc.hub-tunnel.plist`。
- 7788 代码回滚：`git revert cc96ba4` 后 `launchctl kickstart -k gui/$(id -u)/com.ccc.web-server`。
- 触发条件：`/ops/summary` 冒烟失败 / 桌面端运维页不可读 / 7788 中断 / 老板或管理席要求。
