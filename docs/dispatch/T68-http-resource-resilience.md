# 任务卡 T68 · HTTP 壳静态资源加载韧性（Cursor 测试卡 · M1 前端开发）

> 关联：T48 审计 P0（M1→2017 静态资源并发 ERR_CONNECTION_RESET 41%，SPA 白屏根因，前端侧）· 执行体：Cursor（M1 测试接手）· 验收：Codex（独立复验）· 状态：已回写 · 派发：manual · 项目：ccc · 日期：2026-08-05
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

**执行体**：Cursor（M1）· 日期：2026-08-05

### 实现方案与取舍

- 新增经典脚本 `server/web/legacy-chat/js/bootloader.js`；`index.html` 不再直接挂 `<script type="module" src=/js/app.js>`，改为加载 bootloader，由其动态注入 module 入口。
- **取舍**：ES module 失败 URL 会留在浏览器 module map，同页二次 `import('./state.js')` 不可靠。因此：
  - **成功路径**：与现状同构——直接 `createElement('script type=module')` 注入 `app.js`，无预检、无横幅闪烁、无额外业务请求。
  - **失败路径**：`sessionStorage` 计数 + 指数退避（400ms × 2^n）整页重载（清 module map）；重试访问时对 `state.js`/`app.js` 做 fetch 预检（最多 3 次）；累计 3 次仍失败 → 显示可点击横幅「资源加载失败，点击重试」（点击清计数并 reload）。
  - bootloader 自身加载失败：`index.html` 内联 `onerror` 同样打出横幅。
- 样式：`css/shell.css` 增加 `.ccc-resource-fail-banner`；缓存 token `v=20260805t68`。
- 改动范围仅 `legacy-chat/`（index.html / js/bootloader.js / css/shell.css）。

### 语法检查

```text
$ node --check server/web/legacy-chat/js/bootloader.js
（exit 0，无输出）
```

### verify-shell（2017 :7788）

```text
$ bash scripts/verify-shell.sh --host 192.168.3.116 --port 7788 --with-conversation
═══ CCC 壳 headless 复验 · http://192.168.3.116:7788 · 2026-08-05 20:05:30 ═══
[PASS] 免登录直进: /health ok（auth_required=False），直连免鉴权
[PASS] 左栏业务项目: /projects 返回 17 个业务项目：ai-loop-router, CCC, medio-0, qb, QuantHive, ccc-demo
[PASS] 零 console error: 9 个壳端点全部 2xx/3xx，无 5xx/401
[PASS] 流式: SSE 事件流动（verdict=ok，文本 174 字）
[PASS] 思考折叠无空占位: 前端守卫 OK；本流无 thinking 事件（无折叠即无占位）
[PASS] 切界面不断流: after=6 → 增量 2 条，seq=8 无缺口（切回拉取不丢内容）
─── 汇总 ───
PASS：6 PASS / 0 FAIL / 0 SKIP（共 6 场景）
```

### 无头 Chrome 故障模拟（二者均真实生效）

复现脚本：`/tmp/t68_headless_resilience.py`（本地 ThreadingHTTPServer 托管 `legacy-chat/`，对 `/js/state.js` 返回 503；Selenium + ChromeDriver 148 + headless Chrome）。

```text
$ python3 /tmp/t68_headless_resilience.py
[
  {
    "case": "persistent_fail_banner",
    "expect": "banner",
    "ok": true,
    "detail": "banner visible; scripts={'banner': True, 'bootFails': '3', ...}; hits=7 fails=7"
  },
  {
    "case": "transient_fail_recover",
    "expect": "recover",
    "ok": true,
    "detail": "recovered after flaky state.js; ... hits=3 fails=1"
  }
]
```

- 持续失败 → `#ccc-resource-fail-banner` 文案「资源加载失败，点击重试」出现（`bootFails=3`）。
- 瞬时失败 1 次 → 自动重载/预检后恢复（`bootFails` 清除，module 注入成功）。

### pytest（2017）

```text
$ ssh fan@192.168.3.116 'cd /Users/fan/program/CCC && python3 -m pytest server/tests/ -q --tb=line; echo EXIT:$?'
........................................................................ [ 14%]
........................................................................ [ 29%]
........................................................................ [ 44%]
........................................................................ [ 58%]
........................................................................ [ 73%]
........................................................................ [ 88%]
..........................................................               [100%]
EXIT:0
```

本卡未改 Python；M1 无 6100 时 engine 探活相关用例失败属环境差，以 2017 EXIT:0 为准。

### git

```text
分支：codex/cursor-t01-resource-resilience
414ed25 feat(legacy-chat): add resource bootloader with retry + fail banner (T68)
2a3bcf6 feat(legacy-chat): wire bootloader + resource-fail banner styles (T68)
（本回写另 commit）
push：origin/codex/cursor-t01-resource-resilience
```

### 复现脚本要点（Codex 可独立重跑）

M1：`/tmp/t68_headless_resilience.py` + ChromeDriver 148（`/tmp/chromedriver-mac-arm64/chromedriver`）+ 本机 Chrome。核心：本地托管 `server/web/legacy-chat/`，对 `state.js` 先返回 503（预算 N 次），Selenium headless 打开 `/index.html`，断言横幅或恢复。