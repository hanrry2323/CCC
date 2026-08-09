# 任务卡 clw004 · CCC WebView 面板 + 自动化入口（OpenCode 执行）

> 关联：ccc-plan: clw004 CCC WebView + 自动化 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：clw · 日期：2026-08-09

## 目标

CCC WebView 面板 + 自动化入口（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src-tauri/src/lib.rs`
- `src-tauri/src/webview.rs`
- `src-tauri/Cargo.toml`
- `src/App.tsx`
- `src/Terminal.tsx`
- `src/i18n/`
- `src-tauri/tauri.conf.json`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 侧边栏点击 CCC 面板项，主区显示内嵌 CCC 看板 WebView（/board 页面），可正常浏览看板列与卡片
2. 看板地址从配置读取（不硬编码 IP/端口；默认指向 CCC 部署节点 web 端点，见 docs/deploy/topology.md）
3. WebView 加载失败有中文错误提示与重试入口；不阻塞终端会话功能
4. 红线合规：不修改用户 CLI 配置；会话文件零写入；不写业务项目文件；数据目录 ~/.clwarp/ 隔离
5. 构建通过：cargo build --release + 前端 tsc -b && vite build 均 0 error

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 实现说明
1. **Rust 后端实现 (`src-tauri/src/webview.rs`)**:
   - 暴露 `get_ccc_board_url` 命令，优先从 `CCC_BOARD_URL` 环境变量读取看板地址，未找到时依次检索 `~/.clwarp/config.json` 与 `~/.clwarp/settings.json`，最后静默回退至 `http://192.168.3.116:7788`。
   - 暴露 `check_ccc_board_status` 命令，通过解析 URL 并利用 Rust 原生 `std::net::TcpStream::connect_timeout` (超时 1 秒) 高效验证服务是否可达，零外部网络依赖，绝不产生多余进程与写入。
   - 将此两命令注册并挂载于 `src-tauri/src/lib.rs` 中。
2. **前端界面实现 (`src/App.tsx`, `src/i18n/index.ts`)**:
   - 侧边栏（Sidebar）新增“CCC 看板”项，采用极富视觉质感的 clipboard 📋 徽标与色彩对齐方案。
   - 采用条件显隐方式 (`display`) 渲染 PTY 终端与 CCC 看板视图，在极速切换看板与终端的同时，**绝不阻塞、破坏或终结现有的 PTY 终端会话**。
   - 在加载 CCC 视图时，异步检测连接性，若服务未就绪，提供中文友好提示（服务未就绪、检查配置等），并赋予重试入口。若就绪则正常加载 `iframe` 内嵌 `/board` 看板页面，状态与样式无缝整合。

### 测试结果
- 前端构建成功：运行 `npm run build` 产出 0 error。
- 后端编译成功：运行 `cargo build --release` 产出 0 error。
- 代码风格检查：oxlint & cargo check 均无警告/报错。

### Push 证据
- 业务仓 `clwarp` 提交哈希 (commit hash): `43670535f7f30352d06fe0ae3c0f455cb3e7d51d`
- 业务仓推送分支: `codex/clw004-ccc-webview`

## 机审区

**机审**：2017 · 日期：2026-08-09

**机审：通过**（含一处就地修复）

审查范围：clw004 commit `be9c2c9..4367053`（clwarp，4 文件：`src/App.tsx` / `src/i18n/index.ts` / `src-tauri/src/lib.rs` / 新 `src-tauri/src/webview.rs`），均在卡声明范围，无越界文件；后端改动贴近实现说明 `43670535`。

验收逐条：
1. **看板面板** ✅ 侧边栏「CCC 看板」项切 `ccc` 视图内嵌 `iframe`（`${boardUrl}/#/board`）；选/建会话正确切回终端。PTY 仅 `display` 显隐、不杀进程，浏览看板不中断终端会话。
2. **地址从配置读** ✅ env `CCC_BOARD_URL` → `~/.clwarp/config.json|settings.json` → 回退 `http://192.168.3.116:7788`，即 `docs/deploy/topology.md` 现行唯一生产 HTTP 端点（2017，`:7788`）；`#/board` 路由与 `.ccc/infrastructure.md` 一致，非随机硬编码。
3. **失败中文提示+重试** ✅ `cccLoadFailed`/`cccNotReachable`/`cccRetry`；`TcpStream::connect_timeout`(1s) 探活，失败给重试按钮。探活为连通性近似，可接受。
4. **红线合规** ✅ 只读用户配置，不写 CLI 配置；数据目录 `~/.clwarp/` 隔离；不写业务项目文件。
5. 构建属机械门禁，未重复。

就地修复（mochi 乱码）：`src/i18n/index.ts` `cccNotReachable` 原含替换字符 `无���` → 改为 `无法`；commit `1d86c90`，已 push `codex/clw004-ccc-webview`。

结论：无原则性红线问题，可进入「合入批准」。

## 执行提示

- 项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 仓库路径：/Users/fan/program/apps/clwarp（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：
  - [domains::projects::常用命令] 常用命令 - 前端依赖： - 前端 lint：（oxlint） - 前端构建：（tsc -b && vite build） - Rust 编译检查： - Rust 发布构建： - 开发启动：（仓根，先 npm install） - 出卡： - 看板：CCC 项目=clw

- 禁区：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 审查清单：
  - [domains::projects::section_0] clw (clwarp) 审查维度 > 审查重点：PTY 生命周期、IPC 边界、红线合规、前端错误处理

- 架构约束/红线：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭
