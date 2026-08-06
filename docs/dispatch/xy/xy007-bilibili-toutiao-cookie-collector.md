# 任务卡 xy007 · 登录流程：实现B站与头条自存Cookie扫码抓取工具（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

实现一个基于 Playwright 的 B站与今日头条（toutiao）自存 Cookie 扫码抓取命令行工具，解决 `GOAL.md` 中 K8 扫码卡点，实现自动检测并导出 Cookie 数组保存至本地 `data/cookies/`。

## 红线（先看）

1. 只动 xianyu 仓 `scripts/` 与配置相关代码；不改变已有的安全解密和存储分工。
2. 不直推 main；代码走卡内分支 `codex/xy007-bilibili-toutiao-cookie-collector`。
3. Cookie 必须保存为符合 `browser_base.py` 识别的格式（如标准 puppeteer/playwright Cookie JSON 数组格式）。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- 新增脚本 `scripts/cookie_collector.py` 扫码命令行。
- 支持 B 站（bilibili）和今日头条（toutiao）两平台的浏览器唤起、登录检测与 Cookie 自动保存。
- 视频发布 `browser_base` 本地环境联调测试。

## 步骤

1. **阅读分工**：在 2017 阅读 `docs/09-部署方案/05-平台Cookie扫码登录方案.md`，明确 B 站、头条号和微博由 xianyu 走本地自存路径，即 `data/cookies/bilibili.json` / `toutiao.json`。
2. **实现命令行抓取脚本**：
   - 编写 `scripts/cookie_collector.py`（基于 Playwright），提供命令如 `python scripts/cookie_collector.py --platform bilibili`。
   - 运行后自动唤起一个非无头（headed）的 Chromium 浏览器窗口，自动跳转到平台登录页（扫码页）。
   - 脚本内部以 3 秒/次频率循环检测当前浏览器 URL、localStorage 或特定 DOM 是否进入「已登录」状态，或等待手动扫码完成后回车。
   - 检测成功后，调用 `context.cookies()` 将 cookies 数组结构化，落盘到指定 `data/cookies/{platform}.json`，并自动关闭浏览器。
3. **安全与格式验证**：
   - 保证落盘的 Cookie 格式能够被 xianyu 既有的 `browser_base.py` 直接解析并成功注入到发文流程。
4. **单测覆盖**：
   - 在 `tests/` 编写测试对 `cookie_collector.py` 进行逻辑覆盖（可 mock 浏览器抓取）。
5. **探针实测**：
   - 跑一次 `python scripts/cookie_collector.py --platform bilibili --dry-run` 模拟调用。
6. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `cookie_collector.py` 能稳定唤起浏览器进行 B 站与头条登录。
2. 登录成功后，能在 `data/cookies/` 下自动生成规范的 `bilibili.json` / `toutiao.json`，且能通过 `browser_base.py` 内部检测（附实测扫码生成的文件样本及 logs）。
3. 单元测试全过。

## 补充信息

- 痛点：目前 Cookie 只能手动提取并手写 JSON 注入，效率极低且不安全。有了该 CLI，老范只需在 2017 敲一条命令即可全自动扫码捕获。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：
