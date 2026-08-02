# 任务卡 T24 · 桌面端重打包对接 2017 + 网页对话页重设计（延续桌面端 Claude 风格）（Trae 执行）

> 关联：INT-120（CCC 重构收尾）· 契约：CCC 重构契约 v1（§8 多壳=同一 API 契约的不同客户端；多壳锁门账号密码+token）· 依据：T19–T23（新服务端/壳迁移/2017 部署/HTTP 直开全完成）· 管理席：Codex
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03
> 背景：老板实测——网页可访问可对话 ✅；**桌面端完全断**（根因已定位：`/Applications/CCCDesktop.app` 是 7-30 构建的 v0.65.2 旧包，T19–T23 的新服务端代码未打包安装，App 仍在找已停用的旧 sidecar）；网页对话页需按桌面端 Claude 风格重设计。

## 目标

1. **桌面端重新打包并安装**到 `/Applications/CCCDesktop.app`（版本取仓内 `VERSION`=v0.66.1），默认对接 `http://192.168.3.116:7788`，账号 ccc/ccc，`useNewServer` 开——桌面端恢复可用。
2. **网页对话页重设计**：延续桌面端 Claude 风格（暖米色 chatBg/侧栏、`#D97A55` 橙红 accent、serif 大标题、气泡左右分栏、底部 composer 工具栏），参考旧成熟对话页（`docs/archive/legacy-retired-2026-08-02/scripts/chat_server/frontend/`）与桌面端 `CCCTheme` 令牌，把当前简陋对话区升级为与桌面端同等成熟的对话体验。

## 红线（先看）

1. **桌面端打包必须用仓内当前源码**（含 T19–T23 全部改动），不得用旧 build 缓存；版本读 `VERSION`；安装前旧 App 退出。
2. **网页重设计不动 API/鉴权逻辑**：登录（`/session`）、对话（`/conversation`）、token（localStorage）协议与 T23 一致；只改视觉/交互层（html/css/js 表现层），不破坏 `file://` 本地模式与 `?api=`/同源模式。
3. 网页风格**以桌面端 `CCCTheme` 为权威**：暖米色底、橙红 accent、serif 标题、左用户/右 Agent 气泡、底部 composer（模型选择/附件/发送）；不引入第三方库/框架（纯 html/css/js）。
4. 零硬编码：网页不写死 2017 IP（同源 `location.origin` 推导，T23 已实现不破坏）；桌面端地址走 AppStorage（默认值可改）。
5. 不动：`server/` API 层（除表现层文件）、engine/board-scheduler、M1 4100/4102、2017 6100/6102、2017 Claude Code/OpenCode 配置；不读写外脑；完成必须提交（真实 commit）；验收标准不可自行解释；M1 工作树只允许预存 2 个无关改动。

## 范围

- 桌面端：`desktop/scripts/package-baseline.sh` 打包（release + .app）→ 备份旧 App → 安装新 App 到 `/Applications/` → 写默认配置（`ccc.newServerURL=http://192.168.3.116:7788`、`ccc.useNewServer=1`、`ccc.newServerUser=ccc`、`ccc.newServerPass=ccc`）→ 启动冒烟。
- 网页对话页：`server/web/index.html`（对话视图结构）、`server/web/css/style.css`（对话区样式，沿用现有令牌体系但对话区按 Claude 风格）、`server/web/js/chat.js`（对话渲染/composer/登录交互升级）。
- 不动：`server/web/js/app.js`（看板/集群/运维逻辑）除必要的主题联动；`server/web/server.py` 零改动。

## 步骤

### A. 桌面端重新打包安装（M1）

1. 退出运行中的 CCCDesktop（如有）：`osascript -e 'quit app "CCC Desktop"'` 或 `pkill -f CCCDesktop`。
2. 备份旧包：`mv /Applications/CCCDesktop.app ~/.ccc/backup-CCCDesktop-20260803.app`（如存在）。
3. 打包：`cd desktop && bash scripts/package-baseline.sh`（读 VERSION=v0.66.1，产物 `.build/release/CCCDesktop` + `.build/CCCDesktop.app`）。
4. 安装：`rm -rf /Applications/CCCDesktop.app && cp -R desktop/.build/CCCDesktop.app /Applications/`。
5. 写默认配置（新服务端对接）：
   - `defaults write com.ccc.desktop "ccc.useNewServer" -bool true`
   - `defaults write com.ccc.desktop "ccc.newServerURL" -string "http://192.168.3.116:7788"`
   - `defaults write com.ccc.desktop "ccc.newServerUser" -string "ccc"`
   - `defaults write com.ccc.desktop "ccc.newServerPass" -string "ccc"`
   - 清旧会话：`defaults delete com.ccc.desktop "ccc.agent"` 等旧 key 不必要，但确保 `ccc.server`/`ccc.agent` 不再被新服务端路径依赖（useNewServer 为 true 时走新链路）。
6. 启动：`open /Applications/CCCDesktop.app` → 确认进程在、窗口出。

### B. 桌面端对接验证（M1 实测）

7. `lsof -iTCP:7788` 确认新 App 与 2017 建立连接（观察 App 请求日志或网络连接 `netstat -an | grep 192.168.3.116`）。
8. 若无法自动登录：桌面端设置 UI 手动确认（账号 ccc/密码 ccc/地址 192.168.3.116:7788）——记录手动步骤供验收。

### C. 网页对话页重设计（M1 仓，表现层）

9. 设计基线（严格对齐桌面端 `CCCTheme`）：
   - 对话底色 `#f2ede8`（暖米色）；侧栏 `#efe8e0`；卡片/输入底 `#fbfaf6`；
   - accent `#d97a55`（橙红，按钮/发送/选中态）；正文深暖 `#1a1714`；次要 `#574f48`；
   - 标题 serif（Georgia/PingFang SC 大字重 light，约 22pt）；正文 14.5pt light，行距 4px；
   - 气泡：用户右对齐 `#e0d4c4` 暖褐底、Agent 左对齐 `#faf7f3` 米白底，圆角 12–14，消息块间距 22px；
   - 底部 composer：模型选择下拉（flash/Pro/code）+ 附件按钮 + 输入框 + 发送按钮，间距/圆角对齐桌面端 composerDock。
10. 对话区结构升级（`index.html` 对话视图 + `chat.js`）：
    - 空态欢迎（"有什么可以帮忙的？" + 引导文案，与桌面端一致）；
    - 消息流：用户/Agent 气泡分左右，角色标签、时间戳可选，自动滚动到底；
    - 流式占位：`/conversation` 非流式（T19 现状）→ 发送后显示"思考中…"占位，收到回复替换；
    - 登录卡片：居中卡片式（标题/账号/密码/错误提示/登录按钮），登录后切对话区；
    - 会话体验：发送中禁用按钮、Enter 发送、错误提示保留在输入区上方。
11. 视觉令牌联动：`style.css` 对话区变量对齐桌面端；保持深/浅主题开关可用（浅色=上面米色调；深色=同色系暗化，不引入蓝紫科技风）。

### D. 测试 + 部署

12. `pytest server/tests/ -q` 全绿（表现层改动不应破坏 API 测试；现 197）。
13. 网页冒烟（M1 → 2017）：`/` 200 出页面；登录 → 对话 → 看板/运维切换正常；`file://` 本地模式仍可开。
14. 双端同步：M1 `git push` → 2017 `git pull` → 2017 web-server kickstart 加载新页面。
15. 三扫描（S1–S4 + 密钥 + 外脑依赖）本次变更零命中；M1 工作树仅剩预存 2 项。

### E. 提交 + 回写

16. 提交：`chore(desktop-web): T24 桌面端重打包对接 2017 + 网页对话页 Claude 风格重设计`
17. 回写：卡头 `状态：待分派 → 已回写`，回写区填完（真实 commit hash、桌面端安装/连接证据、网页对话页冒烟、验收自检表）。

## 回滚

- 桌面端：`mv ~/.ccc/backup-CCCDesktop-20260803.app /Applications/CCCDesktop.app`（旧包恢复）；或重装新包后仅回退配置 `defaults delete com.ccc.desktop "ccc.useNewServer"`。
- 网页：`git revert` 本卡提交 → 双端 kickstart。
- 触发条件：桌面端连接失败不可修复 / 网页对话页功能回归（登录/对话/看板任一断） / 2017 pull 冲突 / 老板或管理席要求。

## 验收标准（Codex 按此验收）

1. 桌面端：`/Applications/CCCDesktop.app` 为新包（版本 v0.66.1、构建时间 2026-08-03）；`defaults` 中 `useNewServer=true`、`newServerURL=http://192.168.3.116:7788`；App 启动后与 2017 建立连接（网络连接或对话往返证据）。
2. 网页对话页：登录卡片、用户/Agent 左右气泡、composer（模型/附件/发送）、空态欢迎、思考占位全部实现；视觉对齐桌面端 Claude 风格（暖米色 + 橙红 accent + serif 标题，深/浅主题可用）。
3. 功能不回归：登录→对话→看板/运维切换全通；`file://` 本地模式可用；`?api=`/同源模式可用。
4. `pytest` 全绿；三扫描零命中；真实提交；M1 工作树仅剩预存 2 项；卡头状态已同步（§3）。

## 回写区

**执行体**：Trae · 日期：2026-08-03

### 结果摘要

（执行后填写）

### 执行明细

（执行后填写：A–E 各步结果）

### 验收自检

（执行后填写：对照验收标准逐条勾选）
