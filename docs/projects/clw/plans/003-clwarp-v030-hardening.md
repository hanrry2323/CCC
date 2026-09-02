# 方案 · clwarp 0.3.0 缺陷收口与兑现（设置接线 / CSS 重建 / 终端生命周期 / CSP / 工程化修绿）

> 项目：clw · 编号：clw-plan-003 · 状态：已完成 · 作者：OpenCode（中枢） · 工具：OpenCode
> 创建：2026-08-11 · 更新：2026-08-11
>  关联卡：已归档（原引用 clw013, clw014, clw015, clw016, clw017, clw018, clw021 随 8-24 治理归档，见 docs/archive 与 RETIRED 记录）
> 关联方案：clw-plan-002（v0.2.0 全量重构，已合入发布）
> 进度：7/7 (100%)

## 目标

把 clwarp v0.2.0 暴露的 **P0/P1 级缺陷** 收口，兑现 0.2.0 声称但实际未落地的能力（设置面板接线、CSS/主题层、事件时序、配置去硬编码），并让 CI 真正修绿、构建可分发。核心链路（设置可改可存、终端生命周期不泄漏、看板可配置、CI 绿）在 0.3.0 实测下真实可用。

## 背景

0.2.0（clw008-012）已合入 clwarp main 并发布部署。三路 Agent 深度探查（Rust 后端 / 前端 UI / 工程化对照）交叉印证，**核心结论：后端 7/10 真实可跑，前端"设置面板 10%、样式层 5%"，多项声明与实际不符**。

**P0 级（用户直接感知的假功能）：**
- **设置面板空壳**：App.tsx 渲染 `components/SettingsPanel.tsx`（纯 UI 壳，零 invoke，注释自曝"接线将在 clw011 中实现"——clw011 已合入但没兑现）；真实现 `src/SettingsPanel.tsx`（223 行，load/save/board_url/workspace_paths/layout 全有）是死代码无人 import。改设置不生效不落盘。
- **CSS 层不存在**：App.css/index.css 100% 是 Vite 模板残留（`.counter/.hero/#next-steps/.ticks`），应用实际使用的 35+ 类（app-container/sidebar/resize-handle/main-view/...）零定义；`#root{width:1126px;text-align:center}` 框住全局；主题 token/深色模式实际不存在（组件硬编码 Dracula hex）；clw010"清残留+主题token"名不副实。

**P1 级（可靠性与声明欠账）：**
- **StrictMode 双挂载泄漏 PTY**：dev 模式每次开终端泄漏 1 会话 + 2 个全局监听器（main.tsx 用 StrictMode，cleanup 在异步 spawn 未决时 activeSessionId 为空 → 不杀后端 PTY）。
- **视图切换杀终端**：切看板/设置 → TerminalView 卸载 → cleanup 调 `kill_terminal` 强杀会话；sessionToResume/activePtyId 未联动清 → 切回后重新 spawn（现场丢失），header 残留死 PTY ID。
- **事件时序竞态**：读线程先于 `sessions.insert` 启动（terminal.rs:180 vs 246），子进程秒退时死会话入 map；前端先 invoke 再 listen，spawn 后初始输出/退出事件丢失 → 白屏/假连接。
- **登录 shell 无超时 + 每次 spawn 跑一次**：`$SHELL -lc 'echo $PATH'` 同步阻塞无超时，profile 挂起则 spawn/resume 永久不返回；未缓存。
- **CSP 锁死单一 IP**：frame-src/connect-src 写死 `192.168.3.116:7788`，settings.board_url 改了也被拦（"可配置"形同虚设）；`script-src 'unsafe-inline' 'unsafe-eval'` 过宽。
- **HOME/board_url 硬编码残留**：settings.rs 4 处 `/Users/fan` 兜底（且与 session.rs 的 dirs 不一致）；配置写非原子（fs::write 直接写，写一半崩溃即损坏）；board_url 默认值硬编码内网 IP。
- **CI 不可绿**：git_status.rs 测试断言 `/Users/fan/...` 本机路径，macos runner 必失败；settings 测试写真实 $HOME；tauri build --no-bundle 不产 DMG 无 artifact。

**P2（清理项）：** kill 可靠性（Pty::drop 阻塞 wait、逃逸子进程）、死命令（read_from_terminal/set_window_size/kill_session 无人调用）、@xterm/addon-fit 死依赖、workspace_paths/layout 存而不用、UI 副标题仍写"GPU 加速"、RELEASE.md 指向 v0.1.0 报告、favicon 还是 Vite logo、窗口 800×600 偏小。

## 方案内容

按六块推进，每块一张卡，顺序依赖（先修"看起来有实际没有"的 P0 → 再修可靠性 → 工程化收口）：

**切片 A · 设置面板接线 + 配置真实消费（P0 根修）**
- 删 `src/components/SettingsPanel.tsx` 空壳，App.tsx 改引 `src/SettingsPanel.tsx` 真面板（load_settings/save_settings/board_url/workspace_paths/layout 全接线）；保存后刷新 App 的 settings 状态（board_url 即时生效，去掉"重启生效"误导）
- workspace_paths 接到 `spawn_terminal`（新会话默认 cwd）、layout 接到布局应用；若 0.3.0 不消费则从设置面移除（避免"假配置"）
- 补 SettingsPanel 组件测试

**切片 B · CSS/主题层重建（P0 根修）**
- 删除 App.css/index.css 全部 Vite 模板残留（.counter/.hero/#next-steps/.ticks 等）+ assets/hero.png、react.svg、vite.svg、public/icons.svg、public/favicon.svg（换应用图标）
- 为 35+ 个真实类补齐样式：app-container flex 行布局、sidebar、resize-handle（宽度+cursor col-resize+防选）、main-view、header/footer-panel、provider-group、session-item、git-badge、spinner（带 role=status）、alert-error 等
- 主题 token（CSS 变量）：定义 `--primary-color/--error-color/--warning-color/--text-muted` 等已引用变量；xterm 主题从 token 注入；index.css 去 `#root{width:1126px;text-align:center}`；窗口默认 1000×700

**切片 C · 终端生命周期修复（P1 根修）**
- StrictMode 双挂载泄漏：spawn 竞态守卫（cleanup 用同步 flag 标记已卸载，async 完成时检测；或在 cleanup 里 kill 未决 spawn）
- 视图切换不杀会话：TerminalView 卸载时不清 session（App 层保活），或改为显式"分屏/保留"策略并清理 UI 状态（activePtyId/sessionToResume 联动）
- spawn 失败 loading 死锁：handleSessionCreated 无论成功失败都 setLocalLoading(false)
- 事件时序：spawn 完成、会话入表、读线程就绪后再返回 invoke（insert 先于读线程），前端 listen 与 invoke 竞态修复（会话级输出缓冲/启动握手）
- 死命令清理：删 read_from_terminal/set_window_size/kill_session 注册与实现（前端已用事件推送/resize_terminal/kill_terminal）

**切片 D · CSP / 看板 / 配置健壮性（P1 根修）**
- CSP 动态化：frame-src 跟随 config 的 board_url（或统一代理看板请求；文档写明安全权衡）；去掉 `script-src 'unsafe-eval'`（vite build 产物不需要）；看板 iframe 加 loading/失败态 + sandbox
- 配置原子写：tmp+rename + 解析失败自动备份重建；board_url 协议白名单校验
- HOME 去硬编码统一 `dirs::home_dir()`（settings.rs/session.rs 全量，删 `/Users/fan` 兜底）
- 登录 PATH 一次性解析 + 缓存（state 级）+ 超时；spawn 从"可挂起秒级"降"毫秒级"

**切片 E · 工程化修绿 + 分发（P1 根修）**
- CI 修绿：git_status.rs 测试改纯函数/临时目录（不依赖本机路径）；settings.rs 测试用 tempfile 隔离；加 cargo cache + `--locked`；`tauri build` 去掉 --no-bundle 并上传 DMG artifact；cargo clippy -D warnings 清零
- 测试补强：前端补 SessionList/SettingsPanel/TerminalView 真实用例（mock event API + xterm resize）；Rust 补 split_valid_utf8 边界、PATH 注入逻辑
- 签名与分发：配置 signingIdentity + notarization 说明（或至少 spctl 指引）；可选 tauri-action 自动 Release
- 死代码清理：@xterm/addon-fit 死依赖（Terminal.tsx 用 ResizeObserver）确认去留

**切片 F · 文档/文案一致性（P2 收口）**
- i18n 副标题去"GPU 加速的原生 PTY"→ xterm.js 如实；App.tsx 设置按钮关闭态文案（`✕ 终止` → 独立词条）、看板按钮文案进 i18n；formatDate 传 zh-CN；index.html lang=zh-CN
- RELEASE.md 补 v0.2.0 交付报告（现指向 v0.1.0 报告，其仍声称 Metal GPU）；CHANGELOG 对齐

## 验收标准

- [x] 设置面板真实可用：改 board_url/workspace_paths 保存后落盘 `~/.clwarp/config.json`，看板 iframe 即时按新 URL 加载（不再"重启生效"）；不再有假空壳面板
- [x] CSS 层真实存在：Vite 模板类全清，35+ 真实类有样式，布局 flex 正常，resize-handle 可抓取，终端撑满不塌缩，深色主题 token 生效，index.html lang=zh-CN
- [x] 终端生命周期：dev StrictMode 下重复开/切终端无 PTY 泄漏（进程数验证）；切看板/设置不杀会话（返回现场保留）；spawn 失败 loading 消失并显示友好错误
- [x] 事件时序：spawn 后初始输出不丢失、秒退会话正确收尾（无"已连接"假象）
- [x] CSP 与配置一致：改 board_url 后 iframe 不被拦；配置原子写（中断不损坏）；无 `/Users/fan`/`192.168.3.116` 源码硬编码（除默认值文档化）
- [x] CI 修绿：`cargo test`/`clippy -D warnings`/前端 vitest 在干净 runner 全过；tauri build 产出 DMG artifact
- [x] 文档/文案一致：UI 无"GPU 加速"字样；RELEASE/CHANGELOG 与 v0.2.0 实际一致
- [x] 回归：`cargo build --release` + `cargo test` + `tsc -b && vite build` 全通过；红线合规（CLI 配置只读、会话文件零写入）

## 转卡计划

```ccc-plan
title: clwarp 0.3.0 缺陷收口与兑现（设置接线 / CSS 重建 / 终端生命周期 / CSP / 工程化修绿）
project: clw
slices:
  - title: "设置面板接线 + 配置真实消费（P0 根修）"
    slug: settings-wiring
    executor: OpenCode
    acceptance:
      - "删除 src/components/SettingsPanel.tsx 空壳，App.tsx 改引 src/SettingsPanel.tsx 真实现（load_settings/save_settings/board_url/workspace_paths/layout 全接线）"
      - "设置保存后即时生效：board_url 改动后看板 iframe 立即按新 URL 加载，不再提示重启生效；保存落盘 ~/.clwarp/config.json"
      - "workspace_paths 接入 spawn_terminal 新会话默认 cwd，或明确从设置面移除（避免假配置）；layout 接入布局应用或移除"
      - "补 SettingsPanel 组件测试（mock load/save）"
      - "回归：tsc -b && vite build + cargo build --release 通过；不修改用户 CLI 配置、会话文件零写入"
    whitelist:
      - "src/App.tsx"
      - "src/components/SettingsPanel.tsx"
      - "src/SettingsPanel.tsx"
      - "src-tauri/src/settings.rs"
      - "src-tauri/src/lib.rs"
      - "src/App.test.tsx"
  - title: "CSS/主题层重建（P0 根修：清模板 + 真实样式层 + token + 深色）"
    slug: css-theme-rebuild
    executor: OpenCode
    acceptance:
      - "App.css/index.css 的 Vite 模板类（.counter/.hero/#next-steps/.ticks/.social 等）全部删除，无残留"
      - "应用实际使用的 35+ 类（app-container/sidebar/resize-handle/main-view/header-panel/footer-panel/provider-group/session-item/git-badge/spinner/alert-error 等）全部有样式定义"
      - "布局正常：app-container flex 行、sidebar 固定宽可拖拽（resize-handle 有宽度+cursor:col-resize+防选）、main-view 撑满、终端 height:100% 不塌缩"
      - "主题 token（CSS 变量）定义 --primary-color/--error-color/--warning-color/--text-muted 等已引用变量，深色模式生效；xterm 主题从 token 注入"
      - "index.css 删除 #root{width:1126px;text-align:center}；窗口默认 1000×700（tauri.conf.json）"
      - "模板残留文件清理：src/assets/hero.png、react.svg、vite.svg、public/icons.svg、public/favicon.svg（换应用图标）"
      - "回归：tsc -b && vite build 通过"
    whitelist:
      - "src/App.css"
      - "src/index.css"
      - "src/App.tsx"
      - "src/components/*.tsx"
      - "src/Terminal.tsx"
      - "src/SettingsPanel.tsx"
      - "src-tauri/tauri.conf.json"
      - "src/assets/"
      - "public/"
  - title: "终端生命周期修复（StrictMode 泄漏 / 视图切换杀会话 / loading 死锁 / 事件时序）"
    slug: terminal-lifecycle
    executor: OpenCode
    acceptance:
      - "StrictMode 双挂载不再泄漏 PTY：dev 模式重复打开/切换终端后无残留 claude/codex/opencode 子进程（进程数验证）"
      - "切看板/设置不杀终端会话：TerminalView 卸载不清 session，切回后现场保留；header 的 activePtyId/sessionToResume 与真实会话状态联动（会话退出后清理）"
      - "spawn 失败 loading 消失：handleSessionCreated 成功/失败都 setLocalLoading(false)，友好错误可见（不被 spinner 遮挡）"
      - "事件时序修复：spawn 完成、会话入表、读线程就绪后再返回；spawn 后初始输出不丢失、秒退会话正确收尾（无已连接假象）"
      - "死命令清理：read_from_terminal/set_window_size/kill_session 从注册与实现移除（前端已用事件推送/resize_terminal/kill_terminal）"
      - "回归：tsc -b && vite build + cargo build --release 通过"
    whitelist:
      - "src/Terminal.tsx"
      - "src/App.tsx"
      - "src/components/TerminalView.tsx"
      - "src-tauri/src/terminal.rs"
      - "src-tauri/src/lib.rs"
      - "src/main.tsx"
  - title: "CSP/看板/配置健壮性（CSP 动态化 / 原子写 / HOME 去硬编码 / PATH 缓存）"
    slug: csp-config-hardening
    executor: OpenCode
    acceptance:
      - "CSP frame-src/connect-src 跟随 config 的 board_url（或统一代理看板请求），改 board_url 后 iframe 不被拦；script-src 去掉 unsafe-eval"
      - "看板 iframe 加 loading/失败态 + sandbox，白屏有反馈"
      - "配置原子写：save_settings 用 tmp+rename，load 解析失败自动备份重建不丢数据"
      - "HOME 全量去硬编码：settings.rs/session.rs 统一 dirs::home_dir()，无 /Users/fan 兜底；board_url 默认值文档化（不散落硬编码）"
      - "登录 PATH 一次性解析+缓存（state 级）+超时：spawn/resume 不再每次跑 $SHELL -lc，profile 挂起有超时兜底"
      - "回归：cargo build --release + cargo test 通过"
    whitelist:
      - "src-tauri/tauri.conf.json"
      - "src-tauri/src/settings.rs"
      - "src-tauri/src/session.rs"
      - "src-tauri/src/terminal.rs"
      - "src/App.tsx"
      - "src-tauri/capabilities/default.json"
  - title: "工程化修绿 + 分发（CI 真绿 / 测试补强 / 签名 / 死代码清理）"
    slug: eng-green-dispatch
    executor: OpenCode
    acceptance:
      - "CI 修绿：git_status.rs 测试改纯函数/临时目录不依赖本机路径；settings.rs 测试用 tempfile 隔离；cargo test + clippy -D warnings 在干净 runner 全过"
      - "CI 产出 DMG：tauri build 去掉 --no-bundle，上传 DMG artifact；加 cargo cache + --locked"
      - "前端测试补强：SessionList 分组/折叠、SettingsPanel 保存、TerminalView 挂载/卸载真实用例（mock event API + xterm resize）"
      - "死代码清理：@xterm/addon-fit 死依赖确认去留；cargo clippy -D warnings 清零"
      - "签名与分发：signingIdentity+notarization 配置或 spctl 说明；可选 tauri-action 自动 Release"
      - "回归：cargo test + tsc -b && vite build + lint 全通过"
    whitelist:
      - ".github/workflows/ci.yml"
      - "src-tauri/src/git_status.rs"
      - "src-tauri/src/settings.rs"
      - "src/App.test.tsx"
      - "package.json"
      - "src-tauri/Cargo.toml"
      - "src-tauri/tauri.conf.json"
  - title: "文档/文案一致性（去 GPU 字样 / i18n 补全 / RELEASE 对齐）"
    slug: docs-copy-consistency
    executor: OpenCode
    acceptance:
      - "i18n 副标题去 GPU 加速字样（xterm.js 如实）；App.tsx 设置按钮关闭态独立文案（不再复用✕终止）、看板按钮文案进 i18n"
      - "formatDate 传 zh-CN；index.html lang=zh-CN"
      - "RELEASE.md 指向 v0.2.0 交付报告（现指向 v0.1.0 且声称 Metal GPU）；CHANGELOG 与实现一致"
      - "回归：tsc -b && vite build 通过"
    whitelist:
      - "src/i18n/index.ts"
      - "src/App.tsx"
      - "index.html"
      - "RELEASE.md"
      - "CHANGELOG.md"
```

## 备注

- **顺序依赖**：A → B → C 是"假功能变真功能"主线，必须按序；D 可在 C 后并行；E、F 收口最后
- **探查依据**：三路 Agent 深度审查报告（Rust 后端 22 项 / 前端 26 项 / 工程化对照 12 项），本方案只收 P0/P1 + 关键 P2，P3 观察项（opencode 时间戳单位、UTF-8 尾字节丢弃等）留 0.4.0
- **跨仓**：业务代码在 clwarp（`/Users/fan/program/apps/clwarp`），卡验收含业务仓分支 push + 合入收口
- **流程红线**：执行体报「已回写」前必须自测核心链路可跑；卡已关闭必须与代码合入 clwarp main 强绑定（杜绝 clw004/005 孤岛重演）
- **范围外**：Linux 多端适配、远程会话中继（WebRTC/SSE）、daemon 服务化拆分——均不在 0.3.0
