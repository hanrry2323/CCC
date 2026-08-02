# 任务书 K · 7788 对话口账号密码鉴权（窗口 1：sidecar + 前端）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 1 即可。  
> 老板拍板（2026-08-02）：7788 对话口必须账号密码登录，**禁止 ccc/ccc 弱口令，禁止任何默认弱口令**。

## 0. 先读

1. `CLAUDE.md`
2. `scripts/ccc-agent-sidecar.py` 现有鉴权（`_auth_enforced` / `_check_agent_auth` / `_effective_token`，约 212–260 行、1217 行附近）
3. `scripts/chat_server/frontend/js/auth.js`（A3 登录门，对话壳目前跳过）与 `api.js`（`_fetchAgent` / `ccc_agent_token`）
4. `docs/dispatch/2026-08-01-http-chat-optimization-review.md`（§安全）

## 1. 任务目标

1. **账号密码配置（无默认）**：sidecar 新增登录凭证配置（如 `CCC_AGENT_AUTH_USER`/`CCC_AGENT_AUTH_PASS` 或 `~/.ccc/agent-auth.json` 600 权限），**未配置 → 拒绝登录并明确提示「未配置登录凭证」**，绝不回退 ccc/ccc
2. **登录端点**：`POST /api/auth/agent-login`（账号密码 → 会话 token，内存 TTL，如 1h）；`GET /api/auth/agent-session` 探活；登出吊销
3. **请求校验**：`/api/chat` 等对话接口要求 Bearer 会话 token；无/错 → 401
4. **前端登录门**：对话壳（7788）启用登录门——复用 A3 `#login-view` 或对话壳专用登录视图；登录换 token 存 sessionStorage；401 → 引导重登；登出按钮
5. **凭证比较**：`hmac.compare_digest` 常量时间比较；token 强随机；不落 localStorage

## 2. 允许范围

- `scripts/ccc-agent-sidecar.py`（鉴权相关）、`scripts/chat_server/frontend/js/auth.js`、`api.js`（agent 头/401 处理）、登录相关 CSS/HTML、相关测试（`scripts/tests/test_web_*` 或新增 sidecar 鉴权测试）

## 3. 红线（禁止）

- **无任何默认弱口令**（含 ccc/ccc、空密码）；密码/凭据不入库、不 commit
- Hub 服务端鉴权（`chat_server/auth.py`）不动；`routers/*.py` 不动
- **Desktop 直连 7788 的链路不能断**——本窗口改服务端与前端，Desktop 侧归窗口 2；若切换后有兼容窗口（如旧 token 文件临时兼容），必须在报告中说明
- 4000/4100 relay 相关、DRY_RUN、产线启动；提交 main 禁止

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「凭证配置方案（含未配置时的行为）+ 登录端点契约 + 前端登录门改动面 + 与窗口 2 的衔接点」，**不写代码**。  
确认后实现，测试全绿再提交。

## 5. 验收标准

- 未配置凭证：登录被拒且提示明确（有测试）
- 错误密码 401、正确密码换 token 后对话可用（有测试）
- 无 token 调对话接口 401；过期 401 引导重登
- token 只进 sessionStorage；`hmac.compare_digest` 比较
- 相关测试全绿；提交在 `codex/ws-7-agent-auth` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 移交项（给窗口 2 的 Desktop 契约）
