# 任务卡 clw005 · 设置面板（OpenCode 执行）

> 关联：clw-plan-001 · 阶段 5/6 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：clw · 日期：2026-08-09
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 目标

设置面板——侧边栏新增「设置」入口，打开后面板可调整主题/终端字体/CCC 看板地址等配置，修改即时持久化到 `~/.clwarp/config.json`，重启后保持。

## 红线（先看）

1. 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
2. 数据目录 `~/.clwarp/` 隔离，不写其他路径
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src-tauri/src/settings.rs`（新）
- `src-tauri/src/lib.rs`
- `src-tauri/Cargo.toml`
- `src/App.tsx`
- `src/Settings.tsx`（新）
- `src/i18n/`
- `~/.clwarp/config.json`（运行时读写，不提交）

## 步骤

1. Rust 后端：新建 `settings.rs`，实现 `load_settings` / `save_settings` 命令，读写 `~/.clwarp/config.json`（JSON 格式，字段：`theme`、`ccc_board_url`、`terminal_font_size`）；首次启动无文件时返回默认值
2. Rust 后端：在 `lib.rs` 注册新命令，挂载到 Tauri invoke handler
3. 前端：新建 `Settings.tsx`，设置面板 UI（侧边栏入口 + 主区面板），包含：
   - 主题切换：深色/浅色（即时生效，通过 CSS 变量或 class 切换）
   - CCC 看板地址：文本输入框（默认值从现有 `get_ccc_board_url` 读取）
   - 终端字体大小：数字输入或滑块（12–24px，默认 14）
4. 前端：`App.tsx` 侧边栏新增「设置」入口（齿轮图标 ⚙️），`viewMode` 扩展 `'settings'`，点击切换到设置面板；主题切换即时应用到全局
5. 设置变更即时保存（onChange 防抖 300ms 后调 `save_settings`），无需手动保存按钮
6. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 侧边栏有「设置」入口，点击后主区显示设置面板（不为空），可切回终端/CCC 看板
2. 主题切换：选深色/浅色后全局即时生效，重启 app 后保持
3. CCC 看板地址：修改后下次打开 CCC 面板使用新地址（与 clw004 `get_ccc_board_url` 读取链兼容：env > config.json > 回退）
4. 终端字体大小：修改后新开终端使用新字号
5. `~/.clwarp/config.json` 文件存在且为合法 JSON，包含上述字段
6. 红线合规：不修改用户 CLI 配置；会话文件零写入；不写业务项目文件；数据目录 `~/.clwarp/` 隔离
7. 构建通过：`cargo build --release` + 前端 `tsc -b && vite build` 均 0 error

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 仓库路径：/Users/fan/program/apps/clwarp（Mac2017）

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 前端依赖：`npm install` - 前端 lint：`npx oxlint` - 前端构建：`tsc -b && vite build` - Rust 编译检查：`cargo check` - Rust 发布构建：`cargo build --release` - 开发启动：仓根 `cargo tauri dev` - 出卡：`scripts/new-card.sh --project clw` - 看板：CCC 项目=clw

- 禁区：
  - 禁止在 CCC 建 `docs/clw/` 深文档树
  - 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
  - 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 现有代码参考：
  - `src-tauri/src/webview.rs`：`get_ccc_board_url` 已从 `~/.clwarp/config.json` 读取配置，settings 模块应复用同一文件路径
  - `src/App.tsx`：`viewMode` 当前为 `'terminal' | 'ccc'`，需扩展 `'settings'`；主题色硬编码在 inline style 中，需改为读取 settings 状态
  - `src/i18n/index.ts`：翻译表已存在，需新增设置相关文案

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：clw（统一 AI 开发桌面驾驶舱 — 一个窗口管理所有 AI CLI 会话（Claude Code / OpenCode / Codex），内嵌 CCC 看板，GPU 原生终端渲染。）

- 审查清单：
  - [domains::projects::section_0] clw (clwarp) 审查维度 > 审查重点：PTY 生命周期、IPC 边界、红线合规、前端错误处理

- 架构约束/红线：
  - 禁止在 CCC 建 `docs/clw/` 深文档树
  - 不修改用户现有 CLI 配置（`~/.claude/`、`~/.codex/` 等只读）
  - 数据目录 `~/.clwarp/`，和 ShellSight 隔离

- 处理原则：
  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过
  - 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出
  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
