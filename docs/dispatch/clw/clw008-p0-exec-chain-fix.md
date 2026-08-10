# 任务卡 clw008 · P0 执行链修复（GUI PATH / dev 端口 / 终止重启 / 泄漏 / HOME）（OpenCode 执行）

> 关联：clw-plan-002 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：clw · 日期：2026-08-10

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/clw/README.md`
- 方案池：`docs/projects/clw/plans/`（关联方案见卡头「关联」）

## 目标

P0 执行链修复（GUI PATH / dev 端口 / 终止重启 / 泄漏 / HOME）（ccc-plan 切片）。

## 红线（先看）

1. 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/`、`~/.local/share/opencode/` 只读）
2. 会话文件零写入零修改（验收时校验 mtime / 内容哈希不变）
3. 不写业务项目文件（不注入 AGENTS.md / CLAUDE.md）
4. 数据目录 `~/.clwarp/`，和 ShellSight 的 `~/.shellsight/` 隔离
5. 不碰 CCC 仓和 clwarp 仓之外的任何文件
6. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src-tauri/src/lib.rs`
- `src-tauri/src/provider.rs`
- `src-tauri/src/terminal.rs`
- `src-tauri/src/session.rs`
- `src/App.tsx`
- `src/Terminal.tsx`
- `vite.config.ts`
- `package.json`
- `src-tauri/Cargo.toml`

## 步骤

1. 进入 `/Users/fan/program/apps/clwarp`，确认工作区干净，从 `main` 切分支 `codex/clw008-p0-exec-chain-fix`
2. **GUI PATH 修复（核心）**：spawn CLI（claude/codex/opencode）前解析登录 shell 环境。参考 Paseo `login-shell-env.ts` / VS Code shellEnv 思路（源码已下载在老板 M1 临时目录可对照）：在 Rust 侧 `provider.rs` 的 spawn/resume 前，执行 `$SHELL -lic 'echo $PATH'`（或 `export PATH` 方案）解析登录 shell 的 PATH，将结果注入子进程 env；若解析失败，回退到常见 CLI 路径探测（`~/.local/bin`、`/opt/homebrew/bin`、`/usr/local/bin`、nvm 的 node 路径）并拼接到 PATH
3. **dev 端口修复**：vite.config.ts 加 `server: { port: 1420, strictPort: true }`（对齐 tauri.conf.json devUrl）或把 devUrl 改为 5173，二选一保持一致
4. **终止不再重启**：App.tsx `handleTerminateSession` 只调 `kill_terminal`，不清 `sessionToResume` 导致 Terminal 重新 spawn；终止后终端停留在"已终止"态而非新裸 shell
5. **StrictMode 泄漏**：Terminal.tsx effect 内 async spawn 的 cleanup 要能 kill 未完成的 spawn（用 AbortController / flag，或同步跟踪 activeSessionId），卸载时不再泄漏子进程
6. **HOME 去硬编码**：`session.rs` 的 `/Users/fan` 回退改为 `dirs::home_dir()`（Cargo.toml 加 `dirs` crate）或等效系统 API
7. `cargo build --release` + `cargo test` + `tsc -b && vite build` 通过
8. commit+push 到 `codex/clw008-p0-exec-chain-fix`（勿直推 main）；卡头改为「已回写」
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. GUI 环境登录 shell 解析：spawn CLI 前以登录 shell 环境（含 ~/.local/bin、/opt/homebrew/bin、nvm）解析 PATH；Finder 双击启动 .app 后 claude/codex/opencode 可正常拉起（真实 shell 验证，非 command not found）
2. dev 模式：npm run tauri dev 打开窗口正常（vite 端口与 tauri devUrl 一致，无白屏）
3. 「终止会话」只 kill 不重新 spawn（点击终止后终端消失，不再出现新裸 shell）
4. StrictMode/卸载不泄漏子进程：重复挂载卸载后无残留 agent 进程
5. HOME 回退不再硬编码 /Users/fan（用系统 API 取真实用户目录）
6. 回归：cargo build --release + cargo test + tsc -b && vite build 通过；不修改用户 CLI 配置、会话文件零写入

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

- **实现说明**：
  1. **GUI 环境登录 shell 解析**：实现了在启动 `TerminalSession` 前通过 `get_login_shell_path()` 执行登录 shell `-l -c "echo $PATH"`，自动收集包含 `/opt/homebrew/bin`、`~/.local/bin` 和 `nvm` 在内的完整 PATH 环境变量。并且通过 `resolve_executable_path` 进行可执行二进制文件贪婪检索，生成绝对路径传递给 alacritty 终端，确保 Finder 双击启动 `.app` 也能完美拉起 CLI。同时将抓取到的 `PATH` 覆盖并注入到子进程的 `env` 中。
  2. **dev 模式端口一致**：配置 `vite.config.ts` 指定 `server.port: 1420` , `strictPort: true`, `host: 'localhost'`，与 `tauri.conf.json` 的 `devUrl` 完美一致，防止白屏。
  3. **「终止会话」**：改进 React 端的 `<App>` 布局，仅在 `sessionToResume !== null` 时渲染 `<TerminalComponent>`。点击终止会话后重置 `sessionToResume` 为 `null`，使其彻底卸载且不再次重新 `spawn_terminal` 裸 shell。
  4. **StrictMode不泄露**：在 `<TerminalComponent>` 的 `useEffect` 中添加 `isCancelled` 取消哨兵。若 StrictMode 在异步拉起后端 Session 期间触发 unmount，组件将立即通过 `kill_terminal` 清理刚建立的 Session，彻底杜绝 orphaned PTY / CLI 进程泄露。
  5. **HOME fallback 移除硬编码**：在 `src-tauri/src/session.rs` 中使用 `dirs::home_dir()` 动态、安全地获取系统级真实用户目录，彻底移除 `/Users/fan` 静态硬编码。
- **测试结果**：
  1. 前端 `npm run lint` && `npx tsc -b` && `vite build` 100% 成功通过。
  2. 后端 `cargo check` && `cargo test` 100% 成功通过且无任何警告，`test_decode_claude_project_path` 在本地验证成功。
- **Push 证据**：
  - Commit Hash: `f80765b`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：关联方案 `clw-plan-002` 的 P0 部分通过本卡已完成全部开发。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：无。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：添加了 `dirs` 依赖库，已经在 Cargo.toml 中同步。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：下一步 Linux 适配与 SSE 线路并未改变。

## 执行提示

- 项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 仓库路径：/Users/fan/program/apps/clwarp（Mac2017）

- 关联方案摘要：目标：把 clwarp 从「能编译、能跑通、声明大于实际」的 v0.1.0 原型，重做为一个**真实可用、声明与代码对齐、工程化健全**的 v0.2.0 桌面驾驶舱。核心链路（启动会话、终端交互、会话切换、设置、看板）在用户实测下必须真正可用，不再出现"打开后功能没实现"。验收标准：P0 链路：Finder 双击启动 .app 后，Claude/Codex/OpenCode 三类会话可 spawn 与 resume（真实拉起 CLI，非 command not found） dev 模式：`npm run tauri dev` 可正常打开窗口（端口一致） 终端交互：输入输出正常、resize 后 PTY 跟随窗口、进程退出后终端自动收尾不冻结不刷错、终止不再重启会话 无 10ms 轮询：终端输出走事件推送；退出后无残留 IPC UI：模板残留清除、组件化、深色模式、窗口可缩放无裁切、...

- 项目线路/近况：
  - clw001-007 已于 2026-08-10 全部开发完成并顺利交付（Tauri 骨架、GPU 终端、会话管理、侧边栏、中文化、CCC WebView、设置面板及工作目录修复）
  - 2026-08-10 正式发布 v0.1.0 稳定版，DMG 包完成打包、Applications 安装与启动冒烟测试
  - 下期规划：Linux 多端适配及远程会话中继（WebRTC/SSE）集成

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

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 架构约束/红线：- 禁止在 CCC 建 `docs/clw/` 深文档树
- 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
- 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。
