# 任务卡 T23 · HTTP 直开部署（7788 托管页面 + 同源登录 + 桌面端指 2017）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 任意设备=壳，经 HTTP 直连对话；多壳锁门：账号密码 + 会话 token）· 依据：T22（2017 单端已部署）/ 跨机实测（M1→2017:7788 全接口通）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03
> 背景：老板反馈 M1 浏览器直接访问 `http://192.168.3.116:7788` 报 `{"error":"missing or invalid Authorization header"}`——根因：7788 当前是纯 API 服务，`/` 未托管页面且先过鉴权 → 401。

## 目标

浏览器**直接访问 `http://192.168.3.116:7788` 即打开看板页面**（服务端托管 `server/web/` 静态资源）；页面**同源自动走 API**（无需 `?api=` 参数）并**内嵌登录**（账号密码 → `/session` → token 存 localStorage → board/对话/运维全接口自动带 Bearer）；**桌面端默认服务端地址切到 `http://192.168.3.116:7788`**。完成后老板在 M1/手机/平板直接开网址即可登录使用。

## 红线（先看）

1. **鉴权不放松**：`/board/*`、`/conversation`、`/ops/summary`、`/tasks/*` 仍须 Bearer token；仅**静态资源路径**（`/`、`/css/*`、`/js/*`、`/data/board.js`、`/data/cluster.js`）免鉴权（页面本身是登录入口）；`/health`、`/session` 维持免鉴权。
2. **静态托管安全**：静态路径白名单（index.html / css/style.css / js/app.js / js/chat.js / data/board.js / data/cluster.js），禁止目录穿越（`..`、绝对路径拒绝），不落盘用户输入。
3. **零硬编码**：页面同源 API 用 `location.origin` 推导，不写死 IP/端口；桌面端默认地址允许设置界面修改（AppStorage）。
4. 不动：M1 4100/4102、2017 6100/6102、2017 Claude Code/OpenCode 配置、engine/board-scheduler 常驻服务；M1 与 2017 双轨并行，两端 7788 都要加载新代码（kickstart 重启）。
5. 不读写外脑；归档区零改动；完成必须提交（真实 commit）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 范围

- `server/web/server.py`：`do_GET` 在鉴权判断**之前**放行静态白名单路径；`/` 返回 `index.html`；`/css/*`、`/js/*`、`/data/board.js`、`/data/cluster.js` 读磁盘文件（Content-Type 用 mimetypes，零依赖）；非白名单路径照旧先鉴权后路由；防目录穿越。
- `server/web/index.html` / `js/app.js` / `js/chat.js`：同源 API 推导（`location.protocol === "http:"` 且无 `?api=` 时 `API_BASE = location.origin`）；token 统一管理（localStorage 优先 > URL `?token=`）；app.js 与 chat.js 共用同一 token 读取/注入逻辑；无 token 显示登录区，登录后刷新数据；`file://` 零 API 模式保留。
- 桌面端 `AppModel.swift`：`ccc.newServerURL` 默认值 → `http://192.168.3.116:7788`（AppStorage；已保存过旧值的用户需在设置界面改一次，卡内注明）。
- `server/tests/test_http_api.py`：静态托管用例（`/` 200 HTML、`/js/app.js` 200、`/css/style.css` 200、`/data/board.js` 200、目录穿越 404/403、非白名单 API 无 token 仍 401）。
- 部署：M1 `git push` → 2017 `git pull` → 两端 `launchctl kickstart -k gui/$(id -u)/com.ccc.web-server` 加载新代码 → 全链路验证。
- 不动：`engine`、`board-scheduler`（继续常驻）；`com.ccc.web-server` 的 env 配置。

## 步骤

### A. 服务端静态托管（M1 仓，代码）

1. `server/web/server.py` 定义静态白名单（`index.html`、`css/style.css`、`js/app.js`、`js/chat.js`、`data/board.js`、`data/cluster.js`）与根路径映射；`do_GET` 开头先处理静态路径（不查鉴权），再走原鉴权 + API 路由。
2. 静态文件读取：基于 `_PROJECT_ROOT / "server/web"` 拼接并校验 `resolve()` 在 web 目录内（防 `..`）；`Content-Type` 走 `mimetypes`（html/css/js 正确）；文件不存在 404。
3. 目录穿越/绝对路径/隐藏文件一律拒绝（404）。

### B. 前端同源 API + 登录统一（M1 仓，代码）

4. `index.html`：数据源推导改为——显式 `?api=` 参数优先；无参数且 `location.protocol === "http:"` 时 `API_BASE = location.origin`；`file://` 仍走本地 board.js。
5. token 管理统一：抽公共函数（存/取/删 localStorage `ccc-chat-token`，URL `?token=` 注入时同步写入）；app.js 的 board 请求与 chat.js 的对话请求共用；无 token → 显示登录区（chat.js 已有登录表单复用），登录成功 → 刷新 board 数据。
6. 无 token 且 API 模式：页面不白屏——显示登录提示 + 登录表单；登录前不请求 `/board/*`（避免 401 噪音）。
7. 桌面端 `AppModel.swift`：`@AppStorage("ccc.newServerURL")` 默认值改 `http://192.168.3.116:7788`（保留设置界面可改）。

### C. 测试 + 构建

8. `server/tests/test_http_api.py` 新增：`GET /` 200 且 `Content-Type` html；`/js/app.js`、`/css/style.css`、`/data/board.js` 200；`/../server.py`、`/etc/passwd`、`/%2e%2e/` 类路径 404；非白名单 `/board/states` 无 token 401。
9. `pytest server/tests/ -q` 全绿（现 188 + 新增）。
10. 桌面端 `swift build` 成功。

### D. 部署（双端）

11. M1 `git push origin main` → 2017 `git pull origin main`。
12. 两端重启 web-server：M1 `launchctl kickstart -k gui/$(id -u)/com.ccc.web-server`；2017 同命令（SSH）→ 两端 7788 新 PID。
13. 2017 本机验证：`curl http://127.0.0.1:7788/` 返回 HTML（非 401）；`/js/app.js` 200；`/board/states` 无 token 401。

### E. 跨机终验（M1 模拟老板访问）

14. M1：`curl http://192.168.3.116:7788/` 返回 HTML 200（**修复老板报错**）。
15. M1：`curl http://192.168.3.116:7788/js/app.js`、`/css/style.css` 200。
16. 全接口带 token 复测：`/session` 换 token → `/board/states`、`/board/snapshot`、`/ops/summary`、`/conversation`（经 6102 flash）全 200；无 token 401。
17. 桌面端代码确认：默认 `http://192.168.3.116:7788`；`swift build` 已过。
18. 三扫描（S1–S4 + 密钥 + 外脑依赖）本次变更零命中；M1 工作树仅剩预存 2 项。

### F. 提交 + 回写

19. 提交：`chore(http): T23 HTTP 直开部署 — 7788 托管页面 + 同源登录 + 桌面端指 2017`
20. 回写：卡头 `状态：待分派 → 已回写`，回写区填完（真实 commit hash、双端验证输出、验收自检表）。

## 回滚

- 代码回滚：`git revert` 本卡提交 → 两端 kickstart 重载。
- 页面回退：浏览器强刷（避免旧 token/缓存）；`localStorage` 清除 `ccc-chat-token` 即回到登录态。
- 桌面端：设置界面改回 `http://127.0.0.1:7788`（如 M1 双轨保留需要）。
- 触发条件：静态页面 404/穿越风险未控 / 同源登录失败 / 2017 pull 冲突 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. `http://192.168.3.116:7788/` 返回 HTML 200（M1 实测，修复老板报错）；css/js/data 静态资源 200；目录穿越 404。
2. 页面同源自动 API：无 `?api=` 时 `API_BASE=location.origin`；登录后 localStorage token 自动注入，board/对话/运维全通；无 token 显示登录表单不白屏；`file://` 模式保留。
3. 桌面端默认地址 `http://192.168.3.116:7788`；`swift build` 通过。
4. 鉴权不放松：API 无 token 仍 401；`/health`、`/session` 免鉴权。
5. `pytest` 全绿（188+新增）；三扫描零命中；真实提交；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

（执行后填写）

### 执行明细

（执行后填写：A–F 各步结果）

### 验收自检

（执行后填写：对照验收标准逐条勾选）
