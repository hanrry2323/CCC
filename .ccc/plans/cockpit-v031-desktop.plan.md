# Plan: cockpit-v031-desktop — Cockpit v0.31.0 Tauri 桌面端

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

CCC Chat Server 是一个 FastAPI 单文件应用（`scripts/ccc-chat-server.py`，1260 行），绑定 `:8084`，
在内联 HTML_UI 变量中自包含 Chat/Execute/Board 三模式的前端。无静态文件、无构建步骤。
当前运行依赖 `python3` + `uvicorn`。

开源参考 [cdesktop](https://github.com/cdesktop-ai/cdesktop) 提供了类似的 Tauri 包装模式。

- **入口/核心文件**：
  - `scripts/ccc-chat-server.py`（1260 行）— FastAPI 单文件应用，内联 HTML_UI
  - `src-tauri/Cargo.toml` — **新建**：Rust 项目配置
  - `src-tauri/tauri.conf.json` — **新建**：Tauri 应用配置
  - `src-tauri/src/main.rs` — **新建**：Rust 入口，侧载 Python 服务 + 原生功能
  - `package.json` — **新建**：前端包管理（Tauri CLI 脚本）
  - `scripts/ccc-tauri-dev.sh` — **新建**：开发快捷启动脚本
  - `scripts/install-tauri-rust.sh` — **新建**：Rust 工具链安装脚本

- **当前结构要点**：
  - Chat Server 是独立 FastAPI 进程，通过 `uvicorn.run()` 启动
  - 前端全内联，无需构建、无静态文件分发
  - 无已有的 Tauri / Electron / 桌面包装代码
  - 本机有 `npx @tauri-apps/cli`（v1.6.3），但无 Rust 工具链（`rustc` 未安装）
  - Mac 2017（`192.168.3.116`）有 Rust 工具链，可用于编译

- **待改动点**：
  - 项目根新建 `src-tauri/` 目录 + `package.json`
  - Tauri 窗口指向 `http://127.0.0.1:8084`
  - 启动时自动 spawn Python Chat Server 子进程（sidecar 模式）
  - 关闭窗口时清理子进程
  - macOS 原生菜单、系统托盘、通知
  - 离线缓存（WebView localStorage）
  - 开机自启动（LaunchAgents）

---

## 范围

- **目标**：用 Tauri v1 将 CCC Chat Server 包装为 macOS 桌面应用，
  用户双击即可打开原生窗口使用 Chat/Execute/Board，无需手动启动 Python 服务
- **只改文件**：
  - `scripts/ccc-chat-server.py`（极小改动：导出 main() 供 sidecar 稳定启动）
  - 以下为**新建**文件：
    - `src-tauri/Cargo.toml`
    - `src-tauri/tauri.conf.json`
    - `src-tauri/src/main.rs`
    - `src-tauri/src/menu.rs`
    - `src-tauri/src/server.rs`
    - `src-tauri/build.rs`
    - `src-tauri/icons/`（应用图标目录）
    - `package.json`
    - `scripts/cockpit-desktop.sh`（编译+运行入口）
    - `scripts/ccc-tauri-dev.sh`
    - `scripts/install-tauri-rust.sh`
    - `.cargo/config.toml`（Rust 镜像加速）
    - `src-tauri/Info.plist`（macOS 原生配置）
    - `src-tauri/LaunchAgents/com.ccc.cockpit.plist`（开机自启）
- **不改文件**：
  - `.ccc/infrastructure.md`、`.ccc/state.md`、`.ccc/profile.md`
  - `scripts/ccc-cockpit.py`
  - `scripts/ccc-board.py`、`scripts/ccc-board-server.py`
  - 其他任何已有脚本、测试、模板、配置文件
  - `.env` 和密钥相关文件
- **执行方式**：`manual`
- **Phase 数**：3

---

## Phase 1：Tauri 项目脚手架 + Rust 工具链

### 做什么

搭建 Tauri v1 桌面应用的基础骨架：安装 Rust 工具链、创建 `src-tauri/` 目录结构、
初始化 Cargo.toml 和 tauri.conf.json、配置前端 package.json、
生成 macOS 应用图标占位文件、设置 `.cargo/config.toml` 镜像加速。
此 phase 结束后 `npx tauri dev` 应能打开一个空白 Tauri 窗口。

### 怎么做

**1. 安装 Rust 工具链**（新建 `scripts/install-tauri-rust.sh`）：

```bash
#!/usr/bin/env bash
# install-tauri-rust.sh — 安装 Rust 工具链（Tauri 依赖）
set -euo pipefail
if command -v rustc &>/dev/null; then
  echo " Rust 已安装: $(rustc --version)"
  exit 0
fi
echo " 安装 Rust 工具链..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
echo " Rust $(rustc --version) 安装完成"
# 添加 macOS 目标
rustup target add aarch64-apple-darwin x86_64-apple-darwin
```

**2. 创建 `src-tauri/Cargo.toml`**：

- 包名：`ccc-cockpit-desktop`
- 版本：与 CCC 主版本一致（当前 v0.29.0）
- 依赖：`tauri` v1.x（features = `["shell-open", "notification-all", "dialog-all"]`）、`tauri-plugin-shell`、`tauri-plugin-notification`、`serde` + `serde_json`
- 配置 cargo 缓存路径到项目 `.cargo/` 目录

**3. 创建 `src-tauri/tauri.conf.json`**：

- `build.devPath`: `"http://127.0.0.1:8084"`（开发模式指向运行中的 chat-server）
- `build.distDir`: 同上（Tauri v1 要求 distDir 指向本地地址或静态目录）
- `tauri.window`: 标题 "CCC Cockpit"，宽 1200×800，可缩放，最小 800×600
- `tauri.allowlist`: 启用 shell（用于启动 python 子进程）、notification、dialog
- `tauri.bundle.identifier`: `com.ccc.cockpit`
- `tauri.bundle.category`: `DeveloperTool`
- `tauri.security`: `csp: "default-src 'self'; connect-src 'self' http://127.0.0.1:8084; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data: asset: http://127.0.0.1:*"`
- `tauri.systemTray`: 启用（v1 通过配置或代码创建）
- 添加 `tauri.bundle.macOS` 配置：`minimumSystemVersion: "12.0"`

**4. 创建 `src-tauri/src/main.rs`**（最小骨架）：

- 标准 Tauri main()
- 空白的 `tauri::Builder` 初始化
- 注册菜单处理命令
- 编译通过即可

**5. 创建 `package.json`**（项目根）：

- 名称 `ccc-cockpit-desktop`
- scripts: `"tauri": "npx @tauri-apps/cli"`
- devDependencies: `@tauri-apps/cli` ^1.6.0

**6. 创建 `.cargo/config.toml`**：

- 配置国内镜像源（中科大或 RsProxy）加速 Rust crate 下载
- `[source.crates-io]` → `replace-with = "rsproxy"`
- `[source.rsproxy]` → registry 指向 `https://rsproxy.cn/crates.io-index`

**7. 创建 `src-tauri/build.rs`**：

- 标准 Tauri v1 build.rs：`fn main() { tauri_build::build() }`

**8. 创建应用图标**：

- 生成一个最小占位图标：使用 Python 生成 1024×1024 PNG
- 用 `iconutil` 或 Python Pillow 生成 `.icns` 文件
- 输出到 `src-tauri/icons/` 目录
- 图标内容：CCC 三个字母风格化，或简单命令行终端图标

**9. 验证编译**：

- `npm install`（安装 tauri CLI）
- `npx tauri build --debug`（或 `npx tauri build`，看 Rust 编译是否通过）
- 注意：此时代码未完成（`main.rs` 尚未实现 sidecar 启动），仅验证 Cargo.toml + tauri.conf.json 结构和编译链

### 验收清单

- [ ] Rust 工具链已安装（rustc、cargo 可用）
- [ ] `src-tauri/` 目录结构完整
- [ ] `npm install` 成功，无依赖错误
- [ ] `npx tauri build --debug` 编译通过，产生 `.app` bundle（未签名）
- [ ] 双击生成的 .app 能打开一个空白 Tauri 窗口
- [ ] `.cargo/config.toml` 镜像配置正确（cargo build 下载快速）
- [ ] `scripts/install-tauri-rust.sh` 可重复运行（幂等）

---

## Phase 2：Python 服务侧载 + WebView 集成

### 做什么

实现 Tauri 应用的核心功能：启动时自动 spawn `python3 scripts/ccc-chat-server.py` 子进程，
等待服务就绪后 WebView 加载 `http://127.0.0.1:8084`，关闭窗口时自动 kill 子进程。
用户双击应用即可使用 CCC Chat Server，无需手动启动 Python。

### 怎么做

**1. 修改 `src-tauri/src/main.rs`** — 侧载逻辑：

- 在 `tauri::Builder::default().setup()` 回调中：
  - 获取当前 exe 所在目录的同级 `scripts/ccc-chat-server.py` 路径
  - 使用 `std::process::Command` spawn Python 子进程：`python3 <path>/scripts/ccc-chat-server.py`
  - 注意 shell 特性：`process_group(0)` 确保 kill 时整个进程组退出
  - 将子进程句柄存入 `app.manage(ServerState { child: Mutex::new(child) })`
- 轮询等待：循环检查 `http://127.0.0.1:8084` 是否返回 200（最多重试 30 次，间隔 500ms）
  - 超时则弹错误对话框 "Chat Server 启动失败，请检查 Python 环境"
- 启动成功后 WebView 自动加载 `http://127.0.0.1:8084`

**2. 实现优雅退出**（`main.rs` 的 `on_window_event` 或 `Drop`）：

- 窗口关闭时：kill 子进程（`child.kill()` + `child.wait()`）
- 使用 `std::panic::set_hook` 兜底：panic 时也尝试 kill 子进程防止僵尸
- 用 `libc::kill(-pid, SIGTERM)` 或 `process_group` 确保整个进程树退出

**3. 配置 `tauri.conf.json` 更新**：

- `tauri.allowlist.shell.open: true`（允许打开外部 URL）
- 确认 CSP 允许连接 `http://127.0.0.1:8084`

**4. 新建 `src-tauri/src/server.rs`**（解耦侧载逻辑）：

- 把 Python 进程管理从 `main.rs` 拆分到独立模块
- 结构：
  ```rust
  pub fn start_server() -> io::Result<Child> { ... }
  pub fn wait_ready(child: &mut Child) -> bool { ... }
  pub fn stop_server(child: &mut Child) { ... }
  ```

**5. 错误处理路径**：

- Python 未安装：弹出对话框 "Python3 未找到，请安装 Python 3.11+"
- 端口被占用：弹出对话框 "端口 8084 已被占用，请检查是否有其他 CCC Chat Server 在运行"
- 启动超时（30 次重试后）：弹框提示并提供重试/退出选项

**6. 修改 `scripts/ccc-chat-server.py`**（极小改动）：

- 确保 `main()` 函数可被反复安全调用（当前已满足）
- 增加 `--port` 参数支持（当前从常量读取，改为 argparse 或 env 覆写）
- 增加 `--no-open` 参数（不自动打开浏览器）
- 这样 sidecar 可以指定端口避免冲突

**7. 新建 `scripts/cockpit-desktop.sh`**：

- 编译+运行入口脚本
- 在开发环境下方便启动完整桌面应用
- `npm run tauri dev`

### 验收清单

- [ ] Tauri 启动后自动 spawn python3 子进程运行 chat-server
- [ ] 子进程就绪前显示加载指示（或白屏等待）
- [ ] 子进程就绪后 WebView 正常加载 Chat Server 页面
- [ ] Chat/Execute/Board 三模式在桌面窗口中全部可用
- [ ] 关闭窗口后 Python 子进程被杀（`ps aux | grep chat-server` 检查）
- [ ] 端口 8084 被占用时优雅提示退出
- [ ] Python 未安装时弹出错误提示
- [ ] 快速连续开关应用不发生僵尸进程

---

## Phase 3：原生功能 — 菜单 / 通知 / 托盘 / 离线缓存 / 自启

### 做什么

添加 macOS 原生桌面体验：应用菜单栏（文件/编辑/视图/帮助）、
系统托盘图标（右键菜单：显示/隐藏/退出）、
Tauri 原生通知（当任务完成或服务告警时推送）、
WebView localStorage 离线缓存（历史会话断网可用）、
开机自启动（LaunchAgents plist 安装脚本）。

### 怎么做

**1. 新建 `src-tauri/src/menu.rs`** — 原生菜单：

- 使用 `tauri::Menu` API 自定义菜单栏：
  - 应用菜单（CCC Cockpit）：关于、偏好设置...、分隔线、退出
  - 文件（File）：新建会话 Cmd+N、保存 Cmd+S、分隔线、关闭窗口 Cmd+W
  - 编辑（Edit）：标准 撤销/重做/剪切/复制/粘贴/全选
  - 视图（View）：重新加载 Cmd+R、开发者工具 Cmd+Shift+I、分隔线、放大/缩小
  - 窗口（Window）：最小化、缩放
  - 帮助（Help）：关于 CCC Cockpit、GitHub 仓库
- 菜单事件处理：匹配 menu event id，执行对应 JS 或 Rust 操作
  - "reload" → 刷新 WebView
  - "devtools" → `window.open_devtools()`
  - "new-session" → 向 WebView 发送 new-session 事件

**2. 系统托盘**（`main.rs` 或 `menu.rs`）：

- 在 `tauri::Builder` 中创建 SystemTray：
  - 图标：使用 CCC 小图标
  - 右键菜单：显示/隐藏窗口、分隔线、退出
  - 左键单击：切换窗口显示/隐藏
- 事件处理：
  - `SystemTrayEvent::LeftClick`: 切换窗口可见性
  - `SystemTrayEvent::MenuItemClick("quit")` → app 退出
  - `SystemTrayEvent::MenuItemClick("show")` → 显示并聚焦窗口

**3. 原生通知**（`main.rs` 或 `menu.rs`）：

- 注册 Tauri 命令 `notify_user(title: String, body: String)`：
  - 使用 `tauri::api::notification::Notification` 发送 macOS 通知
  - 点击通知跳回应用窗口
- 在 WebView 中通过 `invoke` 调用通知：
  - 注入一段 JS 到 chat-server 的 HTML 中（通过 Tauri 初始化脚本）：
  - 检查 `window.__TAURI__` 是否存在
  - 若存在，在 Chat Server 原有通知逻辑上叠加 `window.__TAURI__.invoke('notify_user', ...)`
- 通知场景：任务执行完成、服务告警、长时间操作结束

**4. 离线缓存**：

- 在 WebView 中注入 Service Worker 或配置 localStorage 持久化：
  - Tauri WebView 的 localStorage 默认持久化到磁盘
  - 确认 `tauri.conf.json` 中无禁止 localStorage 的 CSP
  - 添加初始化脚本 `init.js`：注入 Tauri JS bridge 并启用离线模式检测
- 在 Chat Server HTML 中检测 Tauri 环境：
  - 若 `window.__TAURI__` 存在，页面显示 "桌面模式" 状态指示
  - 网络不可达时使用缓存会话数据

**5. 开机自启动**：

- 新建 `src-tauri/LaunchAgents/com.ccc.cockpit.plist`：
  - Label: `com.ccc.cockpit`
  - ProgramArguments: `/Applications/CCC\ Cockpit.app/Contents/MacOS/ccc-cockpit-desktop`
  - RunAtLoad: true
  - KeepAlive: false（不自动重启，用户主动打开）
  - StandardOutPath / StandardErrorPath → `~/Library/Logs/ccc-cockpit.log`
- 新建 `scripts/install-launchagent.sh`：
  - 复制 `.plist` 到 `~/Library/LaunchAgents/`
  - `launchctl load ~/Library/LaunchAgents/com.ccc.cockpit.plist`
  - 提供 `uninstall` 选项：`launchctl unload` + 删除 plist

**6. 构建配置更新**：

- `tauri.conf.json` 中：
  - `tauri.bundle.macOS.signing.identity`: 留空（开发者本地签名或 ad-hoc）
  - `tauri.bundle.macOS.entitlements`: 添加通知权限
- 设置应用版本同步 `VERSION` 文件

**7. 用户数据目录**：

- Tauri 应用数据目录默认为 `~/Library/Application Support/com.ccc.cockpit/`
- 将 chat server 的 `CHAT_DIR` 重定向到此目录（sidecar 启动时通过环境变量传递）
- 这样历史会话数据在 Tauri 模式下存储在标准 macOS 应用数据位置

### 验收清单

- [ ] 应用启动后有完整 macOS 菜单栏（CCC Cockpit / 文件 / 编辑 / 视图 / 窗口 / 帮助）
- [ ] 菜单快捷键工作正常（Cmd+R 刷新、Cmd+Shift+I 打开开发者工具）
- [ ] 系统托盘图标显示，右键菜单可用
- [ ] 左键点击托盘切换窗口显示/隐藏
- [ ] 原生通知发送成功（任务完成时推送）
- [ ] 离线模式下（断网）历史会话仍可查看
- [ ] 开机自启动 plist 安装后重启自动打开应用
- [ ] Tauri 应用数据目录存储历史会话（`~/Library/Application Support/com.ccc.cockpit/`）
- [ ] 开发者工具可打开（方便调试）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | 项目脚手架：src-tauri/ 目录、Rust 工具链、Cargo.toml、tauri.conf.json、package.json | `feat(cockpit): Tauri 桌面端 — 项目脚手架 (phase 1/3)` |
| 2 | 侧载集成：Python 子进程管理、WebView 加载、进程生命周期 | `feat(cockpit): Tauri 桌面端 — 侧载 Python 服务 (phase 2/3)` |
| 3 | 原生功能：菜单、托盘、通知、离线缓存、自启 | `feat(cockpit): Tauri 桌面端 — 原生功能 (phase 3/3)` |

规则：每个 phase 一个独立 commit，message 含 phase 编号。

---

## 全局验收清单

- [ ] Rust 编译通过（`npx tauri build --debug`）
- [ ] Tauri 应用打开后自动启动 Python Chat Server
- [ ] Chat/Execute/Board 三模式在桌面窗口中完整可用
- [ ] 关闭窗口后无残留进程
- [ ] 菜单、托盘、通知原生体验正常
- [ ] diff 范围仅限"只改文件"列表
- [ ] 每个 phase 对应一个独立 commit
- [ ] phases.json 与 plan phase 数一致（3 个）
- [ ] Plan 中所有验收意图全部达成
- [ ] Python 原版浏览器访问 `http://localhost:8084` 不受影响（backward compatible）

---

## 后续步骤

完成 P1-P3 后，CCC Chat Server 将拥有完整的 macOS 桌面体验。
后续方向：

| 方向 | 说明 | 优先级 |
|------|------|--------|
| P4: 构建自动化 | GitHub Actions 自动构建 + notarize macOS .dmg | 低 |
| P5: Sparkle 自动更新 | 集成 Sparkle 框架实现自动更新检查 | 低 |
| P6: Apple Silicon 原生 | 编译 universal binary（x86_64 + arm64） | 中 |
| P7: 多窗口支持 | 多个 Chat Server 会话窗口 | 低 |