# 任务书 A3 · 网页前端登录 + 会话 token 接入（窗口 A 第三波）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 A 即可。  
> 前提：窗口 B2（网页鉴权整改）已合入 main；接口契约见 `docs/dispatch/report-B2-backend-auth-round2.md` §五。

## 0. 先读

1. `CLAUDE.md`
2. `docs/dispatch/report-B2-backend-auth-round2.md`（尤其 §五 接口契约）
3. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 任务目标

1. **登录态**：`POST /api/auth/token`（Basic 换 Bearer），token 存 `sessionStorage`（会话级，不落 localStorage）
2. **请求头**：前端 API 调用带 `Authorization: Bearer <token>`；页面不再硬编码 Basic 凭证
3. **权限态**：viewer 只读 token → 写按钮禁用/403 友好提示；operator 正常
4. **探活/过期**：`GET /api/auth/session` 探活；过期引导重新登录；logout 可用
5. **401 处理**：不白屏、不弹裸错误，进登录引导

## 2. 允许范围

- `scripts/chat_server/frontend/**` 前端源码与样式、前端测试
- 登录相关的最小样式与状态管理

## 3. 红线（禁止）

- **后端鉴权逻辑不改**（`scripts/chat_server/auth.py`、`routers/auth.py`、`routers/*.py` 均不动，缺接口时列移交项）
- token 不写 localStorage；不引入密钥/真实凭据
- `desktop/`、`src-tauri/`、4000/4100 relay 相关
- 不破坏 Desktop/sidecar 既有链路；不删文件（除非计划说明）
- 提交 main

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「登录态方案 + 改动面 + 权限态交互设计」，**不写代码**。  
确认后实现，前端测试全绿再提交。

## 5. 验收标准

- 登录 → 拿到 token → 读/写接口正常（operator）
- 过期 → 自动引导重新登录，不白屏
- viewer token → 写操作禁用或 403 提示（有测试）
- 无 token/401 → 登录引导而非裸错误
- 前端测试全绿，无新增后端失败
- 提交在 `codex/ws-1-web` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 移交项（需后端配合的单独列）
