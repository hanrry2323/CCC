# 方案 · clwarp 0.3.0 加固——会话打开可靠性（不开发新功能）

> 项目：clw · 编号：clw-plan-005 · 状态：已完成 · 作者：OpenCode（中枢·调度） · 工具：OpenCode
> 创建：2026-08-12 · 更新：2026-08-12
>  关联卡：已归档（原引用 clw023, clw024, clw025 随 8-24 治理归档，见 docs/archive 与 RETIRED 记录）
> 关联方案：clw-plan-003（v0.3.0 缺陷收口，已合入）
> 进度：3/3 (100%)
> 依据：老板 2026-08-12 实测反馈「会话打不开，连不上」+ 中枢只读侦察结论

## 目标

修复 clwarp 会话打开/连接的 P0 问题，使「点历史会话恢复 / 新建会话」在实测下真实可用。**本方案只做加固，不开发新功能。**

## 背景（中枢只读侦察结论，2026-08-12）

2017 实测（`$SHELL -lc 'echo $PATH'` + `which claude/codex/opencode`）：
- `claude` ✅ `/Users/fan/.npm-global/bin/claude`（版本 2.1.228 可拉起）
- `opencode` ✅ `/Users/fan/.npm-global/bin/opencode`（版本 1.18.13 可拉起）
- **`codex` ❌ not found** —— Sidebar 中 codex 历史会话点击恢复 → `resume_session` 执行 `codex` 命令 → 找不到 → 会话打不开

代码链路核查（`src-tauri/src/terminal.rs` + `provider.rs` + `src/Terminal.tsx`）：
1. **PATH 解析**：`get_login_shell_path_with_timeout` 已实现（5s 超时 + `/usr/local/bin:/opt/homebrew/bin` 兜底），`get_cached_path` 5s 缓存——PATH 层基本可靠
2. **spawn 链路**：`spawn_terminal(cols, rows)` 只建裸 PTY（默认 shell），**不拉 AI CLI**；真正拉 AI CLI 走 `resume_session`（build_provider_command → claude/codex/opencode）
3. **codex 缺失是确定根因之一**：任何 codex 会话恢复必然失败
4. **待验证**：claude/opencode 会话恢复在 GUI 实测是否稳定（前端 `frontend_ready` 握手、5s PATH 缓存是否够、会话启动超时）

## 方案内容

按三块加固，每块一张卡：

**切片 A · codex 可执行性修复（P0 确定根因）**
- 排查 2017 codex 实际安装位置（可能 `~/.codex/bin/` 或 npm 全局未装）；若已装 → 加入登录 shell PATH（`~/.zshrc`/profile）；若未装 → Sidebar 对 codex 会话降级展示（禁用恢复 + 提示"codex 未安装"），不白屏
- `build_provider_command` 对 codex 加可执行性预检：spawn 前 `resolve_executable_path` 失败 → 返回明确错误（前端显示友好文案，不卡 loading）
- 前端：spawn 失败错误态完善（`getFriendlyError` 覆盖 command not found）

**切片 B · 会话打开链路加固（P0 可靠性）**
- PATH 缓存 5s 过期问题：spawn/resume 关键路径确保每次拿到最新 login PATH（缓存失效策略；`codex` 若后续安装不重启生效）
- `frontend_ready` 握手超时：spawn 后前端等待初始输出，若 CLI 启动慢/无输出 → 前端超时显示友好态（不永久 loading）
- `resume_session` 的工作目录解析失败容错（claude project path 解码失败 → 回退默认目录，不失败退出）
- spawn 错误从后端透传前端（当前 `spawn_terminal` 错误可能被吞）

**切片 C · 会话打开回归验证（P0 验收）**
- 2017 实测清单：新建 claude 会话可打开可交互；恢复 claude 历史会话可打开；opencode 新建/恢复可打开；codex 恢复给出友好错误（而非打不开）
- 记录实测证据（截图/日志/会话输出），作为 0.3.0 加固验收
- 补充前端 Terminal 组件单测（spawn 成功/失败路径）

## 验收标准

- [x] 2017 上新建 claude 会话可打开、可输入输出
- [x] 恢复 claude/opencode 历史会话可打开、可继续对话
- [x] codex 会话恢复不白屏：给出明确"codex 未安装/找不到"友好错误
- [x] spawn 失败不再永久 loading（前端显示错误态）
- [x] `cargo build --release` + `tsc -b && vite build` + vitest 全过
- [x] 回归：0.3.0 既有功能（设置/看板/终端）不破坏

## 转卡计划

```ccc-plan
title: clwarp 0.3.0 加固——会话打开可靠性（codex 可执行性 / spawn 链路 / 回归验证）
project: clw
slices:
  - title: "codex 可执行性修复（P0 确定根因：codex not found → 会话打不开）"
    slug: codex-executability
    executor: OpenCode
    acceptance:
      - "排查 2017 codex 实际安装位置：已装 → 加入登录 shell PATH（profile/zshrc）；未装 → Sidebar codex 会话降级（禁用恢复 + 提示未安装，不白屏）"
      - "build_provider_command 对 codex 加可执行性预检：resolve_executable_path 失败 → 返回明确错误，前端显示友好文案，不卡 loading"
      - "前端 getFriendlyError 覆盖 command not found 场景（中文提示）"
      - "回归：cargo build --release + tsc -b && vite build 通过"
    whitelist:
      - "src-tauri/src/provider.rs"
      - "src-tauri/src/terminal.rs"
      - "src/components/errors.ts"
      - "src/components/SessionItem.tsx"
      - "src/components/Sidebar.tsx"
  - title: "会话打开链路加固（spawn/resume 可靠性：PATH 缓存 / 握手超时 / 错误透传）"
    slug: session-open-hardening
    executor: OpenCode
    acceptance:
      - "PATH 缓存策略修复：spawn/resume 拿到最新 login PATH（codex 后续安装不重启生效）"
      - "frontend_ready 握手超时：CLI 启动慢/无初始输出 → 前端超时显示友好态，不永久 loading"
      - "resume_session 工作目录解析失败容错：claude project path 解码失败 → 回退默认目录不失败退出"
      - "spawn/resume 错误从后端透传前端（不吞错误），前端显示明确错误信息"
      - "回归：cargo build --release + tsc -b && vite build + vitest 通过"
    whitelist:
      - "src-tauri/src/terminal.rs"
      - "src-tauri/src/provider.rs"
      - "src/Terminal.tsx"
      - "src/components/TerminalView.tsx"
      - "src/components/errors.ts"
  - title: "会话打开回归验证（0.3.0 加固验收：2017 实测清单 + 证据）"
    slug: session-open-verify
    executor: OpenCode
    acceptance:
      - "2017 实测：新建 claude 会话可打开可交互；恢复 claude 历史会话可打开；opencode 新建/恢复可打开；codex 恢复给友好错误"
      - "实测证据记录（会话输出/日志/错误信息），回写卡"
      - "spawn 失败不再永久 loading（前端错误态）"
      - "补充前端 Terminal 组件单测（spawn 成功/失败路径）"
      - "回归：0.3.0 既有功能（设置/看板/终端）不破坏"
    whitelist:
      - "src/Terminal.tsx"
      - "src/components/TerminalView.tsx"
      - "src/App.test.tsx"
      - "src-tauri/src/terminal.rs"
```

## 备注

- 本方案为**调度指令**：中枢只读侦察 + 出卡，执行体按卡开发（不代执行）
- **红线**：不改 CLI 配置（`~/.claude/` 等只读）；会话文件零写入；数据目录 `~/.clwarp/`
- 执行约束：codex 安装需 2017 本机操作（sudo/brew），卡内探针验证；spawn 链路改动带单测
- 范围外：新功能（Linux 适配/远程中继）不在本方案
