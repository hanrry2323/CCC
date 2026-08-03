# 任务卡 T44 · 双壳体验优化：10 项问题修复（OpenCode 执行）

> 关联：老板实测反馈「问题太多」· 依据：Codex 无头 Chrome 真机实测 + 代码取证（2026-08-04）——10 项问题全部有证据，见下
> 执行体：OpenCode · 验收：Codex（严格，逐项复验）· 状态：执行中 · 日期：2026-08-04

## 目标

修复双壳（HTTP/桌面）10 项真实体验问题：桌面端旧包重装、HTTP 登录后直达对话、左栏项目列表、右栏任务卡流数据、模型档位、线程隔离、并发锁体验、线路图视图、登录文案、401 噪音。

## 红线（先看）

1. 每项修复先复现再改，验收按「问题清单逐项复验」；禁止只改代码不实测。
2. 只改 `server/web/`（legacy-chat 前端 + server.py 如需）+ `desktop/Sources/`；不动 2017 运行面（本卡 M1 实现 + 本地真机验证；2017 部署与桌面打包由 Codex 放行）。
3. 对话 API 协议不破坏（/session /conversation /board/* 向后兼容）；新增字段/端点必须向后兼容。
4. 回写前必须 push 成功并附证据（P2-4 纪律）。

## 问题清单（10 项，含证据与修复方向）

### P0（先做）

1. **桌面端安装包是旧版**——`/Applications/CCCDesktop.app` 二进制 2026-08-03 13:15（T28 打包），T40/T41/T43 的三栏/自动登录/流式全不在包里，老板打开的是旧 v0.66.1。
   → 修复：按 T28 流程重新打包安装（M1 OpenCode），含 T40–T43 全部源码；默认直连 2017:7788。
2. **HTTP 登录后默认落 `#/board`（看板）而非对话**——首要场景是对话，老板登录后被甩到看板页。
   → 修复：登录成功后默认路由改 `#/chat`（未登录/无会话状态也进对话视图）。
3. **HTTP 左栏项目列表彻底坏了**——`api.js loadProjects()` 把 `/board/summaries` 的**对象**（`{"INT-120": {...}}`）当数组 `.map` → `TypeError` → 侧栏永远「暂无项目 / Hub 恢复后自动出现」（旧文案）。
   → 修复：`Object.entries(data.summaries)` 处理 + 空态文案改「暂无项目」；boot 后侧栏真实渲染项目列表。

### P1

4. **HTTP 对话右栏任务卡流全 0**——工作区默认「CCC」查不到真实卡（真实项目为 INT-120 等），右栏永远「暂无任务」。
   → 修复：卡流按「全部工作区」或当前项目拉取（/board/snapshot 不带 workspace 或正确传参），与看板页数据一致。
5. **模型档位列表为空**——UI 显示「模型档位不可用：模型列表为空」，档位选择器（flash/Pro/code/sonnet/haiku）无数据源。
   → 修复：接入 /config 或服务端模型档位（实际可用 flash/code），档位选择可用。
6. **对话历史全局单列表，无线程/项目隔离**——`_conversations` 全局列表，`loadSession(threadId)` 忽略线程参数 → 多标签/多项目聊天互相污染；重启即失。
   → 修复：会话/线程维度隔离（前端本地按线程分桶 + 服务端 GET/POST /conversation 支持 thread_id 参数，缺省兼容全局行为）。
7. **全局单会话锁 503 busy**——一路对话进行中，其他路全部被拒，多壳并发体验差（ThreadingHTTPServer 已就绪，锁成为唯一瓶颈）。
   → 修复：按会话/项目分锁或并发上限 2（可配置），同会话串行、跨会话可并发。

### P2

8. **壳内无线路图视图**——四标签（看板/运维/控制台/对话）无线路图；老板要求三栏+线路图。
   → 修复：加「线路图」标签（/board/roadmap 数据已存在，按状态聚合展示）。
9. **登录页文案误导**——提示「CCC_AGENT_AUTH_USER / ~/.ccc/agent-auth.json」是旧 sidecar 配置名，新服务端为 CCC_WEB_USERNAME/PASSWORD_HASH；未读 /health auth_configured。
   → 修复：登录页按 /health 实际状态显示（已配置→正常登录；未配置→明确提示），文案去旧配置名。
10. **6 个 401 控制台噪音**——未登录/部分请求不带 token 报 401（轮询/探活/模型档位等）。
    → 修复：未登录态请求静默降级（不刷错误）、统一请求头带 token、401 只弹一次登录门。

## 范围

server/web/legacy-chat/（api.js、app.js、router.js、login-gate.js、agentAuth.js、components/sidebar.js、boardPanel.js、chatStatus.js、pages/、css/、index.html）、server/web/server.py（如需 thread_id/模型档位/分锁支持）、server/config/config.example.env、desktop/Sources/（如需随包）、server/tests/、打包产物（/Applications 安装）。

## 步骤

1. P0 三项：桌面重打包（T28 流程）；默认路由 → 对话；loadProjects 修对象解析 + 侧栏渲染（真机验证左栏出现项目列表）。
2. P1 三项：右栏卡流正确取数（真机验证与看板一致）；模型档位接入可用；线程隔离（server thread_id + 前端分桶，兼容缺省）。
3. P2 三项：线路图标签；登录文案按 /health；401 噪音静默。
4. 全量回归：pytest / swift build+test / ruff / py_compile；无头 Chrome 全流程复测（登录→对话→看板→运维→线路图→右栏卡流）。
5. 提交 + push（附证据）；桌面包由 Codex 放行后安装。

## 验收标准（逐项复验）

1. 桌面包为 T43 后新包（二进制时间 ≥ 本卡源码提交），自动登录直连 2017，三栏+流式可用。
2. 登录后直达 `#/chat`；对话视图左栏真实项目列表（非「暂无项目」）；右栏卡流与看板数据一致（非全 0）。
3. 模型档位选择器有真实档位可选；「模型档位不可用」提示消除。
4. 双会话并发：两个不同会话可同时对话（同会话串行），不再全局 503 拒绝。
5. 多线程/多项目对话历史不互相污染（各自会话独立）。
6. 线路图视图可用（数据来自 /board/roadmap）。
7. 登录页文案与 /health 实际状态一致；控制台无 401 噪音（无头 Chrome 复测零 console error）。
8. pytest / swift / ruff 全绿；无头 Chrome 全流程零 JS 错误；push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：10 项逐条「修复说明 + 复现前后对比」、桌面打包记录、无头 Chrome 复测输出、pytest/build 结果、push 证据。

## 回写区

**执行体**：OpenCode · 日期：
