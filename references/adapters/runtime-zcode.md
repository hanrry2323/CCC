# Runtime: ZCode (智谱 AI 编码助手)

ZCode 下的 CCC skill 加载与执行方式。ZCode 没有 `claude -p` 等价的非交互 CLI，通过 skill 发现 + subagent dispatch 实现 CCC 三阶段管线。

---

## 何时使用

- 开发者在 ZCode session 中
- 需要 ZCode 执行 CCC 全流程（Planner → Executor → Verifier）
- 使用智谱大模型（GLM-5）时

---

## 安装

ZCode 已从以下路径发现 CCC skill（symlink 至 `~/program/CCC`）：

| 优先级 | 路径 | 说明 |
|--------|------|------|
| 1 | `<project>/.zcode/skills/ccc-protocol/` | 项目级（手动创建 symlink） |
| 2 | `<project>/.agents/skills/ccc-protocol/` | 项目级（同） |
| 3 | `~/.zcode/skills/ccc-protocol/` | **用户级**（已安装） |
| 4 | `~/.agents/skills/ccc-protocol/` | 用户级（未装） |

用户级已安装，项目级按需创建 symlink：

```bash
# 在项目根目录创建项目级 CCC skill
cd <project>
ln -sfn ~/program/CCC .zcode/skills/ccc-protocol

# 或使用 .agents（跨工具兼容标准）
ln -sfn ~/program/CCC .agents/skills/ccc-protocol
```

### 验证安装

确保 CCC 对 ZCode 可见：

```bash
ls -la ~/.zcode/skills/ccc-protocol/SKILL.md    # 用户级 ✓
ls -la .zcode/skills/ccc-protocol/SKILL.md      # 项目级（可选）
```

CCC skill 在 ZCode 中被加载后，LLM 看到其 `name: ccc-protocol` + `description`，在匹配用户意图（如"按 CCC 流程跑"、"plan-execute-verify"）时自动触发。

---

## 使用

### 方法 A：skill 触发（推荐）

在 ZCode session 中，表达使用 CCC 协议的意图即可触发 skill：

```
按 CCC 流程处理这个任务：<task spec>
```

ZCode LLM 读取 CCC 的 SKILL.md 后自动启动 **Planner → Executor → Verifier** 三阶段管线。

### 方法 B：直接引用

```
@ccc-protocol/SKILL.md

按要求执行 CCC 流程：
<task spec>
```

### 方法 C：subagent dispatch（ZCode Superpowers）

ZCode 内置了 Superpowers 插件，其子技能与 CCC 互补。当 ZCode Executor 需要拆分任务时，使用 subagent-driven-development：

1. `<project>/.zcode/skills/ccc-protocol/SKILL.md` — 读入 CCC 协议
2. ZCode 自动调用 `subagent-driven-development`（通过 Superpowers 插件）
3. 每个 task 分派独立 subagent，完成后汇总

---

## 与 Claude 运行时的差异

| 方面 | claude -p | ZCode |
|------|-----------|-------|
| 执行方式 | `claude -p "prompt"` 非交互 | skill 内触发，无 CLI 等效 |
| 模型 | Claude Opus/Sonnet/Haiku | 智谱 GLM-5 / GLM-5-Turbo |
| Subagent | 子进程 claude CLI | 内置 subagent dispatch (Superpowers) |
| Permission | `--permission-mode bypassPermissions` | 由 ZCode 设置控制 |
| 文件契约 | `.ccc/` 目录（4 文件） | 同，跨工具兼容 |
| 预算控制 | `--max-budget-usd` | ZCode 无对应参数 |

---

## Executor 适配说明

CCC Executor 在 ZCode 下的行为调整：

1. **Phase 1-3**（Plan → Execute → Verify）：ZCode 按 skill 内的 procedure 执行，无额外 CLI 包装
2. **Phase 4**（Report）：输出至 `.ccc/reports/` 同路径
3. **Phase 5**（Review）：同

ZCode 无需额外 CLI 参数。Executor 直接读 `.ccc/phases/<task>.phases.json`，按 phase 逐项执行。

---

## 注意事项

- ZCode 上 `claude -p` 不存在 —— Executor 阶段不可用 `--permission-mode bypassPermissions` 等参数
- 大模型差异：智谱 GLM 与 Claude 输出存在差异，CCC 的 `description` 应加注触发关键词
- Superpowers 插件的 `subagent-driven-development` 与本 skill 互补但不冲突：CCC 定协议，Superpowers 提供执行子 agent
- ZCode skill 的 `name` 和 `description` 决定了触发精度 —— 若触发不佳，可考虑在 ZCode 用户级 skills 中建一个 wrapper SKILL.md，description 加更多中文触发词
