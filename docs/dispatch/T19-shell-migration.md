# 任务卡 T19 · 壳迁移执行（7788 对话口 + 桌面端 + HTTP 页面切新服务端，对话接大脑）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 拓扑 / §9 红线 / D8 多壳）· 依据：T16（API/鉴权已就绪）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-02
> 放行确认：老板 2026-08-02 明确「出壳迁移指令，Trae 执行」；T16 服务端侧已验收通过（`88cf04a`）。

## 目标

把 7788 对话口 + 桌面端 + HTTP 页面从旧 sidecar/Hub 链路**切换到新服务端 `server/web/server.py`**（账号密码 + Bearer token，已就绪），并把 `/conversation` 从回声占位升级为**真实大脑对话**（转发配置的模型上游）。完成后旧 sidecar（7788）下线，桌面端与 HTTP 页面作为纯壳经 HTTP 直连新服务端。

## 红线（先看）

1. **M1 4100/4102 中转站零改动；2017 6100/6102 中转站只读调用、不停止**；2017 仓/2017 任何进程**零接触**（2017 代码流转另排卡）。
2. **旧 sidecar 下线前必须**：新服务端已起、冒烟通过（/health + /session + /conversation 真实回复）；plist 先备份；失败立即回滚恢复 sidecar。
3. **零硬编码**：端口/host/账号/上游地址/模型名一律 env 配置；密钥零落库、零进 git。
4. 不读不写外脑（qx-map / HP KB）；`docs/archive/legacy-retired-2026-08-02/` 归档区零改动。
5. 桌面端改动限「APIClient 接入点 + 登录/发送薄 UI 层」，不重构旧业务、不碰看板链路（看板切换为后续卡）。
6. 完成必须提交（真实 commit）；验收标准不可自行解释；工作树只允许预存 2 个无关改动（`.ccc/agent-mind/decided.json`、`_update_handoff.py`）。

## 范围

- `server/web/server.py`：`/conversation` 回声占位 → 转发配置的模型上游（stdlib urllib 实现，非流式），配置化；保留鉴权与对话历史。
- `server/deploy/`：新增新服务端 launchd plist 模板（变量化零字面量）+ 启动/健康示例脚本。
- `server/config/config.example.env`：补齐对话上游/模型名/账号占位说明（已有 `CCC_WEB_USERNAME`/`CCC_WEB_PASSWORD_HASH`/`CCC_WEB_TOKEN_TTL`/`RELAY_UPSTREAM_URL`/`RELAY_UPSTREAM_KEY`）。
- HTTP 页面 `server/web/index.html`（+ 必要 js/css）：登录入口（账号密码 → `POST /session` → token 注入 Bearer），对话框走 `/conversation`；保留 `file://` 零 API 模式与 `?api=`/`?token=` 兼容。
- 桌面端 `desktop/Sources/CCCDesktop/`：AppModel/ContentView 接入 T16 已就绪的 `configureNewServer`/`loginToNewServer`/`sendConversation`，新增登录 UI（账号密码 → token），对话发送走新链路，401 提示重登；默认指向本机新服务端，旧地址兼容开关保留。
- M1 运行面：备份 sidecar plist → `launchctl bootout gui/$(id -u)/com.ccc.agent-sidecar` → 确认 7788 释放 → bootstrap 新服务端 plist（host 0.0.0.0 / 端口 7788，env 配置）→ 冒烟。
- 不动：7777（chat-server）/ 7775（board-server）旧进程（看板壳迁移为后续卡）；2017 侧一切。

## 步骤

### A. 服务端升级（M1 仓，代码）

1. `server/web/server.py` `_handle_conversation_post`：读 env 配置的上游地址/密钥/模型名（零字面量，缺配置返回 503 明确错误）；stdlib `urllib.request` 转发（POST，携带 Bearer/上游约定头）；收到上游回复后存历史并返回 `{"reply": ...}`；上游失败返回 502 且不落历史。
2. 保留：鉴权中间件、`/session`、`/health`、`/board/*`、对话历史。
3. 测试：`server/tests/test_http_api.py` 补用例——缺上游配置 503、上游成功往返（mock 上游）、上游失败 502、鉴权三态不回归；全量 `pytest server/tests/ -q` 必须全绿（现 171）。

### B. 部署模板

4. `server/deploy/` 新增 `com.ccc.web-server.plist` 模板：Label/ProgramArguments/WorkingDirectory/KeepAlive/StandardOut-Err 全变量化（`$PYTHON_BIN`/`$PROJECT_ROOT`/`$LOG_DIR`/`$USERNAME`），端口/host 走 env（`WEB_PORT`/`WEB_HOST`），零字面量。
5. `run.example.sh` / `health.example.sh` 补 web-server 启动与健康检查示例（`$PYTHON_BIN -m server.web.server --host "$WEB_HOST" --port "$WEB_PORT"` + `curl /health`）。

### C. HTTP 页面登录 + 对话

6. `server/web/index.html`：新增登录区（账号/密码输入 + 登录按钮）；登录成功 `POST /session` → token 存 `localStorage`（与 `?token=` 兼容：URL 参数优先）；所有 `/board/*` 与 `/conversation` 请求注入 Bearer；无 token 或 401 显示登录提示；保留 `file://` 本地数据回退。
7. 对话区：消息输入 → `POST /conversation` → 渲染回复；401 提示重登。

### D. 桌面端接入

8. `AppModel.swift`：对话发送路径接入 `configureNewServer(url:)` + `loginToNewServer(username:password:)` + `sendConversation(message:)`；新增登录状态/账号密码存储（Keychain 或 AppStorage，不得明文进 git）；401 时清 token 提示重登。
9. `ContentView.swift`（或对应设置视图）：登录 UI（账号/密码/服务器地址，默认 `http://127.0.0.1:7788`）。
10. 构建验证：`cd desktop && swift build` 成功（仅允许无害警告）。

### E. M1 运行面切换（有回滚）

11. 备份：`cp ~/Library/LaunchAgents/com.ccc.agent-sidecar.plist ~/Library/LaunchAgents/com.ccc.agent-sidecar.plist.bak-shell-mig`
12. 先起新服务端冒烟（可临时进程，验证通过后再转 launchd）：`WEB_PORT=7788 WEB_HOST=0.0.0.0 ... $PYTHON_BIN -m server.web.server` → `/health` 200、`/session` 换 token、`/conversation` 真实回复（非 `echo:`）。
13. 停旧：`launchctl bootout gui/$(id -u)/com.ccc.agent-sidecar` → `ps aux | grep agent-sidecar` 清空；`lsof -iTCP:7788` 确认释放。
14. 装新：把 web-server plist 装到 `~/Library/LaunchAgents/`（替换变量 → `launchctl bootstrap gui/$(id -u)/com.ccc.web-server`）→ 确认 7788 由新服务端监听（PID 变化可证）。
15. 桌面端切换到新服务端（第 D 步产物）：配置服务器地址 + 账号密码登录 → 真实对话往返成功。

### F. 验证（全部必跑）

16. `pytest server/tests/ -q` 全绿（无回归，含新增用例）。
17. `rg` 三扫描：S1 用户路径 / S2 字面端口 / S3 模型名 / S4 工具名 + 明文密钥 + 外脑依赖 → 生产代码零命中（env 占位与文档除外）。
18. 运行面终验：7788 = 新服务端（PID 非旧 sidecar）；`/session` 换 token；`/conversation` 真实回复；桌面端登录 + 对话成功。
19. `git status`：仅剩预存 2 项。

### G. 提交 + 回写

20. 提交：`chore(shell): T19 壳迁移 — 对话接大脑 + 桌面端/HTTP 切新服务端 + 旧 sidecar 下线`
21. 回写：卡头 `状态：待分派 → 已回写`，回写区填完（真实 commit hash、各步结果、验收自检表）。

## 回滚

- 恢复旧对话：`launchctl bootout gui/$(id -u)/com.ccc.web-server` → `cp ~/Library/LaunchAgents/com.ccc.agent-sidecar.plist.bak-shell-mig ~/Library/LaunchAgents/com.ccc.agent-sidecar.plist` → `launchctl bootstrap gui/$(id -u)/com.ccc.agent-sidecar` → 桌面端地址改回旧值。
- 代码回滚：`git revert` 本卡提交（或 `git checkout` 上版），不影响 7777/7775/2017。
- 触发条件：/conversation 无真实回复 / 桌面端登录失败不可修复 / 7788 未由新服务端接管 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `/conversation` 返回真实模型回复（非 `echo:`），缺上游配置 503、上游失败 502；测试覆盖。
2. HTTP 页面：登录换 token 成功，带 token 请求 `/board/*` 与 `/conversation` 200；`file://` 本地模式仍可用。
3. 桌面端：登录成功、对话真实往返、401 提示重登；`swift build` 成功。
4. M1 运行面：旧 sidecar 进程清空、plist 有备份；7788 由新服务端监听；4100/4102 与 2017 零接触。
5. 三扫描零命中；`pytest` 全绿；真实提交；工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-02

### 结果摘要

（执行后填写）

### 执行明细

（执行后填写：A–G 各步结果）

### 验收自检

（执行后填写：对照验收标准逐条勾选）
