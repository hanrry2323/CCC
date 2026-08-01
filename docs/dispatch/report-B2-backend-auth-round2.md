# 窗口 B2 · 网页鉴权整改 + 遗留收尾 — 完成报告

> 日期：2026-08-01 · 分支：`codex/ws-2-backend`（本波 4 commits，基于 round1 报告后）  
> 任务书：[`docs/dispatch/task-B2-backend-auth-round2.md`](task-B2-backend-auth-round2.md) · 第一波报告：[`report-B-backend-engine.md`](report-B-backend-engine.md)  
> 格式：发现 → 动作 → 证据 → 移交项

---

## 基线

- 现状：Hub `:7777` 所有端点统一 Basic `ccc:ccc`（`check_auth`），**读写同权**；7788 sidecar 默认无 Token；前端 SPA / Desktop / sidecar / 工具全走 Basic。
- 写端点：ops `daily-review/run`（日审 apply）、desktop `transfer`/`promote-planned`/`board-repair`/`repair-queue/claim`/`proactive-epic`/`proposals adopt`/`proposal`、board 8 个写端点。
- 调用方凭证：sidecar `_hub_auth_headers()`（Basic `ccc:ccc`）、前端 `api.js`（Basic localStorage）、工具（Basic）。

---

## 一、后端鉴权（会话 token + 写操作提权）

### 发现
「真实鉴权」缺失点：① 唯一凭据是固定 Basic `ccc:ccc`（内网已知默认，等价无鉴权）；② 读写同权——任何能进 Hub 的调用可 `apply` 日审 / 转任务 / 挪看板。

### 动作
1. **会话 token**（`chat_server/auth.py`）：内存 opaque token（`secrets.token_urlsafe`，TTL 1h，过期清扫，重启失效——非持久化凭据，不入库）。
2. **`check_auth` 双通道**：Basic（legacy → **operator** 全权兼容）或 Bearer 会话 token（token role）。legacy Basic 打 debug 日志。
3. **`require_write` 提权门**：写端点默认要求 `role=operator`；viewer token → **403**；无凭证 → **401**。
4. **token 端点**（新 `routers/auth.py`）：`POST /api/auth/token`、`POST /api/auth/logout`、`GET /api/auth/session`。
5. **可选 viewer 凭证**：`CCC_HUB_VIEWER_PASS` → `viewer:<pass>` 登录得只读 token（写 403）。未设 → 无 viewer 登录路径。
6. **提权门应用到 16 个写端点**：ops 日审 apply ×1、desktop 转任务/板务/投递 ×7、board 写 ×8。

### 证据
- 13 例鉴权测试（token 签发 / Bearer 读 / viewer 写 403 / operator 写放行 / Basic 写兼容 / 401 / 过期 / logout）全绿。
- 相关 89 例 chat_server TestClient 测试全绿（Basic=operator 兼容成立）。
- `tests/scripts/` 全量绿 · `scripts/tests/` 全量绿 · `ccc-self-check` 通过。

---

## 二、兼容过渡（明确行为）

| 调用方 | 现状凭证 | 过渡期行为 |
|--------|----------|-----------|
| Desktop / sidecar | Basic `ccc:ccc` | **operator 全权**（不破坏；`_hub_auth_headers` 不变） |
| 前端 SPA（窗口 A） | Basic localStorage | 可继续（operator）；迁移路径 = `POST /api/auth/token` → Bearer |
| 工具（ccc-hub-lens 等） | Basic | **operator 全权**（不破坏） |
| viewer token（新增可选） | `CCC_HUB_VIEWER_PASS` | **只读**；写端点 403 |

- **Basic 不设硬截止**：长期兼容过渡期；`check_auth` debug 日志标记 legacy 使用，前端后续窗口 A 换 token 流。
- 角色分离立即在代码层生效（写端点查 role==operator），机制（viewer 口令）可选启用。

---

## 三、遗留三项收尾

### 1. `_executor.py` 长 prompt 死路径 → **修**
- **发现**：`OpenCodeExecutor.execute` 长 prompt 写临时文件但命令只传固定 `message="Read attached file…"`（`prompt_file` 被 `build_opencode_run_cmd` 忽略）→ **prompt 内容丢失**。该路径仅 `opencode-pool` 使用（其 2 个测试在跑，非完全死）。
- **动作**：对齐 R-14——长 prompt `message=None` + `stdin=PIPE` + `communicate(input=prompt.encode())`；临时文件保留（审计）。短 prompt 不变。
- **证据**：`0d2cc94`；`test_executor` / `test_opencode_pool_*` 全绿。
- 结论：**修**（保留 opencode-pool，产线实际走 `opencode-runner.sh → opencode-exec.py`）。

### 2. `hygiene-python` patrol 卡 → **修**
- **发现**：卡标记查 deprecated `resolve_executor_intent`；实际执行器由 `resolve_executor_from_skill`（skill.md 默认执行器）决定。
- **动作**：`must_contain` 改 `["resolve_executor_from_skill", "python"]`。
- **证据**：`729f292`；patrol 测试绿。

### 3. 文档漂移 → **修**
- **发现**：CLAUDE.md「#/chat 已删」与 router.js 实有内联跳转路由不符；GO-LIVE / GO-LIVE-DESKTOP / hub-remote-management / README 称网页 `#/board` `#/ops`「已停更」，但 2026-07-31 已恢复（`ed46279`/`1f75fe8`）；ccc-hub-ports 称 #/chat 自动跳转（实为内联提示）。
- **动作**：6 文件 9 处表述同步（CLAUDE.md、README.md、GO-LIVE、GO-LIVE-DESKTOP、hub-remote-management、ccc-hub-ports）。
- **证据**：`8ff3814`；版本一致性 `VERSION sync OK (v0.66.1)`。

---

## 四、验证

| 项 | 结果 |
|----|------|
| `pytest tests/scripts/` | **全绿** |
| `pytest scripts/tests/` | **全绿** |
| `ruff`（本波改动文件） | 全过（存量 8 错为 UP045 版本漂移 + ops.py E401，非本波引入） |
| `ccc-self-check` | **通过**（VERSION 一致） |
| 鉴权测试 | 13 例 + 相关 89 例 TestClient 全绿 |

---

## 五、移交项（前端/窗口 A 配合接口契约）

**前端登录页 / Token 存储由窗口 A 实现**（本波只做后端）。接口契约：

1. **登录换 token**：`POST /api/auth/token`
   - 请求：Basic 凭证（operator=`ccc:ccc` 或配置账密；只读=`viewer:<CCC_HUB_VIEWER_PASS>`）
   - 响应 200：`{"token": "<opaque>", "role": "operator"|"viewer", "scheme": "bearer", "expires_at": "<ISO>", "ttl_s": 3600}`
   - 401：凭证错误（`WWW-Authenticate: Basic`）
2. **后续请求**：`Authorization: Bearer <token>`（替换 Basic；`GET/POST/PUT/DELETE` 全适用）
3. **探活**：`GET /api/auth/session`（Bearer/Basic）→ `{"valid": true, "scheme": ..., "role": ...}`；无效 → 401
4. **登出**：`POST /api/auth/logout`（Bearer）→ 吊销（幂等）
5. **权限语义**：写操作（`POST /api/ops/daily-review/run`、`/api/desktop/transfer*`、`/api/desktop/board-repair`、`/api/board/tasks/*` 等）要求 `role=operator`；viewer token → **403**。前端 UI 可据 `/api/auth/session` 的 role 隐藏/禁用写按钮。
6. **过渡**：Basic 仍全权可用；前端可逐步迁移到 token（localStorage 存 token，401 时重登）。

---

## 六、风险 / 遗留

1. **内存 token 重启失效**：非持久化凭据，可接受；若需跨重启会话由窗口 A 定持久化方案（不入库）。
2. **写门 scope**：viewer token 为新增可选，无存量调用方；Basic=operator 保证 Desktop/sidecar/工具全链不破坏。
3. **`validate_auth_config`** 的 `0.0.0.0+ccc:ccc` 拒绝不受本波影响（既有防线，未改）。
4. 本波未改 7788 sidecar 自身鉴权（`CCC_AGENT_AUTH`）；其 Basic→Hub 调用保持兼容。
