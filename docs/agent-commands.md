# 命令速查（规划者参考）

> Mavis + Claude 两端的命令。规划者写 plan 时参考这些能力来指定执行方式。

---

## Mavis 端（规划 / 监控 / 验收）

| 命令 | 作用 | 在 plan 中怎么写 |
|------|------|------------------|
| `mavis session new <项目简称>-CC -p "..." -w <路径>` | 触发项目规划师生成 plan | "项目 CC 规划师出 plan" |
| `mavis session new verifier -p "..." -w <路径>` | 触发验收师终验 | "verifier 做验收" |
| `claude -p "..." --permission-mode auto`（在 Claude Code CLI 终端跑，**不是** mavis session） | Executor 角色 — 执行 plan 的自主长任务 session | "执行方式 auto" |

**注意**：Executor **不是** Mavis agent。Mavis 端没有 Executor agent。Executor 必须在用户自己的 Claude Code CLI 终端运行 `claude -p`，Planner 不能在自己的 mavis session 里同步 spawn `claude -p`（会 block session 25 分钟）。
| `mavis cron create <agent> <name> --schedule "..." --prompt "..."` | 定时监控执行 | "每 5 分钟检查一次进度" |
| `mavis session diff <sessionId>` | 查看某次 session 的文件改动 | 终验时对照 |
| `mavis session list <agent>` | 列出 agent 的所有 session | |
| `mavis agent info <name>` | 查看 agent 详情 | |

---

## Claude 端（执行）

### 长任务自主执行（按执行方式）

| 方式 | 命令 | 何时使用 | 在 plan 中怎么写 |
|------|------|---------|------------------|
| `manual` | 直接编辑 + commit | 单文件、可直接验证 | "执行方式：manual" |
| `auto` | `claude -p "..." --permission-mode auto` | 简单多 phase | "执行方式：auto" |
| `loop` | `/loop <间隔> <指令>` | 定时重复（最长 7 天） | "执行方式：loop 30m" |
| `goal` | `/goal <条件>` | 复杂多 phase 不中断 | "执行方式：goal" |

### 上下文管理

| 命令 | 作用 |
|------|------|
| `/clear` | 清除对话历史，重置上下文 |
| `/compact` | 压缩历史释放空间 |
| `/compact <指令>` | 按指定优先级压缩 |
| `/context` | 查看当前上下文使用情况 |
| `/btw <问题>` | 提问但不写入对话历史（不占 context） |

### 会话控制

| 命令 | 作用 |
|------|------|
| `Esc` | 停止当前操作 |
| `/rewind` | 回退到任意 checkpoint（对话 + 代码均可） |
| `/rename` | 为会话命名 |
| `claude --resume` | 恢复上次会话 |
| `claude --continue` | 继续最新一次会话 |
| `/branch` | 派生一个分支会话 |

### 质量保障

| 命令 | 作用 |
|------|------|
| `/code-review` | 内置代码审查（子 agent 新鲜上下文） |
| `/code-review ultra` | 深度审查，跟踪式 review |

### 自定义命令（CCC 框架独有）

| 命令 | 作用 |
|------|------|
| `/codex-executor <task>` | 加载 plan 并执行：读 plan → 逐 Phase → phases → report |

### 启动选项

| 选项 | 作用 |
|------|------|
| `--permission-mode auto` | 自动模式，权限不弹窗 |
| `--model <model>` | 指定模型（默认 flash） |
| `--effort <level>` | 努力程度：low / medium / high / max |
| `-p "<指令>"` | 非交互模式，执行完退出 |
| `--continue` | 继续上次的会话 |

---

## 术语约定（P2 修复）

执行方式只有以下 4 个值，**禁止使用其他术语**：

- `manual` ✅
- `auto` ✅
- `loop` ✅
- `goal` ✅

历史曾出现但不规范：`codeloop` / `手动` / `auto-loop` → 全部统一为以上 4 个。