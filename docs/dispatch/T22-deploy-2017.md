# 任务卡 T22 · 2017 代码流转 + 新栈部署（2017 单端落地 · 中转站走 6100/6102）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 运行拓扑终态：2017 单端）/ §9 红线 · 依据：老板 2026-08-02 中转站双轨决议（M1 4100/4102 长期保留；2017 6100/6102 CCC 专用，使用方仅 2017 Claude Code + OpenCode，均 flash 档位）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：已回写 · 日期：2026-08-03
> 放行确认：老板 2026-08-02「按照决议修改下一步指令」→ 即启动 2017 部署；M1 侧服务（web-server 7788 等）本卡**不停**，双轨并行验证，停用时机另定。

## 目标

把新栈 `server/` 从 M1 经 GitHub 流转到 Mac2017（`/Users/fan/program/CCC`），配置并常驻运行 **web-server（HTTP API + 看板 + 对话）**、**Engine**、**board-scheduler**，使 2017 成为 CCC 唯一运行端（契约 §8 终态）。**中转站按决议走 2017 本地 6100/6102（flash 档位）**；M1 4100/4102 与 M1 运行面零接触。

## 红线（先看）

1. **中转站按双轨决议**：2017 新服务端对话上游只指 `127.0.0.1:6102`（OpenAI chat / flash，与决议一致）；2017 侧 Claude Code/OpenCode 已有配置不动；**M1 4100/4102（PID 63542）与 M1 上 web-server（7788，PID 63928）零接触**。
2. **2017 旧栈遗留处理须先备份**：2017 仓本地未提交改动（`scripts/_product_fanout.py`、`scripts/_product_session.py`、`scripts/engine/gates.py`、`.ccc/agent-mind/` 未跟踪项）先备份到 `~/.ccc/backup-20260802-pre-deploy/`，再清理，禁止无备份删除。
3. **2017 旧 launchd plist 必须替换而非叠加**：`~/Library/LaunchAgents/` 下旧 `com.ccc.engine.plist`（指向 `scripts/ccc-engine.py`）与 `com.ccc.board.plist`/`com.ccc.chat-server.plist` 已 bootout（T18）；部署新栈前先备份旧 plist 并确认卸载，再装新 plist（同名 label 冲突会报错）。
4. **2017 副本只 pull 不手改**（§8 代码流转）：配置（config.env/executors.json/plist 变量替换）只写 `server/config/` 下 gitignore 覆盖或 `~/Library/LaunchAgents/`，不手改仓内受版本控制文件。
5. 零硬编码：端口/路径/账号/上游地址一律配置化；密钥零落 git；不读写外脑；完成必须提交（真实 commit）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 范围

- 代码流转：M1 `main` push → GitHub → 2017 `git pull`（先备份并清理 2017 本地旧栈改动）。
- 2017 配置：`server/config/config.env`（从 example 复制：`PYTHON_BIN=/Users/fan/program/CCC/.venv-hub/bin/python`、`WEB_PORT=7788`、`WEB_HOST=0.0.0.0`、`RELAY_UPSTREAM_URL=http://127.0.0.1:6102`、账号/哈希按既有 `ccc/ccc`、`CLUSTER_TARGETS` 含 7788/6100/6102 等）、`executors.json`（契约 §7 五角色）。
- launchd 部署（替换变量后装到 `~/Library/LaunchAgents/`）：`com.ccc.web-server`（7788）、`com.ccc.engine`（新栈入口 `server/engine/main.py`）、`com.ccc.board-scheduler`。
- 验证：web 接口全链路（health/session/conversation/board/*/ops/summary）、engine `--once`、scheduler `--once`、kb selftest（如数据就绪）、2017 测试冒烟（可选跑 `pytest server/tests/` 需依赖就绪）。
- 不动：M1 一切；2017 中转站（6100/6102）与 2017 Claude Code/OpenCode 配置；2017 业务仓（qb 等）。

## 步骤

### A. 代码流转（M1 → GitHub → 2017）

1. M1：确认 `git status` 干净（仅预存 2 项）→ `git push origin main`。
2. 2017：备份本地旧栈改动：`mkdir -p ~/.ccc/backup-20260802-pre-deploy && cp scripts/_product_fanout.py scripts/_product_session.py scripts/engine/gates.py ~/.ccc/backup-20260802-pre-deploy/`；`.ccc/agent-mind/` 未跟踪项同理备份。
3. 2017：清理本地改动（已备份）：`git checkout -- scripts/` + 移除已备份的未跟踪项 → `git status` 干净。
4. 2017：`git pull origin main` → 确认 `server/` 目录出现、`docs/archive/legacy-retired-2026-08-02/` 到位、`git log` 含 T21 提交。

### B. 2017 配置（只写配置层，不手改受版本控制文件）

5. `cp server/config/config.example.env server/config/config.env`（config.env 确认 gitignore 覆盖，不进 git）。
6. 填配置：`PYTHON_BIN=/Users/fan/program/CCC/.venv-hub/bin/python`、`ENGINE_PORT`/`BOARD_PORT`/`WEB_PORT=7788`/`RELAY_PORT`、`WEB_HOST=0.0.0.0`、`DATA_DIR`/`LOG_DIR`（如 `~/.ccc/data`、`~/.ccc/logs`）、`RELAY_UPSTREAM_URL=http://127.0.0.1:6102`、`RELAY_UPSTREAM_KEY=ccc-relay-flash`、`CCC_WEB_USERNAME=ccc`、`CCC_WEB_PASSWORD_HASH`（与 M1 相同哈希）、`CLUSTER_TARGETS`（含 `127.0.0.1:7788,127.0.0.1:6100,127.0.0.1:6102`）、`CLUSTER_PORT_NAMES`（如 `7788=web-server,6100=relay-anthropic,6102=relay-openai`）、`EXECUTOR_REGISTRY_PATH=server/config/executors.json`。
7. `cp server/config/executors.example.json server/config/executors.json`（确认 gitignore 覆盖；内容按契约 §7 五角色）。

### C. launchd 部署（先替换旧 plist）

8. 2017 旧 plist 备份：`mkdir -p ~/.ccc/backup-20260802-pre-deploy && cp ~/Library/LaunchAgents/com.ccc.engine.plist ~/Library/LaunchAgents/com.ccc.board.plist ~/Library/LaunchAgents/com.ccc.chat-server.plist ~/.ccc/backup-20260802-pre-deploy/`。
9. 确认旧服务未加载：`launchctl list | grep ccc` → 空（T18 已 bootout）；如残留先 `launchctl bootout`。
10. 新 plist：用 `server/deploy/` 模板替换变量生成 `~/Library/LaunchAgents/com.ccc.web-server.plist`（`$PYTHON_BIN`/`$PROJECT_ROOT=/Users/fan/program/CCC`/`$LOG_DIR`/`$USERNAME=fan`，`WEB_HOST=0.0.0.0`/`WEB_PORT=7788` 走 env）、`com.ccc.engine.plist`（新栈入口）、`com.ccc.board-scheduler.plist`。
11. `launchctl bootstrap gui/$(id -u)` 三个 plist → 确认 7788 由新 web-server 监听、engine 进程在、board-scheduler 心跳在。

### D. 验证（全部必跑）

12. web 全链路（2017 本机 curl）：
    - `/health` 200；`POST /session`（ccc/ccc）换 token；
    - 带 token `/board/snapshot`/`/board/states`/`/ops/summary` 200；无 token 401；
    - `POST /conversation` 真实模型回复（经 `127.0.0.1:6102`，flash）——**验证中转站决议生效**。
13. `engine --once`（用 config.env）退出码 0、JSON 统计正常。
14. `board-scheduler --once` 正常导出。
15. 2017 侧 Claude Code / OpenCode 配置**未动**（`ANTHROPIC_BASE_URL=6100` / `baseURL=6102` 原样）。
16. M1 侧零接触：4100/4102（PID 63542）、M1 7788（PID 63928）进程未变。
17. 三扫描（S1–S4 + 密钥 + 外脑依赖）在 M1 仓对本次变更零命中。

### E. 提交 + 回写

18. M1 仓提交卡回写：`docs(dispatch): T22 回写`（如涉及配置模板修改一并提交）。
19. 回写：卡头 `状态：待分派 → 已回写`，回写区填完（真实 commit hash、2017 验证输出、验收自检表）。

## 回滚

- 代码层：2017 `git reset --hard origin/main` 前先确认无本地配置丢失；配置/plist 用 `~/.ccc/backup-20260802-pre-deploy/` 恢复。
- 服务层：`launchctl bootout` 新三个 plist → 恢复旧 plist（若需）或保持停止（2017 旧引擎本已退役）。
- M1 侧无需回滚（零接触）。
- 触发条件：对话上游 6102 冒烟失败 / web 接口不可用 / engine 无法启动 / 2017 pull 冲突无法解决 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. 2017 `server/` 已到位（pull 成功），`git status` 干净；本地旧栈改动有备份。
2. 2017 三服务常驻：7788 = 新 web-server（HTTP API + 看板 + 对话）；engine、board-scheduler 在跑。
3. 对话经 `127.0.0.1:6102`（flash）出真实回复；Claude Code/OpenCode 2017 配置未动；**M1 4100/4102 与 M1 7788 零接触（PID 对比）**。
4. 全接口冒烟（health/session/board/ops/conversation + 401）；engine/scheduler 冒烟通过。
5. 零硬编码（配置化）、无密钥进 git、M1 工作树仅剩预存 2 项；真实提交；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

2017 新栈部署完成并常驻运行。M1 `server/` 经 GitHub 流转到 Mac2017（commit b494f79，git pull fast-forward）；`server/config/config.env`（17 keys）+ `executors.json`（5 roles）按双轨决议配置（对话上游 `127.0.0.1:6102` flash）；三个 launchd 服务（web-server 7788 / engine / board-scheduler）已 bootstrap 并常驻。全链路验证通过：web 7 接口（health/session/board×3/ops/conversation，含 6102 真实模型回复 "OK"）+ 401 + engine `--once` exit 0 + scheduler 导出 29 卡。M1 零接触（4100/4102 PID 63542、7788 PID 63928 均未变）；三扫描零命中；Mac2017 Claude Code（ANTHROPIC_BASE_URL=6100）配置未动。

### 执行明细

**A. 代码流转（M1 → GitHub → 2017）**
- A.1 M1 `git status` 干净（仅预存 2 项：`.ccc/agent-mind/decided.json` + `_update_handoff.py`）。
- A.2 M1 `.gitignore` 增加 `server/config/config.env` + `server/config/executors.json`（防敏感配置进 git）；commit `b494f79` push 到 `origin/main`。
- A.3 2017 git 仓本地无未提交改动（T18 已清理）；旧 plist（`com.ccc.board.plist` / `com.ccc.chat-server.plist` / `com.ccc.engine.plist` + 2 个 .bak）已备份到 `~/.ccc/backup-20260802-pre-deploy/`（含此前备份的 `_product_fanout.py` / `_product_session.py` / `gates.py` / `agent-mind-backup/`）。
- A.4 2017 `git pull origin main` fast-forward `b1088a8c..b494f790`，`server/` 目录到位。

**B. 2017 配置（只写配置层，不手改受版本控制文件）**
- B.5 `server/config/config.env` 创建（gitignore 覆盖，不进 git）：`PYTHON_BIN=/Users/fan/program/CCC/.venv-hub/bin/python`、`WEB_PORT=7788`、`WEB_HOST=0.0.0.0`、`DATA_DIR=/Users/fan/.ccc/data`、`LOG_DIR=/Users/fan/.ccc/logs`、`RELAY_UPSTREAM_URL=http://127.0.0.1:6102`、`RELAY_UPSTREAM_KEY=ccc-relay-flash`、`CCC_CONV_MODEL_NAME=flash`、`CCC_WEB_USERNAME=ccc`、`CCC_WEB_PASSWORD_HASH=64daa44a...（sha256("ccc")）`、`CLUSTER_TARGETS=127.0.0.1:7788,127.0.0.1:6100,127.0.0.1:6102`、`CLUSTER_PORT_NAMES=7788:web-server,6100:relay-anthropic,6102:relay-openai`、`EXECUTOR_REGISTRY_PATH=server/config/executors.json`。
- B.6 `server/config/executors.json` 创建（gitignore 覆盖）：契约 §7 五角色（Trae/OpenCode/Claude Code/Codex×2）。
- B.7 `load_config` 验证：17 keys 加载成功，必填项无缺失。

**C. launchd 部署（先替换旧 plist）**
- C.8 旧 plist 备份完成（见 A.3）。
- C.9 `launchctl list | grep ccc` 空（T18 bootout 持续有效，无残留）。
- C.10 旧 plist `com.ccc.board.plist` / `com.ccc.chat-server.plist` / `com.ccc.engine.plist.bak-*` 已删除（备份保留）；新三个 plist 装到 `~/Library/LaunchAgents/`：
  - `com.ccc.web-server.plist`（`$PYTHON_BIN -m server.web.server --host 0.0.0.0 --port 7788` + 全 env 注入）
  - `com.ccc.engine.plist`（`$PYTHON_BIN -m server.engine.main --config config.env`；模板的 `$PROJECT_ROOT/$ENGINE_ENTRY` 改为模块调用）
  - `com.ccc.board-scheduler.plist`（`$PYTHON_BIN -m server.board.scheduler --watch --interval 60`）
- C.11 `launchctl bootstrap gui/501` 三个 plist → 全部 PID 分配：web-server=12021、engine=12023、board-scheduler=12025；7788 由新 web-server 监听（`lsof -iTCP:7788` 确认 PID 12021）。

**D. 验证（全部必跑）**
- D.12 web 全链路（2017 本机 curl）：
  - `/health` 200 `{"status":"ok"}`（无鉴权）
  - `POST /session` ccc/ccc → 200 + token（`63cb0463...`）
  - `GET /board/snapshot` 200（真实看板数据，T1-R 等）
  - `GET /board/states` 200 `{"待分派":1,"执行中":0,"已回写":0,"已关闭":25,"打回":3}`
  - `GET /ops/summary` 200（集群 3 节点全可达：web-server/relay-anthropic/relay-openai）
  - `GET /board/realtime` 无 token → 401 `{"error":"missing or invalid Authorization header"}`
  - `POST /conversation` 带 token → 200 `{"reply":"OK"}`（经 `127.0.0.1:6102` flash 真实回复，**中转站决议生效**）
- D.13 `engine --once` 退出码 0，JSON `{"mode":"once","scanned":0,"dispatched":0,"in_flight":0,"collected":0}`。
- D.14 `board-scheduler --once` 退出码 0，导出 29 卡 → `server/web/data/board.js`（24805 bytes）。
- D.15 2017 Claude Code 配置未动：`ANTHROPIC_BASE_URL=http://127.0.0.1:6100` 原样；6100/6102 仍活（404 = TCP 可达，路径未配）。
- D.16 M1 侧零接触：4100/4102（PID 63542 `node dist/proxy.js`）、M1 7788（PID 63928 `Python -m server.web.server`）进程未变。
- D.17 三扫描（M1 仓对本次 `.gitignore` 变更）：S1 旧状态名 / S2 旧栈名 / S3 密钥 / S4 外脑依赖 全部零命中。

**E. 提交 + 回写**
- E.18 M1 仓提交卡回写（本次 commit）。
- E.19 卡头 `状态：待分派 → 已回写`，回写区填完。

### 验收自检

对照验收标准逐条勾选：

1. ✅ 2017 `server/` 已到位（pull 成功 fast-forward b494f790），`git status` 干净；本地旧栈改动有备份（`~/.ccc/backup-20260802-pre-deploy/`）。
2. ✅ 2017 三服务常驻：7788 = 新 web-server（PID 12021，HTTP API + 看板 + 对话）；engine（PID 12023）、board-scheduler（PID 12025）在跑。
3. ✅ 对话经 `127.0.0.1:6102`（flash）出真实回复 `{"reply":"OK"}`；Claude Code 2017 配置（ANTHROPIC_BASE_URL=6100）未动；M1 4100/4102（PID 63542）与 M1 7788（PID 63928）零接触（PID 对比未变）。
4. ✅ 全接口冒烟通过（health/session/board.snapshot/board.states/ops.summary/conversation + 401）；engine `--once` exit 0；scheduler `--once` 导出 29 卡 exit 0。
5. ✅ 零硬编码（端口/路径/账号/上游地址全配置化）、无密钥进 git（config.env/executors.json gitignore 覆盖 + 三扫描零命中）、M1 工作树仅剩预存 2 项（`.ccc/agent-mind/decided.json` + `_update_handoff.py`）；真实提交（b494f79 + 本回写 commit）；卡头状态已同步（待分派 → 已回写）。
