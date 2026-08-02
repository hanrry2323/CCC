# 窗口 M · Desktop ↔ sidecar Agent 登录契约校准 + 联调 — 完成报告

> 日期：2026-08-02 · 分支：`codex/ws-6-desktop-agent-auth`（校准 commit `a41251e`）+ main 合入（`d759f04` K + `d4450e2` L）  
> 任务书：[`docs/dispatch/task-M-agent-auth-calibration.md`](task-M-agent-auth-calibration.md)  
> 前置：窗口 K `codex/ws-7-agent-auth@c030b6a` · 窗口 L `codex/ws-6-desktop-agent-auth@090b0c8`  
> 格式：发现 → 动作 → 证据 → 移交项（校准与联调记录见 §五）

---

## 一、发现

1. **两端契约对不上，配置正确账号密码也 401**：

   | 项 | sidecar（K，已实现+已测，权威） | Desktop（L，校准前） | 结论 |
   |----|------|------|------|
   | 请求体 | `{"user","password"}` | `{"username","password"}` | 不匹配 → 必 401 |
   | 响应 | `{token, role, expires_in}` | 解码 `expires_at`/`ttl_s` | expires_in 未解析 → 过期跟踪失效 |

2. **report-K §四 契约未回流到 Desktop**：L 按旧 task-K 草稿实现，L 已预告「report-K 回后校准」但未执行。本窗口补上。

## 二、动作

### Desktop 契约校准（`desktop/Sources/CCCDesktop/`，窗口 L 分支上，commit `a41251e`）

1. **`APIClient.swift` `performAgentLoginInner`**：请求体 key `username → user`（对齐 report-K §四）。
2. **`APIClient.swift` 会话过期解析**：`expires_at`(ISO 串) → `expires_in`(相对秒)；`store(expiresAt: obj.expires_in.map { Date().addingTimeInterval(...) })`，无则 nil → 靠 401 重登兜底（语义不变）。
3. **`AgentTokenState.swift` `AgentLoginResponse`**：`expires_at`/`ttl_s` → `expires_in: Int?`；保留 `scheme` 可选（响应多出的 `role` 由 Decodable 自动忽略）。

### 测试校准（`desktop/Tests/CCCDesktopTests/AgentLoginTests.swift`，8 用例语义不变）

- mock 登录响应 `{token, role, expires_in}`（原来 `{token, expires_at, ttl_s, scheme}`）；删 ISO formatter。
- `testAgentLoginExchangedForBearer` 断言升级：解析登录 body 为 JSON，`user == "alice"`、`password == "s3cret"`、**`username` 必须为 nil**（直接锁死契约 key）。

## 三、证据

- **Desktop 全量**：`swift test` → **126 passed, 0 failures**（含 AgentLoginTests 8 用例全绿）。校准后在 L worktree 与合入后的 main 各跑一遍，均全绿。
- **sidecar 无回归**：`pytest scripts/tests/test_web_agent_auth.py` → **18 passed**（K worktree 与合入后 main 均过）。
- **联调冒烟**（不起产线 7788；TestClient 挂真实 sidecar app + 测试凭证）：**11/11 PASS**，见 §五。

## 四、合入与清理

- 两分支 merge-base 均为 main HEAD（`cac1fb6`），与 main 无冲突。
- 合入序：`merge: 窗口K … (aeb6c89)` → `d759f04`；`merge: 窗口L+校准 … (090b0c8+a41251e)` → `d4450e2`。
- main 工作树残留的 Desktop 未提交副本（M/?? 文件，与 090b0c8 逐字节一致）已清理，未混入合入；合入后 Desktop 文件为校准版（`user` + `expires_in`），无残留 `username`/`expires_at`/`ttl_s`（Hub token 的 `expires_at` 属 Hub 契约，非 agent 路径）。

## 五、校准与联调记录（交接）

真实 sidecar app（import `scripts/ccc-agent-sidecar.py` + TestClient，测试凭证 `smoke-user`/`smoke-pass-1`，不起产线）：

| # | 用例 | 结果 |
|---|------|------|
| 1 | `POST /api/auth/agent-login` `{"user","password"}` → 200 `{token, role:"operator", expires_in:3600}` | PASS |
| 2 | body keys 恰为 `{token, role, expires_in}`；expires_in int>0 | PASS |
| 3 | 错 key `{"username",…}` → 401（校准前必失败点） | PASS |
| 4 | 错密码 → 401 | PASS |
| 5 | `GET /api/auth/agent-session` 带 Bearer → 200；无 token → 401 | PASS |
| 6 | 门控 `POST /api/outbox/flush` 带会话 Bearer → 200 | PASS |
| 7 | legacy 共享密钥（`CCC_AGENT_TOKEN`，Bearer）→ 200（Desktop 降级兼容窗口） | PASS |
| 8 | 无任何 token → 401 | PASS |

Desktop 侧 4 项联调（URLProtocol 行为锁 8 用例覆盖）：带凭证 → Bearer 会话 token（`testAgentLoginExchangedForBearer`）；错密码 → 明确报错不降级（`testCredsConfiguredLogin401ThrowsNotSilent`）；未配置 → 降级共享密钥（`testNoCredsFallsBackToSharedSecret`）；401 → 清 token 重登一次有界（`test401OnceThenReloginSucceeds` / `test401TwiceThrowsNoInfiniteLoop`）。

**移交项**：
- 部署序（产线不动，本窗口未触碰）：配凭证（env `CCC_AGENT_AUTH_USER/PASS` 或 `~/.ccc/agent-auth.json` 0600）→ plist `CCC_AGENT_AUTH=1` → 重启 sidecar；web 登录门经 `/health.auth_required` 自动生效。
- **后续项（不在本窗口）**：Desktop 迁移完成且兼容窗口结束后，移除 `authorize_agent_request` 的 legacy 分支（legacy 参数 + `_effective_token` 兼容 + `X-CCC-Agent-Token` 接受）。
- 契约 SSOT：`scripts/_agent_auth.py` + 本报告 §五；Desktop 侧 `AgentLoginResponse`/`performAgentLoginInner` 已对齐。
