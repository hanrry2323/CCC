# 任务卡 T30 · HTTP 页面重构（修复登录 bug + 页面功能/UI 按新栈方案重做）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 任意设备=壳，HTTP 直连 2017 对话/看板/运维；多壳锁门账号密码+token）· 依据：老板 2026-08-03 指示「HTTP 页面还没重构，看清单页功能、UI 然后出方案；特别是账号密码登录不了」· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03

## 根因（Codex 已实锤）

**登录 bug**（P0）：`legacy-chat` 页面走 `agentAuth.js`（`isDialogueShell()=true`），登录成功 token 写入 `ccc_agent_token`；但 `api.js` 请求头读的是 `auth.js` 的 `ccc_chat_token`——**登录成功但请求不带 token，全部 401**。另 `/health` 返回 `{"status":"ok"}` 无 `auth_required` 字段，启动门 `ensureAgentAuthenticated` 直接放行不弹登录门。

**页面现状**：`server/web/legacy-chat/`（旧对话页，T25 找回）含对话/看板/运维/控制台四视图，但 API 层只适配了对话 + 少量 board；看板/运维页（`pages/boardPage.js`/`opsPage.js`/`consolePage.js`）仍依赖旧 Hub 协议；UI 为旧版样式（Claude 暖米色已在，但组件/布局未按新栈收口）。

## 目标

1. **修复登录**：token 键统一、登录门正确触发、登录后对话/看板/运维全部带 Bearer 可访问。
2. **页面功能按新栈**：对话（/conversation 走大脑 Agent，T29 后）、看板（/board/snapshot|states|recent|roadmap）、运维（/ops/summary）、项目（/board/summaries）全部走新服务端协议；删除旧 Hub 协议调用（transfer/flow/mind/board-proxy 等）。
3. **UI 按 Claude 风格收口**：延续桌面端 CCCTheme（暖米色 + 橙红 accent + serif 标题 + 气泡 + composer），对话/看板/运维/控制台四视图统一视觉；深/浅主题可用。

## 红线（先看）

1. **只改 `server/web/`**（legacy-chat 及必要共享 js/css）；`server/web/server.py` 如需增静态映射/health 字段可改，但 API 协议不变（/session /conversation /board/* /ops/summary）。
2. **登录门必须真实**：`/health` 增加 `auth_required`/`auth_configured` 字段（或前端按 401 触发登录门）；token 键统一为单一 `ccc_chat_token`（agentAuth 与 api.js 共用）；登录成功即所有请求带 Bearer。
3. 页面功能只走新协议；旧 Hub 端点（`/api/board/proxy`、`/api/desktop/*`、`/api/ops/*`、`/api/chat`、transfer/flow/mind）零调用。
4. UI 延续桌面端 Claude 风格（CCCTheme 色板/字体/气泡/composer），不引入第三方框架（纯 html/css/js）。
5. 不动：`server/` 其他模块、2017 各服务、M1 中转站、6100/6102、桌面端；不读写外脑；完成必须提交（真实 commit）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 范围（server/web/）

### A. 登录修复（P0）

1. `legacy-chat/js/agentAuth.js` 与 `legacy-chat/js/auth.js` 统一 token 键（统一用 `ccc_chat_token`，或 agentAuth 复用 auth 的 setToken/getToken）；`api.js` 请求头读同一键。
2. `server/web/server.py` `/health` 增加 `auth_required: true`、`auth_configured: true`（凭证已配置）；`ensureAgentAuthenticated` 正确弹登录门。
3. 登录门流程实测：未登录 → 弹登录卡 → ccc/ccc → token 落 localStorage → 对话/看板/运维请求全部 200。

### B. 页面功能新协议化

4. `legacy-chat/js/pages/boardPage.js`：看板数据改走 `/board/snapshot` + `/board/states`（状态徽章）+ `/board/recent` + `/board/roadmap`；项目列表 `/board/summaries`。
5. `legacy-chat/js/pages/opsPage.js`：运维改走 `/ops/summary`（节点/红灯/概览）。
6. `legacy-chat/js/pages/consolePage.js`：控制台按新栈裁剪（Engine/调度状态如有对应接口则接，否则隐藏或占位提示）。
7. `legacy-chat/js/components/*`：删除/禁用旧 Hub 调用（transfer/flow/mind/board-proxy/写操作），保留对话渲染/消息气泡/composer。
8. 全页无旧 `/api/*` 调用（grep 校验）。

### C. UI 按 Claude 风格收口

9. `legacy-chat/css/*`：统一到桌面端 CCCTheme 令牌（暖米色底 `#f2ede8`、surface `#fbfaf6`、accent `#d97a55`、serif 标题、气泡左右、composer 底部工具栏）；四视图布局一致；深/浅主题可用。
10. 对话页保留 T25 找回的成熟交互（多标签/流式占位/侧栏），仅视觉对齐 + 功能新协议。

### D. 测试 + 部署

11. `server/tests/test_http_api.py`：/health 新字段用例；静态资源 200 回归；`pytest` 全绿（现 206+）。
12. M1 push → 2017 pull → 双端 kickstart web-server。
13. 实测（M1 模拟老板）：直开 `http://192.168.3.116:7788` → 登录（ccc/ccc）→ 对话/看板/运维/控制台全可用；无 401 循环；无旧协议 404。

### E. 提交 + 回写

14. 提交：`chore(web): T30 HTTP 页面重构——登录修复 + 功能新协议化 + UI Claude 风格收口`
15. 回写：卡头 `状态：待分派 → 已回写`，回写区填（登录修复说明、协议清单、UI 说明、测试输出、双端实测、验收自检表）。

## 回滚

- `git revert` 本卡提交 → 双端 kickstart（回到 T25 旧页面 + 登录 bug 状态，功能可用性差但可回退）。
- 触发条件：登录仍失败 / 对话/看板/运维任一断 / UI 偏离 Claude 风格过大 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. **登录真实可用**：直开页面弹登录门 → ccc/ccc → 登录成功 → 对话/看板/运维全 200；错误密码 401 提示；token 键统一（grep 单一键）。
2. 页面功能全走新协议：对话 /conversation、看板 /board/*、运维 /ops/summary、项目 /board/summaries；**零旧 `/api/*` 调用**。
3. UI 为桌面端 Claude 风格（暖米色/橙红/serif/气泡/composer/主题切换），四视图视觉一致。
4. `pytest` 全绿；三扫描零命中；真实提交；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

（执行后填写）

### 执行明细

（执行后填写：A–E 各步结果）

### 验收自检

（执行后填写：对照验收标准逐条勾选）
