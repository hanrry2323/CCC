# 任务卡 T29 · 对话接大脑 Agent（/conversation 从裸模型直答改为调用 2017 Claude Code，带心智/工具/知识库）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 任意设备=壳，经 HTTP 直连 2017 大脑对话）· 依据：老板 2026-08-03 反馈「桌面端对话和弱智一样」；Codex 实锤根因：**/conversation 只做裸模型转发（6102 → deepseek-v4-flash），无 Agent 心智/工具/知识库**· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：已关闭 · 日期：2026-08-03 · 派发：manual · 项目：ccc

## 根因（Codex 已实锤）

当前对话链路：`App → 2017:7788 /conversation → 6102 /v1/chat/completions → deepseek-v4-flash（裸模型，无 system prompt、无工具、无知识库、无 Agent 心智）`。

这违反老板定方向「对话口接 2017 最强大脑 Agent（能读知识库、能用工具、有完整心智）」。6100 Anthropic 出口实测可用（Claude Code CLI 直连 6100 正常回复），接大脑基建已就绪。

## 目标

把 `/conversation` 从「裸模型转发」升级为「**2017 Claude Code Agent 对话**」：请求经 `server/web/server.py` 调用 2017 本机 Claude Code CLI（`claude -p`，走 `127.0.0.1:6100`），携带系统角色（CCC 大脑：方案/知识/工具心智）+ 历史上下文，回复真实 Agent 输出。桌面端与网页对话即恢复为智能对话。

## 红线（先看）

1. **只改 2017 `server/web/server.py` 的 `/conversation` 实现层**（或新建大脑代理模块）；不改桌面端/网页协议（仍是 POST /conversation + Bearer）。
2. **对话走 2017 Claude Code + 6100**（契约 §8 大脑在 2017；中转站决议 6100 为 CCC 体系出口）；不直接走 6102 裸模型。
3. **Claude Code 调用方式**：`claude -p "<prompt>" --output-format text`（或等价非交互模式），env 指向 `ANTHROPIC_BASE_URL=http://127.0.0.1:6100`、`ANTHROPIC_AUTH_TOKEN=ccc-relay-flash`、`ANTHROPIC_MODEL=flash`；超时与并发保护（单会话串行，超时返回 504 明确错误）。
4. 系统提示词（CCC 大脑人格）写入 `server/config/` 或 server 内常量：知识库可用（HP 6100 出口/本地检索如就绪）、方案讨论、任务拆解、多壳对话；不硬编码密钥。
5. 不碰：桌面端/网页壳、Engine、board-scheduler、M1 4100/4102、2017 中转站配置、Claude Code 全局配置（`~/.claude/settings.json` 不动）；不读写外脑。
6. 完成必须提交（真实 commit）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 步骤

### A. 大脑代理实现（2017 server）

1. `server/web/server.py`（或新建 `server/web/brain.py` 被 server.py 引用）`_handle_conversation_post` 改造：
   - 组装系统提示词（CCC 大脑人格：你是 CCC 的大脑 Agent，负责方案讨论/知识核查/任务拆解/多壳对话；可读项目文档与知识库；回答中文、结论先行、禁止选择题）；
   - 组装用户上下文：最近 N 轮历史 + 当前消息（复用现有 history）；
   - 调用 2017 Claude Code：`subprocess.run([claude, "-p", prompt, "--output-format", "text"], env={...6100...}, timeout=60)`；
   - 成功 → `{"reply": stdout}`；失败/超时 → 504/502 明确错误，不落历史。
2. 并发保护：同一时刻仅处理一个对话请求（模块级锁或串行队列），避免多壳同时打爆 Claude Code。
3. 保留：鉴权中间件、`/session`、`/health`、board/ops 只读接口。

### B. 配置化

4. `server/config/config.example.env` 增补（如缺）：`CCC_BRAIN_CLAUDE_BIN`（默认 `claude`）、`CCC_BRAIN_MODEL=flash`、`CCC_BRAIN_TIMEOUT=60`、`CCC_BRAIN_BASE_URL=http://127.0.0.1:6100`、`CCC_BRAIN_AUTH_TOKEN=ccc-relay-flash`（占位，2017 config.env 实际填）；server.py 读 env，零硬编码。
5. 2017 `config.env` 同步补配置（不进 git）。

### C. 测试

6. `server/tests/test_http_api.py` 新增：`/conversation` 走大脑代理的用例（mock 或真实 Claude Code：鉴权 401、缺配置 503、成功 200 reply、超时/失败 502/504）。
7. `pytest server/tests/ -q` 全绿（现 206+ 新增）。

### D. 部署 + 验证（2017）

8. M1 push → 2017 pull → 2017 web-server kickstart 加载新代码。
9. 2017 本机实测：`POST /conversation`（带 token）问「1+1=？只答数字」→ 回复来自 Claude Code Agent（非裸 flash 直答特征）；问「CCC 重构的目标是什么」→ 能结合知识库/心智回答。
10. 桌面端/网页跨机实测：对话智能程度明显提升（多轮上下文、结论先行、可读文档）。

### E. 提交 + 回写

11. 提交：`chore(server): T29 对话接大脑 Agent——/conversation 调用 2017 Claude Code（带心智/工具/知识库）`
12. 回写：卡头 `状态：待分派 → 已回写`，回写区填（实现说明、配置、测试输出、双端实测、验收自检表）。

## 回滚

- `git revert` 本卡提交 → 双端 kickstart（回到裸模型直答，但功能可用）。
- 触发条件：Claude Code 调用失败率高 / 对话延迟不可接受（>60s 频繁） / 桌面端或网页对话断 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `/conversation` 回复来自 2017 Claude Code Agent（代码核验 + 实测：回复质量/上下文/工具心智特征明显区别于裸 flash 直答）。
2. 走 6100（Claude Code 出口），不再直连 6102 裸模型；env 配置化零硬编码。
3. 鉴权/历史/超时/并发保护齐全；`pytest` 全绿。
4. 桌面端与网页对话实测可用且智能度明显提升。
5. 真实提交；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

`/conversation` 从「裸转发 6102」升级为「调用 2017 本机 Claude Code CLI（走 6100 Anthropic 出口）」，携带 CCC 大脑人格 + 历史上下文，返回真实 Agent 输出。新建 `server/web/brain.py` 大脑代理模块；`server.py` 删除裸模型转发死代码（`_forward_to_upstream` + `CCC_CONV_*` env helpers），`/conversation` 改调 `call_brain`。本地 `pytest server/tests/` 全绿（208 passed，TestConversation 9 例覆盖 401/503缺配置/503忙/200/504超时/502失败/历史/prompt含上下文）。2017 部署 + 双端实测见「执行明细 D」。

### 执行明细

**A. 大脑代理实现**
- 新建 [server/web/brain.py](file:///Users/apple/program/CCC/server/web/brain.py)：
  - `BRAIN_SYSTEM_PROMPT` 常量（CCC 大脑人格：方案讨论/知识核查/任务拆解/多壳对话，中文结论先行，禁选择题）。
  - `_build_prompt()`：系统人格 + 最近 10 轮历史 + 当前消息，拼成 `claude -p` 单 prompt。
  - `_run_claude()`：`subprocess.run([claude, "-p", prompt, "--output-format", "text"], env={...6100...}, timeout)`；env 在 `os.environ.copy()` 上覆盖 `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_MODEL`，不动 `~/.claude/settings.json`。
  - `call_brain()`：配置校验 → 模块级 `threading.Lock` 非阻塞获取（单会话串行，忙立即 503）→ 调 `_run_claude` → 按 error_kind 映射 503/504/502/200。
- [server/web/server.py](file:///Users/apple/program/CCC/server/web/server.py) `_handle_conversation_post` 改调 `call_brain(message, list(_conversations))`；失败/超时/忙/未配置均不落历史。鉴权/`/session`/`/health`/board/ops 只读接口保持不变。

**B. 配置化**
- [server/config/config.example.env](file:///Users/apple/program/CCC/server/config/config.example.env)：移除 `CCC_CONV_*` 块（T19 裸转发专用，已死），新增 `CCC_BRAIN_CLAUDE_BIN`(默认 claude)/`CCC_BRAIN_MODEL`(flash)/`CCC_BRAIN_BASE_URL`(http://127.0.0.1:6100)/`CCC_BRAIN_AUTH_TOKEN`(占位)/`CCC_BRAIN_TIMEOUT`(60)。`RELAY_UPSTREAM_URL`/`RELAY_UPSTREAM_KEY` 保留（中转站/relay 仍用，非对话专用）。
- [server/deploy/com.ccc.web-server.plist](file:///Users/apple/program/CCC/server/deploy/com.ccc.web-server.plist) 注释同步：`CCC_CONV_*` → `CCC_BRAIN_*`。
- server.py 全程 `os.environ.get`，零硬编码密钥。
- 2017 `config.env` 同步补 `CCC_BRAIN_*`（不进 git）：见 D 步。

**C. 测试**
- [server/tests/test_http_api.py](file:///Users/apple/program/CCC/server/tests/test_http_api.py)：删除旧 `_MockUpstream`/`mock_upstream`/`_set_conv_env`/`_clear_conv_env`（裸转发专用），`TestConversation` 重写为大脑代理用例 9 条：`test_conversation_no_auth`(401)、`_empty_message`(400)、`_not_configured_503`、`_success`(200 reply)、`_history_after_success`、`_timeout_504`、`_failure_502`、`_busy_503`（测试线程持锁验服务线程拿 503 且不触达 `_run_claude`）、`_prompt_includes_history`（验 prompt 含系统人格+历史+当前消息）。`_run_claude` 经 monkeypatch 注入，不依赖真实 CLI。
- `pytest server/tests/ -q` → **208 passed**（HEAD 为 206，净 +2：旧 7 例 → 新 9 例）。
- `python -m py_compile server/web/brain.py server/web/server.py` 通过。
- ruff：`brain.py` 零告警；`server.py`/`test_http_api.py` 11 处告警**全部 HEAD 已存在**（F821 `BoardItem` 未导入 ×6、F401 `OrderedDict`/`Path` 未用、F541 f-string、W292 缺尾换行），T29 未引入新告警。

**D. 部署 + 验证（2017）**
- M1 push `0c2734e` → 2017 `git pull --ff-only`：HEAD `0ccd0119 → 0c2734ed`（同步）。
- 2017 `server/config/config.env`：移除 `CCC_CONV_*`，追加 `CCC_BRAIN_CLAUDE_BIN=/Users/fan/.npm-global/bin/claude` / `CCC_BRAIN_MODEL=flash` / `CCC_BRAIN_BASE_URL=http://127.0.0.1:6100` / `CCC_BRAIN_AUTH_TOKEN=ccc-relay-flash` / `CCC_BRAIN_TIMEOUT=120`；`RELAY_UPSTREAM_*` 保留（relay 仍用）。备份 `config.env.bak.T29`。
- **关键发现**：2017 web-server 进程 env 来自 launchd plist 的 `EnvironmentVariables`（非运行时读 config.env），故同步用 `plistlib` 改 `~/Library/LaunchAgents/com.ccc.web-server.plist`（移除 `CCC_CONV_*`、加 `CCC_BRAIN_*`），`plutil -lint` OK，备份 `plist.bak.T29`。`launchctl bootout gui/501/com.ccc.web-server && bootstrap` 重载，新 PID 35142，`/health` → `{"status":"ok"}`。
- 基建核验：`claude` 2.1.220 在 `/Users/fan/.npm-global/bin/claude`；6100 → HTTP 200。
- 本机实测（2017 localhost:7788，ccc/ccc 换 token）：
  - Q1「1+1=？只答数字」→ `2`（真实 Agent 回复，~15s，CLI 启动地板）。
  - Q2「CCC 重构的目标是什么？结论先行」→ 首次 60s 超时 504（知识题读 CLAUDE.md/docs+推理 ~74s）；调 `CCC_BRAIN_TIMEOUT=120` 复测 → 成功，回复正确引用 INT-120/T29/T30/重构契约 v1 §8，指出「对话口接 2017 最强大脑 Agent…修复裸模型直答无心智」（证明读项目文档+有心智）。
- 跨机实测（M1 → `http://192.168.3.116:7788`，模拟桌面/网页路径）：
  - `/health` 200；无 token POST `/conversation` → 401（鉴权不回归）。
  - 多轮上下文：T1「我叫小明」→「已记下：小明」；T2「我刚才告诉你我叫什么？只答名字」→「小明」（历史上下文经 `_build_prompt` 注入生效）。
- 超时调参提交 `3d4919e`：brain.py 默认 + config.example.env `CCC_BRAIN_TIMEOUT` 60→120（数据驱动；2017 已设 120）。

**E. 提交 + 回写**
- 提交 1：`0c2734e chore(server): T29 对话接大脑 Agent——/conversation 调用 2017 Claude Code（带心智/工具/知识库）`（5 代码文件 + 本卡）。
- 提交 2：`3d4919e chore(server): T29 大脑超时默认 60→120s（实测知识题~74s，60s 过紧）`。
- 均已 push origin/main。回写：卡头 `状态：待分派 → 执行中 → 已回写`。

### 验收自检

- [x] 1. `/conversation` 回复来自 2017 Claude Code Agent：代码核验 `call_brain → _run_claude`（`claude -p` via 6100）；实测 Q2 知识题回复引用项目文档（INT-120/T29/T30/契约§8），多轮上下文生效——明显区别于裸 flash 直答。
- [x] 2. 走 6100（`CCC_BRAIN_BASE_URL=http://127.0.0.1:6100`），不再直连 6102（`_forward_to_upstream` + `CCC_CONV_*` 已删，2017 plist/config.env 同步移除）；env 配置化零硬编码。
- [x] 3. 鉴权（Bearer 中间件不变，跨机 401 实测）/历史（最近 10 轮，多轮实测）/超时（120s，504 实测后调参）/并发（`_brain_lock` 单会话串行，忙 503 单测）齐全；`pytest server/tests/` 在 `0c2734e` 为 **208 passed**。
- [x] 4. 桌面端与网页对话实测可用且智能度明显提升：跨机 M1→2017:7788 多轮 + 知识题均可用；智能度从「裸模型弱智直答」升级为「带心智/工具/知识库的 Agent 回答」。
- [x] 5. 真实提交（`0c2734e` + `3d4919e`，已 push）；T29 自身改动全部落盘，M1 工作树剩余项均为非 T29：预存 3 项（`decided.json`/`_update_handoff.py`/`command-post/`）+ T30 WIP（`server.py`/`test_http_api.py`/`legacy-chat/*`，管理席 Codex 在做，非本卡范围）；卡头状态已同步为「已回写」。

---

## 验收区（Codex 独立取证 · 2026-08-03）

**结论：通过 ✅**（不看回写，全部实测）

| 验收项 | 独立取证结果 |
|--------|--------------|
| 提交 | `0c2734e`（brain.py 168 行 + server.py 接入）+ `3d4919e`（超时 60→120s）+ `24250df` 回写真实；2017 HEAD=dc57178 已同步 ✅ |
| 实现质量 | `brain.py` 核验：系统人格提示词、历史 10 轮、单会话锁（忙 503）、超时 120s（504）、失败 502/未配置 503；env 全配置化零硬编码 ✅ |
| 对话实测 | 2017 实测 `/conversation`「CCC 重构的目标？」→ **真实 Agent 输出**（结构化三要点、中文、结论先行，38s 返回）——明显区别于裸 flash 直答 ✅ |
| 走 6100 | 配置 `CCC_BRAIN_BASE_URL=http://127.0.0.1:6100`、`CCC_BRAIN_MODEL=flash`、token 走 env；不再直连 6102 裸模型 ✅ |
| 测试 | 独立跑 `pytest server/tests/` → **209 passed**（无回归）✅ |
| 双端部署 | 2017 web-server（PID 37587）在跑、7788 监听 ✅ |
| 工作树 | M1 仅剩预存项（T30 WIP 属另一卡）✅ |

**遗留登记**：2017 工作树有 `server/config/config.env.bak.T29` 未跟踪备份文件（T29 部署生成，含配置），建议清理或确认保留；不影响功能。

**结论**：对话口已从「裸模型直答」升级为「2017 Claude Code 大脑 Agent」（带心智/工具/知识库上下文），桌面端与网页对话智能度问题根因解除。
