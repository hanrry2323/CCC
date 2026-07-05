# 命令速查（规划者参考）

> 规划者写 plan 时参考这些命令能力来指定执行方式。
> 工具代际迁移说明：本节中 `mavis session new` / `mavis cron` 等命令在 v0.5
> 前是默认调度路径，v0.5 起改用 `scripts/ccc-scheduler.sh` + launchd cron +
> CCC cluster bus（v1.0 路线）。本节保留 IPC 命令名作为**已废弃命名**用于
> 阅读历史 plan。

---

## IPC 端（已废弃——v0.3 时期使用，v0.5 起改 CCC dispatcher）

> 以下命令名出现在历史 plan 中。**v0.5 起新规划应改用 `scripts/ccc-scheduler.sh` + launchd**。
> 列出它们仅供参考。

| 命令 | 作用 | 在 plan 中怎么写 |
|------|------|------------------|
| `mavis session new <项目简称>-CC -p "..." -w <路径>` | 触发项目规划师生成 plan | **v0.5 起改**: "按 ccc full 跑 X 任务" |
| `mavis session new verifier -p "..." -w <路径>` | 触发验收师终验 | **v0.5 起改**: Verifier 自起 + 必写 verdict 文件（红线 11） |
| `claude -p "..." --permission-mode auto` | Executor 角色（在 Claude Code CLI 终端跑） | **仍是正确写法** |
| `mavis cron create <agent> <name> --schedule "..." --prompt "..."` | 定时监控执行 | **v0.5 起改**: `scripts/ccc-scheduler.sh` + launchd |
| `mavis session diff <sessionId>` | 查看某次 session 的文件改动 | 终验时对照 |
| `mavis session list <agent>` | 列出 agent 的所有 session | — |
| `mavis agent info <name>` | 查看 agent 详情 | — |

**红线提醒**：

> 红线 9（v0.5 起改述）：禁止用 IPC 通道（如 `mavis session new`）绕过 CCC
> dispatch。所有 Executor/Verifier 必须直接 `claude -p` 或通过 CCC dispatcher
> 调度。这是为什么 minimax 模型在 v0 阶段产出不可信、v0.3 时期踩过 Lesson 19。

---

## Claude 端（执行 / 仍有效）

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

### 启动选项

| 选项 | 作用 |
|------|------|
| `--permission-mode auto` | 自动模式，权限不弹窗 |
| `--model <model>` | 指定模型（默认 flash） |
| `--effort <level>` | 努力程度：low / medium / high / max |
| `-p "<指令>"` | 非交互模式，执行完退出（Lesson 27：注意参数语义） |
| `--continue` | 继续上次的会话 |

---

## 术语约定（P2 修复）

执行方式只有以下 4 个值，**禁止使用其他术语**：

- `manual` ✅
- `auto` ✅
- `loop` ✅
- `goal` ✅

历史曾出现但不规范：`codeloop` / `手动` / `auto-loop` → 全部统一为以上 4 个。
