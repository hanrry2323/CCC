# Runtime: Cursor

Cursor Composer/Agent 环境下的 CCC 协议加载方式。

---

## 何时使用

- 工作环境是 Cursor IDE
- 需要在 Cursor Composer 中执行 CCC 流程
- 希望 `.cursorrules` 或 `.cursor/rules/` 提供 CCC 协议上下文

## 安装

### 方式 A：.cursorrules（推荐，立即生效）

在项目根 `.cursorrules` 末尾追加：

```
ref: ~/program/CCC/SKILL.md
```

Cursor 每次启动 composer 时自动加载此文件。

### 方式 B：.cursor/rules/ccc-protocol.mdc

用 Claude Code 或手动创建 `.cursor/rules/ccc-protocol.mdc`：

```
---
description: CCC — AI Agent 协作协议，多阶段 plan-execute-verify 流程
globs: *.ccc/**
---

参考 ~/program/CCC/SKILL.md 执行 CCC 流程。
```

### 方式 C：AGENTS.md 引用

在项目根 `AGENTS.md`（如果有）引用：

```
CCC protocol: read ~/program/CCC/SKILL.md for multi-phase task workflow
```

## 使用

安装后，在 Cursor Composer 中输入：

```
按 CCC 流程跑一个审计任务
```

Cursor 会自动加载 `.cursorrules` 或 `.cursor/rules/*.mdc` 中的规则，从而知道 SKILL.md 的存在。

## 注意事项

- `.cursorrules` 全量进 context（SKILL.md 很大时，设为 Cursor 的 ref 而不是 inline）
- `.cursor/rules/*.mdc` 支持 `globs` 文件模式匹配，按需加载
- Cursor 的 model 选择建议用 Claude（Sonnet / Opus），CCC 协议的经验沉淀在 Claude 族模型上最佳
