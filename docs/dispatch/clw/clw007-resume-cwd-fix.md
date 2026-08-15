# 任务卡 clw007 · resume 携带工作目录 + git 路径解码修复 + kill 非阻塞（OpenCode 执行）

> 关联：clw-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：clw · 日期：2026-08-09

## 目标

resume 携带工作目录 + git 路径解码修复 + kill 非阻塞（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src-tauri/src/provider.rs`
- `src-tauri/src/terminal.rs`
- `src-tauri/src/session.rs`
- `src-tauri/src/git_status.rs`
- `src-tauri/src/lib.rs`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. resume 恢复会话时以会话原始目录为 working_directory 启动 CLI（Claude 解码 -Users- 路径、Codex/OpenCode 用解析出的 cwd），spawn 新会话仍用默认目录
2. git_status 路径解码不误拆目录名中的连字符（my-app 保持原样），且对 Claude/Codex/OpenCode 三类会话 path 均能定位 Git 仓库
3. kill_terminal 不在 UI 线程同步等待子进程退出（drop 在后台线程完成 SIGHUP+wait，或等效非阻塞实现），UI 不冻结
4. 回归：cargo build --release + cargo test 通过；前端 tsc -b && vite build 通过
5. 红线合规：不修改用户 CLI 配置；会话文件零写入；不写业务项目文件

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-09

### 1. 实现说明
- **会话工作目录（working_directory）恢复**：
  在 `provider.rs` 的 `resume_session` 中，通过 `list_all_sessions()` 获取要恢复的会话信息。
  - 对于 Claude 类型的会话，使用 `git_status::decode_claude_project_path` 解码其会话路径（以 `-Users-` 开头的编码格式）为真实的工作目录。
  - 对于 Codex 或 OpenCode 类型的会话，直接使用其记录的 `path` 字段作为工作目录。
  - 最后，将解析出的 `working_directory` 作为参数提供给 `TerminalSession::new`，从而在新 PTY 中恢复相应的工作目录。新创建的会话不受影响（仍然使用默认目录）。
- **Git 路径解码（不误拆连字符）**：
  在 `git_status.rs` 的 `decode_claude_project_path` 中，引入了基于实际文件系统遍历的 `resolve_path_from_segments` 递归匹配机制。通过逐步探测真实存在的目录组合（例如在 `/Users/fan/program` 下匹配整个 `ccc-dev-ws-clw007` 节点而非误拆为 `ccc/dev/ws/clw007`），完美避免了误拆带有连字符（如 `my-app` 或 `ccc-dev-ws-clw007`）的目录，并支持 Claude / Codex / OpenCode 三类会话的路径定位。
- **非阻塞 Kill Terminal**：
  在 `terminal.rs` 的 `kill_terminal` 命令中，不再在 UI 主线程同步 Drop 和等待子进程。将要移除的 `TerminalSession` 转移所有权到通过 `std::thread::spawn` 异步启动的后台线程中进行 Drop。后台线程安全地在后台完成 SIGHUP 和等待子进程，从而确保 UI 线程完全不冻结。

### 2. 测试结果
- **单元测试**：
  在 `git_status.rs` 中编写了专门的 `test_decode_claude_project_path` 单元测试，测试结果：
  ```
  running 1 test
  test git_status::tests::test_decode_claude_project_path ... ok
  ```
- **构建与分析**：
  - Rust 侧编译与测试通过：`cargo build --release` 和 `cargo test` 100% 绿。
  - 前端 Lint 检查无警告：`npm run lint` 通过。
  - 前端 TypeScript 构建通过：`npm run build`（`tsc -b && vite build`）成功。

### 3. Push 证据 (Commit Hash)
- 业务仓（clwarp）提交：[e3d3dd4b4cd2140020b64267d2ee07b0c285dc17](https://github.com/hanrry2323/clwarp/commit/e3d3dd4b4cd2140020b64267d2ee07b0c285dc17) 已经推送至 `codex/clw007-resume-cwd-fix` 分支。

## 维护区

1. **方案同步**：[是] 关联方案 clw-plan-001 阶段 3 后修复卡
   - 说明：clw007 为 clw003 代码审查发现的 P1/P2 缺陷修复，方案转卡计划新增该卡（clw006 编号留位打包卡）。
2. **教训沉淀**：[有] 恢复会话必须携带工作目录，否则 codex/opencode 上下文错位
   - 说明：代码审查发现 resume 未传 working_directory 的功能缺陷，已随本卡修复；教训已同步 clw 复盘。
3. **档案/README**：[否] 无项目档案变更
   - 说明：本卡为缺陷修复，项目档案近况由合入后统一更新。
4. **线路图**：[是] 下一步 = clw006 打包验收（最后一张）
   - 说明：clw001-005、clw007 已收口，clw006 打包卡待出。

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

## 机审区

**机审**：2017 · 2026-08-09 · 结果：**机审：通过**

**审查摘要**

对照 5 项验收标准逐条核验：

1. **resume 携带工作目录** ✅ — `provider.rs::resume_session` 按 provider 分支：Claude 走 `decode_claude_project_path` 解码 `-Users-*` 路径，Codex/OpenCode 直接取 `SessionInfo.path`（其即为真实 cwd）；空 id（新会话）保持 `working_directory=None`。逻辑与三 provider 的 `path` 语义吻合。
2. **连字符不误拆 + 三类定位** ✅ — `git_status.rs` 用贪心最长前缀 + 实盘 `exists()` 探测的 `resolve_path_from_segments`，已实测对 `-Users-fan-program-ccc-dev-ws-clw007` 正确解析出 `ccc-dev-ws-clw007`（而非 `ccc/dev/ws/clw007`），且测试断言同时验正/反两向。
3. **kill 非阻塞** ✅ — `kill_terminal` 将 `TerminalSession` 所有权移交 `std::thread::spawn` 后台线程 drop，UI 线程不 block；session id 由单调递增计数器生成、不复用，后台 drop 与新建 session 无 id 竞态。
4. **回归** ✅ — `cargo test --lib` 全绿（`test_decode_claude_project_path` ok）；编译通过；机械门禁已裁决 build/前端（非本席重复）。
5. **红线合规** ✅ — 全程只读 session 元数据与 cwd，零写入用户 CLI 配置、零会话文件写入、零业务仓文件改动（本次 commit 仅改声明范围内 3 个 Rust 文件）。

**本席就地修复（可修问题，已合规 commit+push）**
- 移除 `decode_claude_project_path` 中针对 project 目录成分做的 `.jsonl` 后缀裁剪：该成分是项目*目录*、从不以 `.jsonl` 结尾（后缀只存在于后续 session 文件名上），是永不触发的死代码，且若真目录恰以 `.jsonl` 结尾会误伤；并给语法回退路径加了空 segments 防护。commit `ab01ece`（clwarp 仓 `codex/clw007-resume-cwd-fix`）。

**结论**：改动在卡声明范围内（5 文件范围的子集）、未违背业务意图、无系统性越界、无安全漏洞。可修问题已修复并回推。**通过**，可交老板「合入批准」。
