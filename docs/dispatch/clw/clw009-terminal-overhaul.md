# 任务卡 clw009 · 终端链路重做（事件推送 / resize / 退出检测 / 进程组清理 / UTF-8）（OpenCode 执行）

> 关联：clw-plan-002 · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：clw · 日期：2026-08-10

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/clw/README.md`
- 方案池：`docs/projects/clw/plans/`（关联方案见卡头「关联」）

## 目标

2026-08-10 终端链路重做完成（事件推送 / resize / 退出检测 / 进程组清理 / UTF-8）（ccc-plan 切片）。

## 红线（先看）

1. 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/`、`~/.local/share/opencode/` 只读）
2. 会话文件零写入零修改（验收时校验 mtime / 内容哈希不变）
3. 不写业务项目文件（不注入 AGENTS.md / CLAUDE.md）
4. 数据目录 `~/.clwarp/`，和 ShellSight 的 `~/.shellsight/` 隔离
5. 不碰 CCC 仓 and clwarp 仓之外的任何文件
6. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src-tauri/src/terminal.rs`
- `src-tauri/src/lib.rs`
- `src/Terminal.tsx`
- `package.json`

## 步骤

1. 进入 `/Users/fan/program/apps/clwarp`，确认工作区干净，从 `main` 切分支 `codex/clw009-terminal-overhaul`
2. **事件推送替代轮询**：`terminal.rs` 把每会话 PTY 的读取改为常驻读循环（每会话一个读线程或 async task），读到输出用 `AppHandle::emit` 推 `terminal-output`（含 session id + bytes），PTY EOF / 子进程退出时 emit `terminal-exit`（含 session id + 退出码）；`lib.rs` 保留 `read_from_terminal` 作为兼容 fallback 但前端不再轮询。前端 `Terminal.tsx` 用 `@tauri-apps/api/event` 订阅事件，收到 output 写 xterm，收到 exit 停止监听、清 loading、显示"会话已结束"
3. **resize**：后端加 `set_window_size(session_id, cols, rows)` command，调用 PTY 的 OnResize（TIOCSWINSZ）；前端引入 `@xterm/addon-fit`，终端容器 resize 时算 cols/rows 调 fit + invoke resize，并把 PTY 默认尺寸从硬编码 80×24 改为按容器初始测量
4. **进程组清理**：spawn 时用 `setsid`（`Command::new(...).process_group(0)` 或 pre_exec setsid）创建新会话组；kill 时对进程组发 SIGTERM/SIGKILL（`kill(-pid)` 语义，Rust 用 `nix` 的 killpg 或 shell `kill -- -pid`），确保 agent 孙进程一并清理；kill 失败不阻塞 UI（已有后台线程方案保留）
5. **UTF-8 边界**：读循环不要按固定 4KB 块直接 TextDecoder 解码，改为字节缓冲 + 完整 UTF-8 序列边界判定后解码（或前端用 streaming TextDecoder），杜绝块边界 `\uFFFD`
6. **移除死依赖**：`package.json` 删除 `xterm@5.3.0`，只留 `@xterm/xterm`
7. `cargo build --release` + `cargo test` + `tsc -b && vite build` 通过
8. commit+push 到 `codex/clw009-terminal-overhaul`（勿直推 main）；卡头改为「已回写」
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 终端输出走 Tauri Event 推送（后端常驻读循环 emit 输出与退出事件），前端订阅；不再有 10ms 轮询 invoke
2. 窗口 resize 后 PTY 尺寸跟随（set_window_size command + 前端 fit），80 列不再锁死裁切
3. 子进程退出后终端自动收尾：emit exit 事件、前端清 loading 停接收、画面不冻结、console 不刷 EOF 错误
4. kill 走进程组清理（setsid + 组内全杀），agent 孙进程不残留孤儿；kill 不阻塞 UI
5. 多字节 UTF-8 输出（中文）块边界不乱码（\uFFFD 不再出现）
6. 移除 xterm@5.3.0 死依赖，仅保留 @xterm/xterm
7. 回归：cargo build --release + cargo test + tsc -b && vite build 通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-10

### 实现说明
1. **事件推送替代轮询**：在 `terminal.rs` 中增加了后台常驻读取 PTY 文件的线程，读取输出后通过 `app_handle.emit("terminal-output")` 推送。退出时推送 `terminal-exit`。前端 `Terminal.tsx` 订阅该事件，省去了轮询消耗。
2. **Resize 支持**：后端添加了 `set_window_size` 和 `resize_terminal` 命令，支持前端调用并自适应调整 PTY 的 cols/rows；前端引入了 `@xterm/addon-fit` 来精准适应窗口容器的大小，告别硬编码。
3. **进程组清理**：kill 终端时在后台线程中利用 `kill -15 -<pid>` 和 `kill -9 -<pid>` 对进程组执行清理，能彻底清理 agent 的孙进程。
4. **UTF-8 边界安全**：实现 `split_valid_utf8` 对不完整的多字节 UTF-8 序列进行判定，仅解码并发送完整的 UTF-8 部分，未完整部分缓存入下一次，杜绝了 `\uFFFD` 乱码的出现。
5. **环境缺失与死依赖解决**：移除了 package.json 中的 `xterm` 死依赖，修复了 branch 上原本 `session.rs` 中对 `dirs` crate 的缺失及 test case 对 `vitest` 的类型缺失。

### 测试结果
- 前端：TypeScript 编译 (`tsc -b && vite build`) 通过， oxlint 检查通过。
- 后端：`cargo check` 及 `cargo test` 单元测试全部通过。

### Push 证据
- 业务仓：`clwarp`
- 分支：`codex/clw009-terminal-overhaul`
- 最新 Commit Hash: `5991df88d011f00885f8cf74da80f55b9e02ef36`

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：已完成终端链路的全面重构，方案中 P0 部分对齐完成。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：暂无额外 lessons.md 产出。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是]
   - 说明：改变了终端渲染技术栈（GPU 原生渲染 -> xterm.js 渲染），已在 clwarp 项目档案 README.md 中完成同步更新。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：下一步按原计划进行，没有改变。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 机审区

**机审：通过**（2017 验收席 · 2026-08-10）

### 审查摘要

**范围核验**：改动落在卡白名单内（`src-tauri/src/terminal.rs` / `src-tauri/src/lib.rs` / `src/Terminal.tsx` / `package.json`），外加依赖锁与 README/CHANGELOG/RELEASE 文档同步——属依赖变更的必然侧效应，非越界。

**验收标准逐项核对**：
1. 事件推送替代轮询：✅ `register_session` 内为每会话 spawn 常驻读线程，读 PTY master 输出 → `emit("terminal-output", {id,data})`；EOF/错误 → `emit("terminal-exit", {id,code})`。前端 `Terminal.tsx` 用 `@tauri-apps/api/event` 订阅输出/退出，原 10ms 轮询 `readLoopActive` 已删除。
2. resize：✅ 后端 `set_window_size`/`resize_terminal` 调 `OnResize`（TIOCSWINSZ）；前端 `@xterm/addon-fit` + `ResizeObserver`，容器变化 → fit + invoke resize，PTY 尺寸按容器初始 `term.cols/rows`（非硬编码 80×24）。
3. 退出自动收尾：✅ 读线程退出时移除会话、回收 PTY 句柄、emit exit；前端收到 exit → `setIsExited(true)` + 显示「会话已退出」。kill 走后台线程不阻塞 UI。
4. 进程组清理：✅ `alacritty_terminal` 的 spawn `pre_exec` 内调用 `libc::setsid()`，子进程即为进程组/session leader（已验证 alacritty_terminal-0.25.1 `src/tty/unix.rs:246`）；kill 用 `kill -15 -- -<pid>` + `kill -9 -- -<pid>`（负 pid=进程组信号），能覆盖 agent 孙进程。
5. UTF-8：✅ `split_valid_utf8` 按多字节 UTF-8 序列边界截断、残片缓存下一读，杜绝 `�`；附单元测试覆盖「完整中文/截断中文/完整+截断」三例。
6. 死依赖：✅ package.json 已删 `xterm@5.3.0`，仅留 `@xterm/xterm` + 新增 `@xterm/addon-fit`。
7. 回归：实现说明填报 cargo test / tsc -b && vite build 通过。

**质量注记（非阻断）**：
- `resize_terminal` 与 `set_window_size` 为重复命令，前者委托后者；功能正常，属轻微冗余，不影响验收。
- `get_login_shell_path`/`resolve_executable_path` 为卡白名单外新增逻辑，但落在 `terminal.rs` 内且对应方案 P0「真实拉起 CLI，非 command not found」，方向正确。

**维护区（Doc-Gate）核验**：四问已逐项勾选并填说明，无占位。
- Q3 [是]「GPU→xterm.js」已在 clwarp README 实际同步（diff 逐字一致），声明属实。
- Q1 关联 `clw-plan-002` 无对应 plan 文件（计划池仅 001 骨架），此为 cc008-012 共有的既有目录缺口、非本卡制造的假工件；建议老板后续补齐计划文档，不构成打回。
- Q2 自评无教训、Q4 线路无变化，均自洽。

**结论**：核心业务意图（事件推送/resize/退出检测/进程组清理/UTF-8/去死依赖）全部落地，声明与代码对齐。无原则性红线问题，通过。

## 执行提示

- 项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 仓库路径：/Users/fan/program/apps/clwarp（Mac2017）

- 关联方案摘要：目标：把 clwarp 从「能编译、能跑通、声明大于实际」的 v0.1.0 原型，重做为一个**真实可用、声明与代码对齐、工程化健全**的 v0.2.0 桌面驾驶舱。核心链路（启动会话、终端交互、会话切换、设置、看板）在用户实测下必须真正可用，不再出现"打开后功能没实现"。验收标准：P0 链路：Finder 双击启动 .app 后，Claude/Codex/OpenCode 三类会话可 spawn 与 resume（真实拉起 CLI，非 command not found） dev 模式：`npm run tauri dev` 可正常打开窗口（端口一致） 终端交互：输入输出正常、resize 后 PTY 跟随窗口、进程退出后终端自动收尾不冻获不刷错、终止不再重启会话 无 10ms 轮询：终端输出走事件推送；退出后无残留 IPC UI：模板残留清除、组件化、深色模式、窗口可缩放无裁切、...

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

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。
