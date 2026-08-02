# 任务卡 T13 · 服务端 HTTP API + 静态页接入（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 拓扑：任意设备经 HTTP 直连）· 管理席：Codex
> 执行体：Trae（手动）· 验收：Codex · 状态：待分派 · 日期：2026-08-02
> 背景：新栈只有静态看板页（board.js 注入），没有服务端 HTTP API——「任意设备=壳，经 HTTP 直连」的终态拓扑还差服务端这一半；旧 7788 对话口与桌面端也未对接新栈（T12 退役联动）。

## 目标

新服务端提供 HTTP API：`GET /health`、`GET /board/realtime`、`GET /board/recent`、`GET /board/by_project`、`GET /board/roadmap`（数据来自 board 查询，与静态导出同一事实源）；看板静态页可切换数据源（本地 board.js / HTTP API）。**本卡只实现 API 与测试，不部署、不迁移 7788、不接桌面端**（部署与旧壳对接需老板放行，留后续卡）。

## 红线（先看）

1. 不删除任何文件；不碰旧代码（scripts/app/desktop/lib/db/relay/skills 零改动，含旧 chat_server）。
2. **不碰运行面**：本卡不启动常驻服务、不注册 launchd、不监听真实端口交付物（用测试端口/临时端口冒烟，端口走配置不硬编码）。
3. 鉴权策略必须写明：对话/写接口的账号密码鉴权（沿用 7788 鉴权地基的契约约定）在后续壳对接卡落实；本卡 API 只读接口，鉴权占位须在 README 标注「上线前必须加鉴权」。
4. 不落密钥；不读写外脑；不硬编码（路径/端口走 config/env）；验收标准不可自行解释。
5. 完成必须提交（真实 commit）；工作树只允许预存 2 个无关改动。

## 范围

- 新增：`server/web/server.py`（HTTP API 入口，Python 标准库 http.server 或等价零依赖实现）、`server/tests/test_http_api.py`。
- 修改：`server/web/README.md`（API 说明 + 鉴权占位标注）、`server/config/config.example.env`（WEB_PORT 等已有占位，如缺补充）。
- 不动：board/engine/kb/relay/deploy 已验收部分。

## 步骤

1. `server/web/server.py`：路由 5 个 GET 接口，数据复用 board 查询（与 board.js 导出同源）；`--port` 走配置/参数（默认值仅测试用，禁止写死生产端口）。
2. 冒烟模式：`python3 -m server.web.server --port <临时端口>` 可启动，请求 /health 返回 200 JSON；测试内启动/关闭。
3. 看板静态页数据源切换：index.html/app.js 支持「本地 board.js / HTTP API」两种来源（配置或 URL 参数决定），API 不可用时回退本地数据。
4. README：API 文档（路径/参数/响应示例）+ 鉴权占位标注（上线前必须加账号密码 + 会话 token）。
5. 测试：5 个接口各自 200 + 数据形状断言；未知路径 404；启动/关闭无残留进程。
6. 硬编码扫描（S1–S4）零字面量；提交 `chore(web):`，回写真实 commit hash。

## 验收标准（Codex 按此验收）

1. 5 个接口测试全绿（数据与 board 查询一致）；/health 200；404 正确。
2. 静态页数据源可切换，API 失败回退本地数据（测试或文档证明）。
3. 零硬编码（端口走配置）；无常驻服务/无真实端口交付物/未注册 launchd。
4. 鉴权占位标注清晰（上线前必须加鉴权），不落密钥。
5. 既有测试不回归；真实提交；工作树仅剩 2 个预存项；未碰旧代码/外脑。

## 回写要求

结果摘要（人话一句）、测试输出、API 冒烟输出、commit hash；按契约 §3 同步更新本卡卡头状态。

## 回写区

（Trae 回写）
