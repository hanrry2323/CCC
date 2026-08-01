# 窗口 K · 7788 对话口账号密码鉴权（sidecar + 前端）— 完成报告

> 日期：2026-08-02 · 分支：`codex/ws-7-agent-auth`（commit `aeb6c89`）  
> 任务书：[`docs/dispatch/task-K-agent-auth-sidecar-round7.md`](task-K-agent-auth-sidecar-round7.md)  
> 格式：发现 → 动作 → 证据 → 移交项（给窗口 2 的 Desktop 契约见 §四）

---

## 一、发现

1. **7788 裸奔**：plist `CCC_AGENT_AUTH=0` + `CCC_AGENT_HOST=0.0.0.0`，内网任何人打开 7788 即可免密对话；且对话壳 SPA 的看板/运维/项目列表走 sidecar Hub 反代（`hub_api_proxy`），转发用 sidecar 自己的 Hub 会话——**未鉴权 LAN 用户可借 sidecar 的 Hub 权限读写看板**（`docs/dispatch/2026-08-01-http-chat-optimization-review.md` §安全）。
2. **鉴权是共享密钥**：`_check_agent_auth` 只认 `CCC_AGENT_TOKEN`/`~/.ccc/agent-token`，无账号密码概念；前端对话壳**跳过** A3 登录门（`auth.js ensureAuthenticated` 对 dialogue shell 直接放行）。
3. **无默认弱口令缺失**：无账号密码配置通道、无「未配置」的明确拒绝路径。

## 二、动作

### 后端（`scripts/`）
1. **新增 `scripts/_agent_auth.py`**（纯逻辑模块，sidecar 与测试共用）：
   - 凭证（**无默认**）：`CCC_AGENT_AUTH_USER/PASS` env 优先，其次 `~/.ccc/agent-auth.json`（0600，`CCC_AGENT_AUTH_FILE` 可覆盖）；**两者都必须非空才算已配置**，否则 `None` → 登录 503「未配置登录凭证」。
   - `verify_credentials`：`hmac.compare_digest` 常量时间比较。
   - 会话：内存 opaque token（`secrets.token_urlsafe(32)`，TTL `CCC_AGENT_SESSION_TTL` 默认 3600s，过期清扫，重启失效，不入库）。
   - 登录限速：IP 滑动窗口 20 次/60s → 429（镜像 `chat_server/auth.py`；仅 `CCC_TRUST_PROXY=1` 信任 XFF）。
   - `authorize_agent_request(auth, x_token, legacy)`：会话 token → `"session"`；旧共享密钥（Bearer 或 `X-CCC-Agent-Token`）→ `"legacy"`（兼容窗口）；否则 `None`。
   - `AGENT_AUTH_ROUTER`：`POST /api/auth/agent-login`、`GET /api/auth/agent-session`、`POST /api/auth/agent-logout`。
2. **`ccc-agent-sidecar.py`**：
   - `app.include_router(AGENT_AUTH_ROUTER)` 于 catch-all 反代**之前**注册（路由顺序先匹配，`/api/auth/agent-*` 不被兜底转发 Hub）。
   - `_check_agent_auth` 改走 `authorize_agent_request`（会话 token 优先，legacy 兼容）；删旧 503「CCC_AGENT_TOKEN unset」分支 → 一律 401。
   - **`hub_api_proxy` 加门**（全端口）：未登录 LAN 用户不能借 sidecar 的 Hub 会话读写看板/运维/项目列表（用户已确认）。
   - `_hub_proxy_skip` 加 `auth/`；`/health` 加 `auth_configured`。
3. **前端（`scripts/chat_server/frontend/`）**：
   - 新增 `js/agentAuth.js`：对话壳登录门。token **只进 sessionStorage**（key `ccc_agent_session`）；`agentLogin/agentLogout/probeAgentSession`；`ensureAgentAuthenticated` 按 `/health` 的 `auth_required`/`auth_configured` 分流（sidecar 不可达 → 放行交断连横幅；未配置 → 登录门顶部明确提示）。
   - `app.js`：boot 按 shell 分支——dialogue 走 agentAuth，Hub 走 A3 auth.js。
   - `api.js`：`_agentHeaders` 改发会话 token（删旧 `ccc_agent_token` localStorage 读取）；`_fetchAgent`/`_fetchWithAuth` 401 → `ccc-agent-auth-required` → 弹登录门引导重登；dialogue shell 的 Hub 代理请求带 agent 会话 token。
   - `index.html`：登录视图标题/提示加 id，供对话壳改文案。
4. **测试**：新增 `scripts/tests/test_web_agent_auth.py`（18 例）；`scripts/tests/conftest.py` 补建 `SCRIPTS/.ccc/phases`（既有 cwd 污染修复——`test_audit_role` 等模块级 `os.chdir(scripts)` 不还原，与窗口 K 无关，但阻塞全量绿）。

## 三、证据

- **新测试**：`pytest scripts/tests/test_web_agent_auth.py -v` → **18 passed**（未配置 503 / 错密码 401 / 换 token 后授权 / 无·错·过期 token 401 / logout 吊销 / 限速 429 / `authorize_agent_request` session·legacy·None / 凭证 env>文件）。
- **全量**：`pytest tests/scripts/ scripts/tests/` → **1472 passed, 2 skipped**（修复 conftest 前 1 处既有 cwd 污染失败）。
- **ruff**：窗口 K 涉及 4 个 Python 文件全过（全仓既有 35 处违规均在未改动文件，未越界清理）。
- **`scripts/ccc-self-check.sh`**：自检全过（编译 / 注入防护 / 端口 / VERSION / plist / dual-host）。
- **真实 app 布线冒烟**（import sidecar 模块 + TestClient，不起产线 7788）：`/health` auth_required/auth_configured ✓；错密码 401 ✓；换 token ✓；无 token `/api/chat` 401 / 带 token 过门进校验 400 ✓；反代 `/api/projects` 无 token 401 / 带 token 200 ✓；`shell-config` 开放 ✓；`outbox` 无 token 401 ✓；logout 后 session 401 ✓；**未配置 → 503「未配置登录凭证」** ✓。

## 四、移交项（给窗口 2 · Desktop 契约）

窗口 2 依 `task-L-agent-auth-desktop-round7.md` 实现 Desktop 账号密码登录，契约如下：

| 项 | 契约 |
|----|------|
| 登录 | `POST /api/auth/agent-login` body JSON `{"user","password"}` → `200 {token, role:"operator", expires_in}`；401 错凭据；**503 未配置**（detail 含「未配置登录凭证」） |
| 请求带 token | 对话/健康类请求 `Authorization: Bearer <session>`：`/api/chat`、`/warm`、`/api/session/drop`、`/api/session/compact`、`/api/outbox/flush`（7788 SPA 反代也已全端口加门，Desktop 不走反代，不受影响） |
| 探活 / 登出 | `GET /api/auth/agent-session`（Bearer 有效 200/无效 401）；`POST /api/auth/agent-logout`（吊销，幂等） |
| 401 处理 | 重取一次（有界）→ 仍失败报清晰错误引导重配；**不要静默** |
| 凭证配置 | 服务端：env `CCC_AGENT_AUTH_USER/PASS` 或 `~/.ccc/agent-auth.json`（0600）。**无默认弱口令，未配置即拒绝登录** |
| **兼容窗口** | 旧共享密钥（`CCC_AGENT_TOKEN`/`~/.ccc/agent-token`，Bearer 或 `X-CCC-Agent-Token`）**仍被接受**——Desktop 现链路（`applyAgentAuth`）不断。**窗口 2 迁移 Desktop 到会话 token 后，移除 `authorize_agent_request` 的 legacy 分支为后续项**（删 legacy 参数 + `_effective_token` 兼容 + `X-CCC-Agent-Token` 接受） |
| 部署序（窗口外/产线不动） | 配凭证 → plist `CCC_AGENT_AUTH=1` → 重启 sidecar。web 登录门经 `/health.auth_required` 自动生效。TTL 1h 过期会弹登录门引导重登（凭据不持久化，属设计内；嫌烦可调 `CCC_AGENT_SESSION_TTL`） |
