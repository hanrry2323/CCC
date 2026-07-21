# loop-code 所有权切割（战略 SSOT）

> **状态**：已拍板（2026-07-21）  
> **性质**：持续工程北极星；冲突时以本文 + [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) 为准。  
> **Phase1 brief**：[`loop-code-ownership-cut-phase1-brief.md`](loop-code-ownership-cut-phase1-brief.md)  
> **Phase2 brief**：[`loop-code-ownership-cut-phase2-brief.md`](loop-code-ownership-cut-phase2-brief.md)  
> **一次收口 brief（Phase3–5 基线）**：[`loop-code-ownership-cut-closeout-brief.md`](loop-code-ownership-cut-closeout-brief.md)

---

## 1. 一句话

**M1 上 Claude 形态产品只剩 CCC Desktop（sidecar + loop-code）；Mac2017 扇出继续用 x86 原版 Claude CLI。对齐协议与 MiniMax，不对齐二进制与产品面。**

---

## 2. 背景（为何切）

| 层 | 当时状态 | 问题 |
|----|----------|------|
| 二进制 | sidecar 已指向 `vendor/loop-code/cli` | 进程级已切 |
| 上游 | plist `ANTHROPIC_*` → MiniMax | 与个人 shell 基本无关 |
| **配置家** | loop-code 仍读 `~/.claude` / `~/.claude.json` | 人格、MCP、skills、历史与个人 Claude **串台** |
| 回落 | `resolve_claude_cli` 可 PATH → 个人 `claude` | 缺 vendor 时静默用原版 |

进程整合约 7 分；配置/身份隔离约 3 分。深度开发 loop-code 前必须先有**唯一受体**。

---

## 3. 已锁定决策

| 面 | 决定 |
|----|------|
| **M1** | CCC Desktop + sidecar + loop-code = **唯一** Claude 形态产品；个人原版 Claude Code 退出生产路径 |
| **Mac2017** | product/reviewer **继续** x86 原版 Claude CLI → MiniMax；**不**为「看起来一致」换 loop-code |
| **「一致」** | 对齐 Anthropic 兼容协议 / MiniMax / plan·phases 契约；**不对齐**二进制与对话 UX |
| **架构事实** | 2017 = `x86_64`；现网 loop-code = `arm64` → 不能直接搬包 |

### 非目标

- 2017 与 Desktop 共用同一份 `vendor/loop-code` 包
- 为品牌一致而维护双架构 fork（除非日后单独立项「CCC 无头 runtime」）
- 本切割内做 MCP/plugins UI（见分阶段）；Phase2 仅退役 CLI，不删 `~/.claude`

```text
M1 对话面                         信息流                    Mac2017 编排面
Desktop → sidecar → loop-code      transfer/flow      Engine → Claude CLI (x86)
         CLAUDE_CONFIG_DIR                              （Phase3：engine-claude 家）
         ~/.ccc/loop-code                               → MiniMax；dev → OpenCode
```

---

## 4. 目标态（M1）

| 项 | 目标 |
|----|------|
| 可执行文件 | 仅 `vendor/loop-code/cli`（或显式 `CCC_CLAUDE_BIN` 且为 loop-code） |
| 配置家 | `CLAUDE_CONFIG_DIR=~/.ccc/loop-code` |
| 人格 | 每轮 `hub_voice` + 私有 `~/.ccc/loop-code/CLAUDE.md`；**不再依赖** `~/.claude/CLAUDE.md` |
| 失败语义 | 缺 loop-code → **明确失败**；禁止 PATH 回落个人 `claude` |
| SDK env | 白名单注入；禁止全量继承 shell |

---

## 5. 分阶段路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase1** | 文档 + `CLAUDE_CONFIG_DIR` + 禁 PATH 回落 + env 白名单 + health/smoke | ✅ 完成（2026-07-21 · `2eafef2`） |
| **Phase2** | M1 卸载/停用原版 Claude Code；PATH 无 `claude` 时 Desktop 仍绿 | ✅ 完成（2026-07-21 · phase2-brief） |
| **Phase3** | 2017 Engine：`CLAUDE_CONFIG_DIR=~/.ccc/engine-claude`（仍用 x86 原版 CLI） | ✅ 完成（closeout） |
| **Phase4** | 会话 SSOT 收敛 + Desktop 展示 loop-code VERSION | ✅ 完成（closeout） |
| **Phase5 基线** | 私有 `settings.json` 种子 + sync 指向（非 MCP 大盘） | ✅ 完成（closeout） |
| **Phase5+** | MCP / hooks / skills 产品面等增强 | 后续（不阻塞收口） |

---

## 6. 验收与回滚（总口径）

**Phase1 绿**：`/health` 报 `agent_runtime=loop-code` 且 `config_dir` 指向 `.ccc/loop-code`；缺 `vendor/loop-code/cli` 时 chat 失败且不落到个人 CLI。

**Phase2 绿**：`command -v claude` 为空；sidecar health 仍为 loop-code + `~/.ccc/loop-code`；`smoke-loop-code-no-personal-claude.sh` PASS。**不得**删整个 `~/.claude`。

**回滚 Phase1**：plist 去掉 `CLAUDE_CONFIG_DIR`、恢复 `resolve` 宽松回落；私有目录可保留。

**回滚 Phase2**：见 phase2-brief（`~/.ccc/retired/` + npm 重装）。

---

## 7. 关联

- 边界：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)
- 热路径：[`desktop-agent-sidecar.md`](desktop-agent-sidecar.md)
- 身份：[`desktop-agent-identity.md`](desktop-agent-identity.md)
- 执行器：[`../executors/loop-code.md`](../executors/loop-code.md)
- 开发通道：[`dev-channel.md`](dev-channel.md)
