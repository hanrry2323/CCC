# 任务卡 clw012 · 工程化基座（CSP / 图标 / CI / 测试 / 开发链路）（OpenCode 执行）

> 关联：clw-plan-002 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：clw · 日期：2026-08-10

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/clw/README.md`
- 方案池：`docs/projects/clw/plans/`（关联方案见卡头「关联」）

## 目标

工程化基座（CSP / 图标 / CI / 测试 / 开发链路）（ccc-plan 切片）。

## 红线（先看）

1. 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/`、`~/.local/share/opencode/` 只读）
2. 会话文件零写入零修改（验收时校验 mtime / 内容哈希不变）
3. 不写业务项目文件（不注入 AGENTS.md / CLAUDE.md）
4. 数据目录 `~/.clwarp/`，和 ShellSight 的 `~/.shellsight/` 隔离
5. 不碰 CCC 仓和 clwarp 仓之外的任何文件
6. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `.github/workflows/ci.yml`
- `package.json`
- `src-tauri/tauri.conf.json`
- `src-tauri/capabilities/default.json`
- `src-tauri/src/*.rs`
- `src/*.tsx`
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`

## 步骤

1. 进入 `/Users/fan/program/apps/clwarp`，确认工作区干净，从 `main` 切分支 `codex/clw012-eng-foundation`
2. **CSP 与权限**：`tauri.conf.json` 的 `csp: null` 改为白名单（允许看板端点域名 + `tauri://localhost`）；`capabilities/default.json` 按实际使用明确权限（保持最小化，不放开不必要权限）
3. **正式图标**：替换 `src-tauri/icons/` 下 Tauri 占位图标（icon 全家桶：icns/ico/png 各尺寸），用 clwarp 自己的品牌图标（先做一套简洁占位设计，避免再用默认 Tauri 图标）
4. **CI**：新建 `.github/workflows/ci.yml`：lint（oxlint + cargo clippy）+ test（cargo test + vitest）+ build（tsc + vite build + cargo build --release）＋打包（tauri build），可在仓库跑通
5. **测试补齐**：Rust 核心链路单测（session 解析、provider 命令构造、git_status 解析）；前端 vitest 补关键组件测试；Cargo.toml/package.json 加对应测试脚本与依赖
6. **开发链路**：`package.json` 加 `tauri` script 与 `@tauri-apps/cli` devDependency（让 `npm run tauri dev/build` 可复跑）；`README.md`/`CLAUDE.md` 命令与实际一致
7. `cargo test` + `tsc -b && vite build` + lint 全通过
8. commit+push 到 `codex/clw012-eng-foundation`（勿直推 main）；卡头改为「已回写」
9. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. CSP 从 null 改为白名单（允许看板端点与 tauri 本地域名），capabilities 权限明确
2. 正式图标替换 Tauri 占位（icon 全家桶）
3. CI 落地：GitHub Actions（lint + test + build + 打包 workflow）可在仓库跑通
4. 测试补齐：Rust 核心链路单测（session 解析 / provider 命令构造 / git_status）、前端 vitest（关键组件）
5. 开发链路修复：package.json 含 tauri script 与 @tauri-apps/cli，README/CLAUDE.md 命令可复跑
6. 回归：cargo test + tsc -b && vite build + lint 全通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是/否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：
2. **教训沉淀**：本卡是否产出可复用教训？[有/无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是/否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：
4. **线路图**：项目近况/下一步是否变化？[是/否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

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
