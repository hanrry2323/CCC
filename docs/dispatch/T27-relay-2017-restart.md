# 任务卡 T27 · 2017 中转站（6100/6102）修复：拉起进程 + launchd 常驻 + 三调用方验证（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1 · 依据：老板 2026-08-03 指示「Mac2017 的 OpenCode 和 Claude Code 中转站配置全部有问题，写指令修复」+ 中转站双轨决议（6100/6102 = CCC 体系专用，使用方仅 2017 Claude Code + OpenCode，均 flash 档位）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：已关闭 · 日期：2026-08-03 · 派发：manual · 项目：ccc

## 根因（Codex 已实锤）

6100/6102 中转站（`ai-loop-router-ccc`）**进程不在运行**，且 **launchd 无常驻注册**：
- `lsof -iTCP:6100/6102` 空（无监听）；
- `ps` 无 `dist/proxy.js` 进程；
- launchd 仅见 engine/board-scheduler/web-server，**无 6100/6102 中转站服务**；
- 旧 `com.ai-loop-router.plist` 指向 M1 旧路径（`~/program/infra/ai-loop-router`）且已禁用于 `disabled-relay-20260720/`，不是本实例；
- 三个调用方配置均指向 `127.0.0.1:6100/6102`（配置正确），因端口无进程而全部失败。

## 目标

在 Mac2017 把 `ai-loop-router-ccc`（6100 Anthropic / 6102 OpenAI Chat）**拉起来并以 launchd 常驻**（开机自启 + 崩溃自动拉起），验证 Claude Code（6100）、OpenCode（6102）、Engine env（6100）三调用方全部连通可用，M1 4100/4102 零影响。

## 红线（先看）

1. **M1 4100/4102 零接触**；只动 2017 侧 `ai-loop-router-ccc` 实例。
2. **密钥不落 git**：upstreams.json 内 API key（ccc_go_paid / zhipu 等）只存 2017 本地，提交内容不得含 key 明文。
3. **零硬编码**：端口（6100/6102）走 env 或启动参数，plist 路径变量化（或按既有模板规范填写，不写死到代码）。
4. 不碰：上游账号/upstreams.json 内容（保留现有配置）、Claude Code/OpenCode 指向（本来就对，只验证）、M1 中转站、2017 其他运行面。
5. 完成必须提交（真实 commit，如有配置模板/文档改动）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 步骤

### A. 拉起中转站（2017）

1. 确认目录与产物：`~/program/apps/ai-loop-router-ccc/dist/proxy.js` 存在、`node --version`（v22.16.0 满足）。
2. 以 6100/6102 启动（临时前台验证）：
   - `cd ~/program/apps/ai-loop-router-ccc && LOOP_ANTHROPIC_PORT=6100 LOOP_OPENAI_PORT=6102 node dist/proxy.js`
   - 确认 `lsof -iTCP:6100 -iTCP:6102 -P -sTCP:LISTEN` 两个端口监听。
3. 若端口 env 变量名与仓库实际约定不同，以仓库 README/`src/` 实际读取的 env 名为准（先 `grep -rn "PORT" src/` 确认），不得臆造。

### B. launchd 常驻（2017）

4. 新建 `~/Library/LaunchAgents/com.ccc.ai-loop-router.plist`（或仓库提供的 plist 模板，若无则按既有 `com.ccc.*` plist 规范写）：
   - Label：`com.ccc.ai-loop-router`（与 6100/6102 实例绑定，勿与 M1 旧 label 混淆）；
   - ProgramArguments：`node dist/proxy.js`（绝对路径）；
   - EnvironmentVariables：`LOOP_ANTHROPIC_PORT=6100`、`LOOP_OPENAI_PORT=6102`、PATH；
   - WorkingDirectory：`/Users/fan/program/apps/ai-loop-router-ccc`；
   - KeepAlive + RunAtLoad + StandardOut/Err 日志路径。
5. `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ccc.ai-loop-router.plist` → 确认监听。
6. **崩溃自愈验证**：kill 中转站进程 → 等待 KeepAlive 拉起（≤15s）→ 端口恢复、进程新 PID。

### C. 三调用方验证（2017）

7. Claude Code（6100）：`ANTHROPIC_BASE_URL=http://127.0.0.1:6100 claude -p "回复OK"`（或 curl 6100 对应路径）→ 出模型响应。
8. OpenCode（6102）：`opencode run --model loop/flash --auto --dir /tmp "回复OK"` → 出响应（之前实测可通，复验）。
9. Engine env（6100）：`~/.ccc/engine.env` 已指 `127.0.0.1:6100`，确认 `AGENT_PLANNER_BASE_URL` 可达（curl 6100 对应路径 200/非连接拒绝）。
10. M1 零影响：`lsof -iTCP:4100 -iTCP:4102` 与修复前一致（PID 不变）。

### D. 提交 + 回写

11. 如新增 plist 模板/启动脚本/README 说明 → 提交到 `ai-loop-router-ccc` 仓（M1 流转或 2017 直提，按仓规）；CCC 仓如有文档改动一并提交。
12. 回写：卡头 `状态：待分派 → 已回写`，回写区填（启动命令、launchd 注册、三调用方验证输出、崩溃自愈证据、M1 零影响证据、commit hash）。

## 回滚

- `launchctl bootout gui/$(id -u)/com.ccc.ai-loop-router` + 恢复旧状态（无进程状态即修复前状态）。
- 配置/plist 备份后再改；密钥不进 git。
- 触发条件：6100/6102 拉起失败 / Claude Code 或 OpenCode 任一不通 / M1 4100/4102 受影响 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `lsof -iTCP:6100 -iTCP:6102 -P -sTCP:LISTEN` 双端口监听；launchd `com.ccc.ai-loop-router` 注册且崩溃自愈验证通过。
2. Claude Code（6100）与 OpenCode（6102）实测出模型响应；Engine env（6100）可达。
3. M1 4100/4102 PID 对比零变化。
4. 无密钥进 git；零硬编码（端口走 env）；真实提交（如有仓内改动）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

Mac2017 `ai-loop-router-ccc`（6100 anthropic / 6102 openai-chat）已拉起并以 launchd 常驻（`com.ccc.ai-loop-router`，KeepAlive+RunAtLoad），崩溃自愈 ≤1s 拉起。Claude Code（6100）、OpenCode（6102）、Engine env（6100）三调用方全部实测出模型响应；M1 4100/4102 PID 零变化。commit `82cdf98` 已落 ai-loop-router-ccc 仓（plist 模板 + 启动脚本 + gitignore）。

### 执行明细

**A. 临时拉起验证（2017）**
- 产物核对：`~/program/apps/ai-loop-router-ccc/dist/proxy.js` 存在（205178B，2026-08-02）；node v22.16.0（>=18 满足）。
- env 名核对（`src/ports.ts`）：`LOOP_ANTHROPIC_PORT` → anthropic 端口；`LOOP_OPENAI_PORT` → openai 端口；OpenAI 默认 = anthropic+2。任务卡 env 名正确。
- 临时启动：`LOOP_ANTHROPIC_PORT=6100 LOOP_OPENAI_PORT=6102 nohup node dist/proxy.js` → PID 5673，双端口监听，日志「双端口就绪: 6100(anthropic) 6102(openai-chat)」。验证后 kill。

**B. launchd 常驻 + 崩溃自愈**
- plist 部署：`~/Library/LaunchAgents/com.ccc.ai-loop-router.plist`（Label `com.ccc.ai-loop-router`，ProgramArguments `/usr/local/bin/node` + `dist/proxy.js` 绝对路径，EnvironmentVariables `LOOP_ANTHROPIC_PORT=6100`/`LOOP_OPENAI_PORT=6102`/PATH，KeepAlive+RunAtLoad+ThrottleInterval 5+ExitTimeOut 30，日志 `~/program/apps/ai-loop-router-ccc/logs/stdout|stderr.log`）。对齐 `com.ccc.web-server`/`com.ccc.engine` 既有规范。
- `launchctl bootstrap gui/501` → exit 0，PID 6050，6100/6102 监听，无 stderr。
- 崩溃自愈：`kill -9 6050`（11:44:11）→ +1s KeepAlive 拉起 PID 6163，6100/6102 恢复监听（≤15s 要求达标）。

**C. 三调用方验证（2017）**
- Claude Code（6100）：`claude -p "回复OK"` → 「收到。」exit 0（config: ANTHROPIC_BASE_URL=127.0.0.1:6100, ANTHROPIC_MODEL=flash, token=ccc-relay-flash）。
- OpenCode（6102）：`opencode run --model loop/flash --auto "回复OK"` → 「OK」exit 0（config: baseURL=127.0.0.1:6102/v1, model=loop/flash）。
- Engine env（6100）：`curl http://127.0.0.1:6100/dashboard` → HTTP 200（connect=0.0004s）；`AGENT_PLANNER_BASE_URL=http://127.0.0.1:6100` 可达 HTTP 200。
- M1 零影响：`lsof -iTCP:4100 -iTCP:4102` PID 63542 修复前后未变。

**D. 提交**
- ai-loop-router-ccc 仓 commit `82cdf98`：`scripts/com.ccc.ai-loop-router.plist`（新建）+ `scripts/start-ccc-router.sh`（新建，手动 start/stop/status 运维脚本）+ `.gitignore`（补 `.ccc-router.pid`）。3 文件 151 行。
- 预存 `package-lock.json` 改动非本任务，未纳入提交。
- upstreams.json 未读未改（红线 2）；端口全走 env（红线 3）。

### 验收自检

1. ✅ `lsof -iTCP:6100 -iTCP:6102 -P -sTCP:LISTEN` 双端口监听（PID 6163）；launchd `com.ccc.ai-loop-router` 注册；崩溃自愈验证通过（kill -9 后 1s 拉起）。
2. ✅ Claude Code（6100）「收到。」+ OpenCode（6102）「OK」实测出模型响应；Engine env（6100）curl HTTP 200 可达。
3. ✅ M1 4100/4102 PID 63542 修复前后零变化。
4. ✅ 无密钥进 git（upstreams.json 在 .gitignore；plist/脚本无 key 明文）；端口走 `LOOP_*_PORT` env 零硬编码；真实 commit `82cdf98`。

---

## 验收区（Codex 独立取证 · 2026-08-03）

**结论：通过 ✅**（不看回写，全部实测）

| 验收项 | 独立取证结果 |
|--------|--------------|
| 6100/6102 监听 | SSH 实测双端口由 PID 6163（node dist/proxy.js）监听 ✅ |
| launchd 常驻 | `launchctl list` 见 `com.ccc.ai-loop-router`；崩溃自愈实测 kill 后 1 秒拉起新 PID ✅ |
| 三调用方 | Claude Code(6100)「收到。」/ OpenCode(6102)「OK」/ Engine env(6100) curl 200 全实测 ✅ |
| M1 零影响 | 4100/4102 PID 63542 对比未变 ✅ |
| 提交 | 2017 `82cdf98`（plist+启动脚本+gitignore，upstreams.json 不入库）；plist 无密钥明文 ✅ |
| 红线 | 端口走 env、密钥不落 git、M1 零接触 ✅ |

**关联问题（登记至 T26-R，非本卡缺陷）**：M1 工作树 `desktop/Sources/CCCDesktop/Models.swift` 存在一笔未提交的 85 行删除（删除了仍被引用的 `InboxProposal`/`ManualEpicForm`/`TaskTemplate`/`Phase`/`ProjectStats`），当前 `swift build` 编译失败——要求 Trae 恢复该文件（`git checkout -- desktop/Sources/CCCDesktop/Models.swift` 或补全被删类型），恢复构建绿 + 工作树仅剩预存 2 项。
