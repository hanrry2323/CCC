# CCC Skill — 跨平台分发报告

> 生成：2026-07-01 · CCC v0.3.0-dev
> 路径: ~/program/CCC · symlink 模式（单源多端）

## 摘要

CCC skill 0.3.0-dev 已分发到 **3 个桌面端平台**：

| 平台 | symlink | 默认 LLM | skill 加载 |
|------|---------|----------|-----------|
| **Mavis** | `~/.mavis/skills/ccc-protocol` → `~/program/CCC` | minimax/MiniMax-M3 ⚠️ | 自动 |
| **Claude Code** | `~/.claude/skills/ccc-protocol` → `~/program/CCC` | Claude (Anthropic) ✅ | 自动 |
| **ZCode** | `~/.zcode/skills/ccc-protocol` → `~/program/CCC` | GLM (智谱 / BigModel) ✅ | 自动 |

## 验证步骤

```bash
# 1. install --check 期望 6 项 OK
bash ~/program/CCC/scripts/install-ccc-as-skill.sh --check

# 2. 三平台目录都包含 SKILL.md
for p in ~/.mavis/skills ~/.claude/skills ~/.zcode/skills; do
  echo -n "$p/ccc-protocol: "
  test -f "$p/ccc-protocol/SKILL.md" && echo "OK" || echo "MISSING"
done
```

## 各平台特性

### Mavis
- **路径**: `~/.mavis/skills/`
- **默认 LLM**: minimax/MiniMax-M3
- **风险**: minimax 自家 M3 与 claude 不等价（Lesson 19 红线 9）；任何 Executor/Verifier 必须用 `claude -p`，**禁 `mavis session new <agent>`**
- **适用场景**: Planner agent 工程（限定的）

### Claude Code
- **路径**: `~/.claude/skills/`
- **默认 LLM**: Anthropic Claude（通过 ai-loop-router :4000）
- **特点**: 标准 CC skill 兼容

### ZCode
- **路径**: `~/.zcode/skills/`
- **默认 LLM**: 智谱 GLM (glm-4.5 / glm-4.6 / glm-5 系列)
- **API 兼容**: anthropic-compatible (`https://open.bigmodel.cn/api/anthropic`)
- **集成引擎**: claude / codex / gemini / glm / opencode（5 个内嵌）
- **plugin 系统**: `~/.zcode/cli/plugins/data/`（含 skill-creator 官方 plugin）
- **特点**: 智谱 AI 是真 LLM，不是 minimax fallback — CCC 协议可正常工作

## 跨 LLM 后端说明

CCC skill 的核心是 SKILL.md（244 行），**纯文本协议**。
- 任何 LLM（Claude / GLM / GPT / 本地模型）读到这份文件，按 procedure 段跑就能执行 CCC 任务
- 不依赖 minimax 或 Anthropic SDK
- 红线 9（Executor/Verifier 必须 claude -p 不用 mavis session new）— 在 ZCode 上改用：ZCode 内嵌的 `claude` 引擎走 `claude -p` 同理；不要走 `mavis session new`

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Mavis minimax 不可信 | 红线 9 + Lesson 19 已写 |
| ZCode GLM 模型可能不熟悉 CCC protocol | SKILL.md 是自然语言协议 + 9 红线清楚 |
| 三平台并发改 CCC 项目源 | 单一源（~/program/CCC）+ 多软链，并发改风险有但可控（一般用户只在一平台操作）|
| 智谱 API 限速 / 计费 | glm-4.5 系列有免费配额；ask user 一次性确认 |

## 后续

- lint SKILL.md (`~/.mavis/.builtin-skills/skill-creator/scripts/lint-skill.js`)
- eval test (skill-creator baseline vs with-skill)
- 跑 hello-world 任务（三平台各跑一次，diff 结果）

## 链接

- 总入口: ~/program/CCC/SKILL.md
- 核心总纲: ~/program/CCC/CLAUDE.md
- 架构文档: ~/program/CCC/docs/architecture.md
- install 脚本: ~/program/CCC/scripts/install-ccc-as-skill.sh
- 跨项目 lessons: ~/program/CCC/projects/qxo/lessons.md（含 Lesson 19 + 20）
