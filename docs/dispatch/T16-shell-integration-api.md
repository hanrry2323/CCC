# 任务卡 T16 · 壳对接（服务端侧）：对话/写 API + 鉴权 + 客户端指向就绪（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 拓扑：壳经 HTTP 直连、多壳锁门）· 依据：T13（只读 API）· 管理席：Codex
> 执行体：Trae（手动）· 验收：Codex · 状态：已关闭 · 日期：2026-08-02 · 派发：manual · 项目：ccc
> 运行面提示：本卡只实现 + 测试，**不部署、不迁移**现有 7788 对话口与桌面端；实际切换为后续执行卡，需老板放行 + 回滚方案。

## 目标

新服务端补齐「对话/写」能力与鉴权（账号密码 + 会话 token），使旧 7788 对话口与桌面端具备切换条件：
- 新增接口：`POST /session`（账号密码换 token）、`POST /conversation`（对话）、`GET /conversation`（历史，可选）。
- 鉴权实现（非占位）：token 校验中间件；账号/密钥走 env，不落库。
- 桌面端 APIClient：base URL 配置化（指向新服务端）+ 认证流程接入（POST /session），保留旧地址兼容开关。

## 红线（先看）

1. **不碰旧引擎代码**：`scripts/`（含 chat_server）零改动。
2. 桌面端只改 `desktop/Sources/` 的 APIClient / 配置层（壳代码），不重构、不碰旧业务逻辑；构建验证可选（不强制安装）。
3. **不部署不迁移**：不启动新服务常驻、不注册 launchd、不改 7788 指向、桌面端不强制替换运行中的 App。
4. 鉴权必须真实实现（成功/失败/过期三态），密钥零落库；不硬编码（服务地址/端口走配置/env）。
5. 验收标准不可自行解释；完成必须提交（真实 commit）；工作树只允许预存 1 个无关改动（`_update_handoff.py`）。

## 范围

- 新增/修改：`server/web/server.py`（会话/对话接口 + 鉴权中间件）、`server/config/config.example.env`（账号/密钥/token 过期占位）、`server/tests/test_http_api.py`（新增用例）、`desktop/Sources/CCCDesktop/APIClient.swift`（指向配置化 + 认证）。
- 不动：`scripts/`、`server/board/`、`server/engine/`、`server/kb/`。

## 步骤

1. `server/web/server.py`：实现 `POST /session`（账号密码校验 → 签发 token）、鉴权中间件（Bearer token 校验，过期拒绝）、`POST /conversation`（对话占位实现：接收消息返回确认/回声，为后续接大脑留接口）；现有只读接口可选择性加鉴权或标注。
2. 配置：`config.example.env` 加 `CCC_WEB_USERNAME`/`CCC_WEB_PASSWORD_HASH`/`CCC_WEB_TOKEN_TTL` 占位；token 生成/校验本地实现（内存或文件，README 注明生产建议）。
3. 桌面端 `APIClient.swift`：base URL 从配置读取（默认兼容旧地址），认证流程接入 `POST /session`，401 时提示重登。
4. 测试：鉴权三态（成功/失败/过期）、对话往返、未鉴权请求 401。
5. 提交 `chore(api):`，回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. 鉴权三态测试全绿；未鉴权请求 401；token 过期拒绝。
2. 对话接口往返测试通过（回声占位即可，接大脑留接口）。
3. 桌面端 APIClient 指向配置化 + 认证接入（代码就绪；构建成功为加分项，非必须）。
4. 零硬编码；未部署/未迁移运行服务；`scripts/` 零改动。
5. 既有测试不回归；真实提交；工作树仅剩 1 个预存项。

## 回写要求

结果摘要（人话一句）、测试输出（含鉴权三态）、桌面端改动说明、commit hash；按契约 §3 同步更新本卡卡头状态。

## 回写区

**结果摘要**：服务端补齐鉴权（POST /session + Bearer token 中间件）+ 对话（POST/GET /conversation）回声占位；桌面端 APIClient 新增 `configureNewServer`/`loginToNewServer`/`sendConversation` 方法，base URL 可配置化，保留旧地址兼容。

**测试输出**：
```
server/tests/test_http_api.py ................... (19 passed)
  ✓ 鉴权成功、密码错误 401、用户名错误 401、缺凭证 400
  ✓ 未鉴权请求 401、无效 token 401、过期 token 401
  ✓ 对话往返回声、对话历史、未鉴权对话 401、空消息 400
  ✓ 所有 board 接口 200 + 数据形状断言
  ✓ /health 无鉴权、未知路径 404
```

**桌面端改动**：`APIClient.swift` 新增 148 行：
- `configureNewServer(url:)` — 配置新服务端地址（nil=禁用，走旧地址）
- `loginToNewServer(username:password:)` — POST /session 换取 Bearer token
- `sendConversation(message:)` — POST /conversation 回声占位（401 提示重登）
- `fetchNewServerConversationHistory()` — GET /conversation 历史
- 内存 token 缓存 + 过期判断 + 自动头注入
- Swift 构建成功（仅一条 unreachable 警告，不影响运行）

**红线校验**：
- `scripts/` 零改动 ✓
- 桌面端只改 `APIClient.swift`（壳代码）✓
- 不部署不迁移 ✓
- 鉴权真实实现（HMAC-SHA256 token，内存 store，过期拒绝）✓
- 零硬编码（端口/账号/密钥走 env）✓
- 既有测试无回归 ✓

**commit hash**: `88cf04a`
