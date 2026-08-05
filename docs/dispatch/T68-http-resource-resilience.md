# 任务卡 T68 · HTTP 壳静态资源加载韧性（Cursor 测试卡 · M1 前端开发）

> 关联：T48 审计 P0（M1→2017 静态资源并发 ERR_CONNECTION_RESET 41%，SPA 白屏根因，前端侧）· 执行体：Cursor（M1 测试接手）· 验收：Codex（独立复验）· 状态：待分派 · 派发：manual · 项目：ccc · 日期：2026-08-05
> 工作目录：M1 `/Users/apple/program/CCC`；分支 `codex/cursor-t01-resource-resilience`（从 main 新建）
> **分步提交纪律（硬）**：每块完成立即 commit+push；禁止 `git add -A` 全量提交。

## 目标

HTTP 壳（`server/web/legacy-chat/`）静态资源偶发加载失败时不再静默白屏：关键脚本自动重试 + 降级提示。

## 背景（已取证，不要重新质疑）

- T48 审计实测：M1→2017 并发 100 请求拉 `/js/state.js` 等，41 次 ERR_CONNECTION_RESET；2017 本机仅 2-7%。
- 后果：`js/state.js` 偶发加载失败 → `app.js`（ES module，import state.js）初始化中断 → 页面只剩导航骨架（白屏），无提示无重试入口。
- 服务端已调队列 5→128（21a4166）；本卡只做**前端侧韧性**，网络根因另卡处理。

## 具体项

1. **关键脚本自动重试**：state.js 及其依赖链加载失败时自动重试（建议 2-3 次、指数退避）；重试成功则正常初始化。
2. **降级提示**：重试仍失败时，页面显示「资源加载失败，点击重试」横幅（点击重新加载），不再静默白屏。
3. **正常路径零变化**：加载成功时行为与现状完全一致（无额外请求、无闪烁）。
4. 设计说明：ES module 的 `state.js` 加载失败浏览器不会自动重试——需设计可靠机制（如经典脚本 bootloader 预检 + 动态注入，或等价方案），并在回写区说明取舍。

## 红线

1. 只改 `server/web/legacy-chat/`（index.html / js/ / css/）；**禁止改 server.py / engine / board / desktop/**。
2. 不引第三方依赖（纯原生 JS）；不引新构建工具。
3. 不动 2017 生产副本；只 push 分支，等 Codex 验收后合入部署。
4. 不得伪造验收证据——每条验收给真实命令输出。

## 验收标准（Codex 独立复验，不采信自述）

1. 正常路径：`bash scripts/verify-shell.sh --host 192.168.3.116 --port 7788 --with-conversation` 六场景全 PASS。
2. 故障路径（无头 Chrome 阻断静态资源模拟）：阻断 `state.js` → 自动重试后页面正常渲染；或持续失败时出现可点击重试横幅——**二者必有其一真实生效**（附复现脚本/证据）。
3. 回归：pytest server/tests 全绿（2017 环境）；改动文件无语法错误（node --check）。
4. git：分支分步提交、工作树干净、push 成功。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现方案与取舍、重试/降级行为证据、verify-shell 输出、pytest 结果、push 证据。

## 回写区

**执行体**：Cursor（M1）· 日期：
