# 方案 · clwarp 0.2.0 全量重构（真实可用 + 兑现声明）

> 项目：clw · 编号：clw-plan-002 · 状态：已完成 · 作者：OpenCode（中枢） · 工具：OpenCode
> 创建：2026-08-10 · 更新：2026-08-10
> 关联卡：clw008, clw009, clw010, clw011, clw012
> 关联方案：clw-plan-001（已完成的 v0.1.0 骨架方案）
> 进度：5/5 (100%)

## 目标

把 clwarp 从「能编译、能跑通、声明大于实际」的 v0.1.0 原型，重做为一个**真实可用、声明与代码对齐、工程化健全**的 v0.2.0 桌面驾驶舱。核心链路（启动会话、终端交互、会话切换、设置、看板）在用户实测下必须真正可用，不再出现"打开后功能没实现"。

## 背景

老板实测 v0.1.0（2026-08-10 交付）反馈：功能未实现、UI 与组件问题多、不完善。经三路 Agent 深度审计（Rust 后端 / 前端 UI / 工程化对照），交叉印证核心结论：

**声明的 8 项能力，实际只有 5 项真实存在，其中 2 项完全缺失、1 项名不副实、1 项虚报：**

| 声明功能 | 实际 | 结论 |
|---------|------|------|
| GPU 终端 / Metal 原生渲染 | 实际 xterm.js CPU 渲染，alacritty 仅当 PTY | ❌ 名不副实 |
| spawning CLI 会话 | provider 真实 spawn claude/codex/opencode | ✅ 真实 |
| persisting 会话 | 应用零写入，只读 CLI 历史 | ❌ 虚报 |
| 响应式侧边栏 + 历史会话树 | 真实渲染（读三工具会话） | ✅ 真实 |
| Git 状态指示器 | 真实跑 git 命令 | ✅ 真实 |
| 内嵌 CCC 看板 WebView | clw004 分支**从未合入 main** | ❌ 空壳 |
| 交互式设置面板 + 持久化 | clw005 分支**从未合入 main** | ❌ 空壳 |
| DMG 打包 | 配置在但图标为占位、无签名 | ⚠️ 部分 |

**流程问题**：clw004/clw005 卡被标「已关闭」、方案验收全勾、交付报告声称通过——但代码根本没在 main 上。卡关闭与代码落地无强绑定，孤岛式交付。

**P0 级可用性问题**：
- GUI 启动 PATH 极简，`claude`/`codex`/`opencode` 裸命令找不到 → 恢复会话确定性失败（Finder 双击启动的头号故障）
- dev 模式必挂：tauri devUrl=1420 但 vite 默认 5173，端口不匹配白屏
- 终端 10ms 轮询（100 IPC/秒/会话）、无 resize（锁死 80×24）、无退出检测（EOF 后空转刷错）、「终止」实际重启会话、StrictMode 双挂载泄漏子进程
- CSP=null、双 xterm 版本死依赖、HOME 硬编码 `/Users/fan`、图标全占位、Vite 模板 CSS 残留、无 CI、Rust 仅 1 单测

**借鉴基准**：Paseo（`github.com/getpaseo/paseo`，同一赛道成熟项目：统一管理 Claude Code/Codex/Copilot/OpenCode/Pi 会话）已调研，可借鉴其成熟解法：
- `login-shell-env.ts`（VS Code 移植）：登录 shell 环境解析，解决 GUI PATH 问题
- `executable-resolution.ts`：agent 可执行文件解析（PATH/常见安装目录探测）
- `terminal-session-controller.ts`：kill 带 exit 事件推送、resize payload 处理、进程组清理
- `agent-hooks/provider-registry.ts`：多 provider 统一抽象
- daemon + WebSocket 事件推送：替代轮询的成熟模式（clwarp 远期方向，0.2.0 先落地事件推送不引入 daemon 拆分）

## 方案内容

按五块推进，每块一张卡，顺序依赖（先 P0 可用性 → 终端 → UI → 功能补齐 → 工程化收口）：

**切片 A · P0 执行链修复**：解决「打开后会话起不来」的头号根因。
- GUI 环境登录 shell 解析（借鉴 Paseo login-shell-env / VS Code shellEnv）：spawn CLI 前用登录 shell 导出 PATH（含 `~/.local/bin`、`/opt/homebrew/bin`、nvm 等）
- 修 dev 端口：vite.config.ts 配 `server.port: 1420` 或 tauri devUrl 对齐 5173
- 修复「终止=重启」：终止只 kill，不触发重新 spawn
- StrictMode 双挂载泄漏修复（unmount 时 kill 未完成的 spawn）
- HOME 回退去硬编码（用 `dirs`/`home` crate 或 `user_home`）

**切片 B · 终端链路重做**：从"能显示、不可用"到"真可用"。
- 10ms 轮询改 Tauri Event 推送：后端常驻读循环 → `emit` 输出/退出事件；前端订阅。保留 read command 作为 fallback
- 补 resize：后端 `set_window_size` command（PTY TIOCSWINSZ，alacritty 已提供 OnResize）+ 前端 `@xterm/addon-fit`
- 子进程退出检测：PTY EOF 或 waitpid 后 emit `exit` 事件，前端停止轮询、清 loading、非冻结
- 进程组清理：setsid 启动 agent，kill 时杀整个进程组（防孤儿孙进程）；kill 失败不阻塞
- 修复 UTF-8 多字节块边界乱码（读循环按完整字符边界解码）
- 移除 xterm@5.3.0 死依赖，只留 @xterm/xterm

**切片 C · 前端 UI 重建**：从"内联样式原型"到"产品 UI"。
- 清 Vite 模板残留：App.css/index.css 模板类、assets/react.svg、vite.svg、hero.png
- 组件体系：拆分 App 巨型组件为 Sidebar / SessionList / SessionItem / GitBadge / TerminalView / SettingsPanel，主题 token（CSS 变量），深色模式
- 布局：响应式（可拖拽分栏）、minWidth、修复 80×24 放不下裁切问题
- 补 loading 态、错误展示友好化（不糊原始 Rust 错误串）
- i18n 补全：Terminal.tsx 硬编码中文收进 i18n，formatDate 不再硬编码 zh-CN
- 无障碍基础：aria-label、button type、focus 样式

**切片 D · 兑现缺失声明（看板 + 设置面板）**：
- CCC 看板内嵌：实现 WebView 窗口/嵌入组件加载看板 URL（URL 从 `~/.clwarp/config.json` 读，不硬编码 IP；默认值可给 192.168.3.116:7788），配 CSP 白名单
- 设置面板 + 持久化：`~/.clwarp/config.json`（读写 workspace 路径、看板 URL、布局偏好），`load_settings`/`save_settings` commands，前端 SettingsPanel
- 删除或降级不实声明：CHANGELOG/README/RELEASE 的"GPU/Metal"改为"xterm.js 渲染"；"persisting sessions"如实描述为"读取 CLI 历史会话"

**切片 E · 工程化基座 + 流程收口**：
- CSP 从 null 改为白名单（允许看板端点 + tauri://localhost）
- 换正式图标（不再 Tauri 占位）
- 补 CI（GitHub Actions：lint + test + build + 打包）与测试（Rust 核心单测、前端 vitest）
- 修复 `npm run tauri dev` 链路（package.json 加 tauri script + @tauri-apps/cli）
- CHANGELOG/README/RELEASE 声明与实际全面对齐；方案验收标准「以实测为准」

## 验收标准

- [x] P0 链路：Finder 双击启动 .app 后，Claude/Codex/OpenCode 三类会话可 spawn 与 resume（真实拉起 CLI，非 command not found）
- [x] dev 模式：`npm run tauri dev` 可正常打开窗口（端口一致）
- [x] 终端交互：输入输出正常、resize 后 PTY 跟随窗口、进程退出后终端自动收尾不冻结不刷错、终止不再重启会话
- [x] 无 10ms 轮询：终端输出走事件推送；退出后无残留 IPC
- [x] UI：模板残留清除、组件化、深色模式、窗口可缩放无裁切、loading/错误态友好
- [x] 看板内嵌 + 设置面板真实存在并持久化（`~/.clwarp/config.json` 读写验证）
- [x] 文档声明与代码一致：CHANGELOG/README/RELEASE 不再声称不存在的 GPU/持久化能力
- [x] 工程化：CSP 白名单生效、正式图标、CI 跑通、Rust+前端测试覆盖核心链路
- [x] 回归：`cargo build --release`、`cargo test`、`tsc -b && vite build` 全通过；红线合规（CLI 配置只读、会话文件零写入）

## 转卡计划

```ccc-plan
title: clwarp 0.2.0 全量重构（真实可用 + 兑现声明）
project: clw
slices:
  - title: "P0 执行链修复（GUI PATH / dev 端口 / 终止重启 / 泄漏 / HOME）"
    slug: p0-exec-chain-fix
    executor: OpenCode
    acceptance:
      - "GUI 环境登录 shell 解析：spawn CLI 前以登录 shell 环境（含 ~/.local/bin、/opt/homebrew/bin、nvm）解析 PATH；Finder 双击启动 .app 后 claude/codex/opencode 可正常拉起（真实 shell 验证，非 command not found）"
      - "dev 模式：npm run tauri dev 打开窗口正常（vite 端口与 tauri devUrl 一致，无白屏）"
      - "「终止会话」只 kill 不重新 spawn（点击终止后终端消失，不再出现新裸 shell）"
      - "StrictMode/卸载不泄漏子进程：重复挂载卸载后无残留 agent 进程"
      - "HOME 回退不再硬编码 /Users/fan（用系统 API 取真实用户目录）"
      - "回归：cargo build --release + cargo test + tsc -b && vite build 通过；不修改用户 CLI 配置、会话文件零写入"
    whitelist:
      - "src-tauri/src/lib.rs"
      - "src-tauri/src/provider.rs"
      - "src-tauri/src/terminal.rs"
      - "src-tauri/src/session.rs"
      - "src/App.tsx"
      - "src/Terminal.tsx"
      - "vite.config.ts"
      - "package.json"
      - "src-tauri/Cargo.toml"
  - title: "终端链路重做（事件推送 / resize / 退出检测 / 进程组清理 / UTF-8）"
    slug: terminal-overhaul
    executor: OpenCode
    acceptance:
      - "终端输出走 Tauri Event 推送（后端常驻读循环 emit 输出与退出事件），前端订阅；不再有 10ms 轮询 invoke"
      - "窗口 resize 后 PTY 尺寸跟随（set_window_size command + 前端 fit），80 列不再锁死裁切"
      - "子进程退出后终端自动收尾：emit exit 事件、前端清 loading 停接收、画面不冻结、console 不刷 EOF 错误"
      - "kill 走进程组清理（setsid + 组内全杀），agent 孙进程不残留孤儿；kill 不阻塞 UI"
      - "多字节 UTF-8 输出（中文）块边界不乱码（\uFFFD 不再出现）"
      - "移除 xterm@5.3.0 死依赖，仅保留 @xterm/xterm"
      - "回归：cargo build --release + cargo test + tsc -b && vite build 通过"
    whitelist:
      - "src-tauri/src/terminal.rs"
      - "src-tauri/src/lib.rs"
      - "src/Terminal.tsx"
      - "package.json"
  - title: "前端 UI 重建（清模板 / 组件化 / 主题 / 响应式 / 状态友好）"
    slug: ui-rebuild
    executor: OpenCode
    acceptance:
      - "Vite 模板残留清除：App.css/index.css 模板类、assets/react.svg、vite.svg、hero.png 全部删除或移除引用"
      - "组件化：App 巨型组件拆分为 Sidebar / SessionList / SessionItem / GitBadge / TerminalView / SettingsPanel；无重复 inline style 堆叠"
      - "主题 token（CSS 变量）+ 深色模式；窗口可缩放（minWidth/minHeight、可拖拽分栏），终端 80 列在默认窗口不裁切"
      - "会话启动有 loading 态；失败显示友好错误文案（不糊原始 Rust 错误串）"
      - "i18n 补全：Terminal.tsx 硬编码中文收进 i18n，formatDate 不硬编码 zh-CN；index.html lang=zh-CN"
      - "无障碍基础：按钮 aria-label/type、focus 样式"
      - "回归：tsc -b && vite build 通过，cargo build --release 通过"
    whitelist:
      - "src/App.tsx"
      - "src/App.css"
      - "src/index.css"
      - "src/Terminal.tsx"
      - "src/i18n/index.ts"
      - "index.html"
      - "src/main.tsx"
  - title: "兑现缺失声明（CCC 看板内嵌 + 设置面板持久化）"
    slug: webview-settings
    executor: OpenCode
    acceptance:
      - "CCC 看板内嵌真实存在：WebView 组件加载看板 URL（URL 从配置目录的 config.json 读取，默认值为看板端点，不硬编码在代码里），侧边栏有入口可打开"
      - "设置面板真实存在：前端 SettingsPanel 与后端 load_settings/save_settings 命令，读写配置目录的 config.json（workspace 路径、看板 URL、布局偏好），改后重启生效"
      - "CSP 白名单允许看板端点与 tauri 本地域名（不再关闭 CSP）"
      - "文档声明对齐：CHANGELOG/README/RELEASE 中 GPU/Metal 改为 xterm.js 渲染、persisting 如实描述为读取 CLI 历史会话，不再声称不存在的『GPU 原生渲染』『应用自身持久化』"
      - "回归：cargo build --release + cargo test + tsc -b && vite build 通过；~/.clwarp/config.json 读写验证"
    whitelist:
      - "src-tauri/src/lib.rs"
      - "src-tauri/src/settings.rs"
      - "src/App.tsx"
      - "src/SettingsPanel.tsx"
      - "src-tauri/tauri.conf.json"
      - "src-tauri/capabilities/default.json"
      - "CHANGELOG.md"
      - "README.md"
      - "RELEASE.md"
  - title: "工程化基座（CSP / 图标 / CI / 测试 / 开发链路）"
    slug: eng-foundation
    executor: OpenCode
    acceptance:
      - "CSP 从 null 改为白名单（允许看板端点与 tauri 本地域名），capabilities 权限明确"
      - "正式图标替换 Tauri 占位（icon 全家桶）"
      - "CI 落地：GitHub Actions（lint + test + build + 打包 workflow）可在仓库跑通"
      - "测试补齐：Rust 核心链路单测（session 解析 / provider 命令构造 / git_status）、前端 vitest（关键组件）"
      - "开发链路修复：package.json 含 tauri script 与 @tauri-apps/cli，README/CLAUDE.md 命令可复跑"
      - "回归：cargo test + tsc -b && vite build + lint 全通过"
    whitelist:
      - ".github/workflows/ci.yml"
      - "package.json"
      - "src-tauri/tauri.conf.json"
      - "src-tauri/capabilities/default.json"
      - "src-tauri/src/*.rs"
      - "src/*.tsx"
      - "README.md"
      - "CLAUDE.md"
      - "AGENTS.md"
```

## 备注

- **顺序依赖**：A → B → C 是可用性主线，必须按序；D 可在 C 之后并行；E 收口最后
- **借鉴 Paseo**：切片 A 的 PATH 解析、切片 B 的 exit 事件/resize/进程组清理，直接参考 Paseo `login-shell-env.ts`、`executable-resolution.ts`、`terminal-session-controller.ts`（本仓已下载源码在临时目录，可对照）
- **GPU/Metal 声明**：0.2.0 明确降级为 xterm.js 渲染；真正 GPU 渲染（alacritty renderer / egui）留待后续版本独立方案评估
- **流程红线**：本方案转卡后，卡「已关闭」必须与代码合入 main 强绑定（验收含 main 上代码证据），杜绝 clw004/005 孤岛式交付重演
- **风险**：事件推送改造涉及前后端协议改动，切片 B 需保证与既有 invoke 接口兼容期
- **范围外**：Linux 多端适配、远程会话中继（WebRTC/SSE）、daemon 服务化拆分——均不在 0.2.0，留待后续方案
